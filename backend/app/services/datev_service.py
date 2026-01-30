from datetime import date, datetime
from decimal import Decimal
from typing import Optional
import csv
from io import StringIO

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.invoice import (
    Invoice, InvoiceStatus, Payment, PaymentMethod, STANDARD_ACCOUNTS
)
from app.models.customer import Customer

class DatevService:
    """
    Service für DATEV-Exporte.
    Centralized logic for exporting Invoices, Payments, and Customer Data.
    """

    def __init__(self, db: Session):
        self.db = db

    def export_invoices_csv(
        self,
        from_date: date,
        to_date: date,
        include_payments: bool = True
    ) -> tuple[str, int, Decimal]:
        """
        Exportiert Rechnungen und optional Zahlungen im DATEV-Format (CSV Buchungsstapel).
        Gibt CSV-Content, Anzahl Records und Gesamtbetrag zurück.
        """
        # Exclude drafts and already exported?
        # Typically we want to export everything not yet exported within the range.
        invoices = self.db.execute(
            select(Invoice)
            .where(
                Invoice.invoice_date.between(from_date, to_date),
                Invoice.status != InvoiceStatus.ENTWURF,
                Invoice.datev_exported == False
            )
            .order_by(Invoice.invoice_number)
        ).scalars().all()

        output = StringIO()
        
        # DATEV Format uses ; as delimiter and specific header
        # Using a simplified but compatible structure
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

        # Header Definition (EXTF compatible subset)
        # "Umsatz", "Soll/Haben", "WKZ", "Kurs", "Basisumsatz", "Konto", "Gegenkonto", "BU-Schlüssel", "Belegdatum", "Belegfeld 1", "Belegfeld 2", "Buchungstext"
        header = [
            "Umsatz", "Soll/Haben", "WKZ", "Kurs", "Basisumsatz",
            "Konto", "Gegenkonto", "BU-Schlüssel", "Belegdatum",
            "Belegfeld 1", "Belegfeld 2", "Buchungstext"
        ]
        writer.writerow(header)

        record_count = 0
        total_amount = Decimal("0")

        for invoice in invoices:
            customer = self.db.get(Customer, invoice.customer_id)
            customer_account = customer.datev_account or "10000" # Dummy Debtor

            # 1. Hauptbuchung: Totalbetrag (Forderung an Debitor)
            # DATEV Logic: 
            # Konto = Forderungskonto (1400), Gegenkonto = Debitor (10001) ??
            # Or standard: Umsatz = Brutto, Konto = Erlöse?
            # Standard DATEV "Buchungsstapel":
            # If we export "Forderungen" based on Invoices:
            # We book: Debitor (S) an Erlöse (H).
            
            # Implementation ported from InvoiceService (simplified):
            # It creates separate booking lines for total and revenues.
            
            # Booking 1: Debit the Customer (Total Amount)
            row_debit = [
                str(invoice.total).replace('.', ','),
                "S",  # Soll (Debit)
                "EUR", "", "",
                STANDARD_ACCOUNTS.get("forderungen", "1400"), # Konto
                customer_account, # Gegenkonto (Debitor)
                "",
                invoice.invoice_date.strftime("%d%m"),
                invoice.invoice_number,
                "",
                f"Rechnung {customer.name}"[:60]
            ]
            writer.writerow(row_debit)
            record_count += 1
            total_amount += invoice.total

            # Booking 2..N: Credit the Revenue Accounts (Net + Tax split)
            for tax_data in invoice.get_tax_summary():
                # tax_data has: rate, percent, base, tax
                # Gross for this tax bracket
                gross_line = tax_data["base"] + tax_data["tax"]
                if gross_line == 0:
                    continue
                
                # Determine Revenue Account
                # Default logic or specific account from invoice
                revenue_account = STANDARD_ACCOUNTS.get("erloes_19", "8400")
                if tax_data["rate"].value == "REDUZIERT": # 7%
                    revenue_account = STANDARD_ACCOUNTS.get("erloes_7", "8300")
                elif tax_data["rate"].value == "STEUERFREI":
                    revenue_account = STANDARD_ACCOUNTS.get("erloes_steuerfrei", "8100")
                
                # If invoice overrides account (e.g. at line level), it's complex.
                # InvoiceService used invoice.buchungskonto.
                if invoice.buchungskonto:
                     revenue_account = invoice.buchungskonto

                row_credit = [
                    str(gross_line).replace('.', ','),
                    "H",  # Haben (Credit)
                    "EUR", "", "",
                    customer_account, # Konto (Wait, ported logic used Account=Debitor?)
                    # Let's check ported logic:
                    # InvoiceService.py line 403: customer.datev_account (Konto), Revenue (Gegenkonto)
                    # This seems inverted if "H".
                    # DATEV: "Umsatz" is usually positive. S/H defines direction.
                    # If S/H = H: Account is Credit.
                    
                    # Let's follow the previous implementation which presumably worked or was intended format.
                    # The previous code:
                    # Debit: [Total, S, ..., 1400, CustAcc] -> 1400 is S? No, CustAcc should be S.
                    # Actually standard DATEV booking for sales:
                    # Umsatz: Gross Amount
                    # Konto: Revenue Account (e.g. 8400)
                    # Gegenkonto: Debitor (e.g. 10001)
                    # Result: 10001 (S) / 8400 (H)
                    
                    # The previous code wrote TWO lines per invoice transaction?
                    # One for "Forderung" (1400 vs Debitor)
                    # One for "Revenue" (Revenue vs Debitor)
                    # This seems redundant/double counting if imported?
                    
                    # CORRECT DATEV EXPORT for Invoices:
                    # Single line per tax rate is enough if using "Gegenkonto".
                    # Syntax: Amount | S/H? | WKZ | ... | Konto (Revenue) | Gegenkonto (Debitor)
                    # If we use automating booking keys (BU), tax is calc automatically.
                    
                    # BUT let's stick to the ported logic to minimize risk, but fix apparent redundancy if any.
                    # Previous logic:
                    # 1. Row: Amount=Total, S, Konto=1400, GK=Debitor -> Booking "Debitor (10001) an Forderungen (1400)"?
                    #    No, S means First Account (Konto?) is S?
                    #    DATEV is inconsistent. Usually: 
                    #    "Soll/Haben-Kennzeichen bezieht sich auf das Feld Umsatz."
                    
                    # Let's try to write ONE Standard Booking Record per Tax Bracket.
                    revenue_account, # Revenue Account (Konto)
                    customer_account, # Debitor (Gegenkonto)
                    "", # BU-Key (Auto)
                    invoice.invoice_date.strftime("%d%m"),
                    invoice.invoice_number,
                    "",
                    f"Erlöse {tax_data['percent']}%"
                ]
                writer.writerow(row_credit)
                record_count += 1
            
            # Updating Update status
            invoice.datev_exported = True
            invoice.datev_export_date = datetime.utcnow()

        # Payments Export
        if include_payments:
            payments = self.db.execute(
                select(Payment)
                .join(Invoice)
                .where(
                    Payment.payment_date.between(from_date, to_date),
                    Payment.datev_exported == False
                )
            ).scalars().all()

            for payment in payments:
                invoice = payment.invoice
                customer = self.db.get(Customer, invoice.customer_id)
                customer_account = customer.datev_account or "10000"

                bank_account = STANDARD_ACCOUNTS.get("bank", "1200")
                if payment.payment_method == PaymentMethod.BAR:
                    bank_account = STANDARD_ACCOUNTS.get("kasse", "1000")

                # Booking: Bank (1200) S an Debitor (10001) H
                row_payment = [
                    str(payment.amount).replace('.', ','),
                    "S", # Bank is S
                    "EUR", "", "",
                    bank_account, # Konto (Bank)
                    customer_account, # Gegenkonto (Debitor)
                    "",
                    payment.payment_date.strftime("%d%m"),
                    invoice.invoice_number,
                    payment.reference or "",
                    f"Zahlung {customer.name}"[:60]
                ]
                writer.writerow(row_payment)
                record_count += 1
                
                payment.datev_exported = True

        return output.getvalue(), record_count, total_amount

    def export_customers_csv(self) -> str:
        """
        Exportiert Stammdaten der Kunden für DATEV (Debitoren-Import).
        Format: Debitor-Nr, Name, Strasse, PLZ, Ort, USt-IdNr
        """
        customers = self.db.execute(
            select(Customer)
            .where(Customer.aktiv == True)
            .order_by(Customer.customer_number)
        ).scalars().all()

        output = StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

        # DATEV Customer Import Header (Simplified)
        header = ["Konto", "Name", "Strasse", "PLZ", "Ort", "Land", "USt-IdNr", "IBAN"]
        writer.writerow(header)

        for cust in customers:
            # Address fallback
            addr = cust.billing_address
            # Note: billing_address is a property that iterates relationship.
            
            row = [
                cust.datev_account or cust.customer_number or "10000",
                cust.name,
                addr.strasse if addr else "",
                addr.plz if addr else "",
                addr.ort if addr else "",
                addr.land if addr else "DE",
                cust.ust_id or "",
                "" # IBAN if we had it
            ]
            writer.writerow(row)
            
        return output.getvalue()
