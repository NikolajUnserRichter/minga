from typing import Optional
"""
Rechnungs-Service - Business Logic für Rechnungen
Mit deutscher MwSt-Berechnung und DATEV-Export
"""
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from io import StringIO
import csv
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_

from app.models.invoice import (
    Invoice, InvoiceLine, Payment,
    InvoiceStatus, InvoiceType, TaxRate, PaymentMethod,
    generate_invoice_number, STANDARD_ACCOUNTS
)
from app.models.customer import Customer, AddressType
from app.models.order import Order, OrderLine
from app.models.product import Product


class InvoiceService:
    """Service für Rechnungs-Operationen"""

    def __init__(self, db: Session):
        self.db = db

    def create_invoice(
        self,
        customer_id: UUID,
        invoice_date: Optional[date] = None,
        delivery_date: Optional[date] = None,
        order_id: Optional[UUID] = None,
        invoice_type: InvoiceType = InvoiceType.RECHNUNG,
        original_invoice_id: Optional[UUID] = None,
        discount_percent: Decimal = Decimal("0"),
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None,
        internal_notes: Optional[str] = None,
        due_date: Optional[date] = None,
        buchungskonto: Optional[str] = None,
    ) -> Invoice:
        """
        Erstellt eine neue Rechnung.
        """
        customer = self.db.get(Customer, customer_id)
        if not customer:
            raise ValueError("Kunde nicht gefunden")

        # Rechnungsnummer generieren
        invoice_number = self._generate_next_invoice_number(invoice_type)

        # Fälligkeitsdatum berechnen
        inv_date = invoice_date or date.today()
        if due_date is None:
            due_date = inv_date + timedelta(days=customer.payment_days)

        # Adressen als Snapshot speichern
        billing_addr = None
        shipping_addr = None
        if customer.billing_address:
            billing_addr = {
                "name": customer.billing_address.name or customer.name,
                "strasse": customer.billing_address.strasse,
                "hausnummer": customer.billing_address.hausnummer,
                "plz": customer.billing_address.plz,
                "ort": customer.billing_address.ort,
                "land": customer.billing_address.land,
            }
        if customer.shipping_address:
            shipping_addr = {
                "name": customer.shipping_address.name or customer.name,
                "strasse": customer.shipping_address.strasse,
                "hausnummer": customer.shipping_address.hausnummer,
                "plz": customer.shipping_address.plz,
                "ort": customer.shipping_address.ort,
                "land": customer.shipping_address.land,
            }

        invoice = Invoice(
            invoice_number=invoice_number,
            invoice_type=invoice_type,
            customer_id=customer_id,
            order_id=order_id,
            original_invoice_id=original_invoice_id,
            invoice_date=inv_date,
            delivery_date=delivery_date,
            due_date=due_date,
            status=InvoiceStatus.ENTWURF,
            billing_address=billing_addr,
            shipping_address=shipping_addr,
            discount_percent=discount_percent,
            header_text=header_text,
            footer_text=footer_text,
            internal_notes=internal_notes,
            buchungskonto=buchungskonto or STANDARD_ACCOUNTS["erloes_7"],  # Default 7% Erlöse
        )

        self.db.add(invoice)
        self.db.flush()

        return invoice

    def add_line(
        self,
        invoice_id: UUID,
        description: str,
        quantity: Decimal,
        unit: str,
        unit_price: Decimal,
        product_id: Optional[UUID] = None,
        sku: Optional[str] = None,
        discount_percent: Decimal = Decimal("0"),
        tax_rate: TaxRate = TaxRate.REDUZIERT,
        order_item_id: Optional[UUID] = None,
        harvest_batch_ids: Optional[list[UUID]] = None,
        buchungskonto: Optional[str] = None,
    ) -> InvoiceLine:
        """
        Fügt eine Position zur Rechnung hinzu.
        """
        invoice = self.db.get(Invoice, invoice_id)
        if not invoice:
            raise ValueError("Rechnung nicht gefunden")

        if invoice.status != InvoiceStatus.ENTWURF:
            raise ValueError("Nur Entwürfe können bearbeitet werden")

        # Position ermitteln
        max_pos = self.db.execute(
            select(func.max(InvoiceLine.position))
            .where(InvoiceLine.invoice_id == invoice_id)
        ).scalar() or 0

        # Buchungskonto basierend auf Steuersatz
        if not buchungskonto:
            buchungskonto = {
                TaxRate.REDUZIERT: STANDARD_ACCOUNTS["erloes_7"],
                TaxRate.STANDARD: STANDARD_ACCOUNTS["erloes_19"],
                TaxRate.STEUERFREI: STANDARD_ACCOUNTS["erloes_steuerfrei"],
            }.get(tax_rate, STANDARD_ACCOUNTS["erloes_7"])

        line = InvoiceLine(
            invoice_id=invoice_id,
            position=max_pos + 1,
            product_id=product_id,
            description=description,
            sku=sku,
            quantity=quantity,
            unit=unit,
            unit_price=unit_price,
            discount_percent=discount_percent,
            tax_rate=tax_rate,
            order_item_id=order_item_id,
            harvest_batch_ids=[str(h) for h in harvest_batch_ids] if harvest_batch_ids else None,
            buchungskonto=buchungskonto,
        )

        # Zeilenbetrag berechnen
        line.calculate_line_total()

        self.db.add(line)
        self.db.flush()

        # Rechnungssummen neu berechnen
        invoice.calculate_totals()

        return line

    def create_invoice_from_order(self, order_id: UUID) -> Invoice:
        """
        Erstellt eine Rechnung aus einer Bestellung.
        """
        order = self.db.get(Order, order_id)
        if not order:
            raise ValueError("Bestellung nicht gefunden")

        # Rechnung erstellen
        invoice = self.create_invoice(
            customer_id=order.kunde_id,
            order_id=order_id,
            delivery_date=order.liefer_datum,
        )

        # Positionen aus Bestellung übernehmen
        for item in order.items:
            # Produkt laden für Beschreibung und MwSt
            product = self.db.get(Product, item.seed_id) if item.seed_id else None

            self.add_line(
                invoice_id=invoice.id,
                description=product.name if product else f"Position {item.id}",
                quantity=item.menge,
                unit=item.einheit,
                unit_price=item.preis_pro_einheit or Decimal("0"),
                product_id=product.id if product else None,
                sku=product.sku if product else None,
                tax_rate=TaxRate.REDUZIERT,  # Lebensmittel
                order_item_id=item.id,
                harvest_batch_ids=[item.harvest_id] if item.harvest_id else None,
            )

        return invoice

    def finalize_invoice(self, invoice_id: UUID) -> Invoice:
        """
        Finalisiert eine Rechnung (Entwurf -> Offen).
        """
        invoice = self.db.get(Invoice, invoice_id)
        if not invoice:
            raise ValueError("Rechnung nicht gefunden")

        if invoice.status != InvoiceStatus.ENTWURF:
            raise ValueError("Nur Entwürfe können finalisiert werden")

        if not invoice.lines:
            raise ValueError("Rechnung hat keine Positionen")

        # Summen final berechnen
        invoice.calculate_totals()

        # Status ändern
        invoice.status = InvoiceStatus.OFFEN
        invoice.sent_at = datetime.utcnow()

        return invoice

    def record_payment(
        self,
        invoice_id: UUID,
        amount: Decimal,
        payment_date: Optional[date] = None,
        payment_method: PaymentMethod = PaymentMethod.UEBERWEISUNG,
        reference: Optional[str] = None,
        bank_reference: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Payment:
        """
        Erfasst eine Zahlung für eine Rechnung.
        """
        invoice = self.db.get(Invoice, invoice_id)
        if not invoice:
            raise ValueError("Rechnung nicht gefunden")

        if invoice.status == InvoiceStatus.STORNIERT:
            raise ValueError("Stornierte Rechnungen können nicht bezahlt werden")

        payment = Payment(
            invoice_id=invoice_id,
            payment_date=payment_date or date.today(),
            amount=amount,
            payment_method=payment_method,
            reference=reference,
            bank_reference=bank_reference,
            notes=notes,
        )

        self.db.add(payment)
        self.db.flush()

        # Bezahlten Betrag aktualisieren
        invoice.paid_amount = sum(p.amount for p in invoice.payments)

        # Status aktualisieren
        if invoice.paid_amount >= invoice.total:
            invoice.status = InvoiceStatus.BEZAHLT
        elif invoice.paid_amount > 0:
            invoice.status = InvoiceStatus.TEILBEZAHLT

        return payment

    def cancel_invoice(
        self,
        invoice_id: UUID,
        reason: str,
        create_credit_note: bool = True
    ) -> tuple[Invoice, Optional[Invoice]]:
        """
        Storniert eine Rechnung und erstellt optional eine Gutschrift.
        """
        invoice = self.db.get(Invoice, invoice_id)
        if not invoice:
            raise ValueError("Rechnung nicht gefunden")

        if invoice.status == InvoiceStatus.STORNIERT:
            raise ValueError("Rechnung ist bereits storniert")

        # Original stornieren
        invoice.status = InvoiceStatus.STORNIERT
        invoice.internal_notes = f"{invoice.internal_notes or ''}\n\nStorniert: {reason}".strip()

        credit_note = None
        if create_credit_note and invoice.total > 0:
            # Gutschrift erstellen
            credit_note = self.create_invoice(
                customer_id=invoice.customer_id,
                invoice_type=InvoiceType.GUTSCHRIFT,
                original_invoice_id=invoice_id,
                header_text=f"Gutschrift zu Rechnung {invoice.invoice_number}",
            )

            # Positionen kopieren (mit negativen Beträgen)
            for line in invoice.lines:
                self.add_line(
                    invoice_id=credit_note.id,
                    description=line.description,
                    quantity=-line.quantity,  # Negativ für Gutschrift
                    unit=line.unit,
                    unit_price=line.unit_price,
                    product_id=line.product_id,
                    sku=line.sku,
                    discount_percent=line.discount_percent,
                    tax_rate=line.tax_rate,
                )

            # Gutschrift sofort finalisieren
            credit_note.status = InvoiceStatus.OFFEN
            credit_note.sent_at = datetime.utcnow()

        return invoice, credit_note

    def check_overdue_invoices(self) -> list[Invoice]:
        """
        Prüft und markiert überfällige Rechnungen.
        """
        today = date.today()
        overdue = self.db.execute(
            select(Invoice)
            .where(
                Invoice.status == InvoiceStatus.OFFEN,
                Invoice.due_date < today
            )
        ).scalars().all()

        for invoice in overdue:
            invoice.status = InvoiceStatus.UEBERFAELLIG

        return overdue

    def export_datev(
        self,
        from_date: date,
        to_date: date,
        include_payments: bool = True
    ) -> tuple[str, int, Decimal]:
        """
        Exportiert Rechnungen im DATEV-Format.
        Gibt CSV-Content, Anzahl Records und Gesamtbetrag zurück.
        """
        invoices = self.db.execute(
            select(Invoice)
            .where(
                Invoice.invoice_date.between(from_date, to_date),
                Invoice.status != InvoiceStatus.ENTWURF,
                Invoice.datev_exported == False
            )
        ).scalars().all()

        output = StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

        # DATEV Header (vereinfacht)
        writer.writerow([
            "Umsatz", "Soll/Haben", "WKZ", "Kurs", "Basisumsatz",
            "Konto", "Gegenkonto", "BU-Schlüssel", "Belegdatum",
            "Belegfeld 1", "Belegfeld 2", "Buchungstext"
        ])

        record_count = 0
        total_amount = Decimal("0")

        for invoice in invoices:
            customer = self.db.get(Customer, invoice.customer_id)

            # Hauptbuchung (Forderung)
            writer.writerow([
                str(invoice.total).replace('.', ','),
                "S",  # Soll
                "EUR",
                "",
                "",
                STANDARD_ACCOUNTS["forderungen"],
                customer.datev_account or "10000",
                "",
                invoice.invoice_date.strftime("%d%m"),
                invoice.invoice_number,
                "",
                f"Rechnung {customer.name}"
            ])
            record_count += 1
            total_amount += invoice.total

            # Erlösbuchungen nach Steuersatz
            for tax_data in invoice.get_tax_summary():
                writer.writerow([
                    str(tax_data["base"]).replace('.', ','),
                    "H",  # Haben
                    "EUR",
                    "",
                    "",
                    customer.datev_account or "10000",
                    tax_data["rate"].value == "REDUZIERT" and STANDARD_ACCOUNTS["erloes_7"] or STANDARD_ACCOUNTS["erloes_19"],
                    str(tax_data["percent"]),
                    invoice.invoice_date.strftime("%d%m"),
                    invoice.invoice_number,
                    "",
                    f"Erlöse {tax_data['percent']}%"
                ])
                record_count += 1

            # Als exportiert markieren
            invoice.datev_exported = True
            invoice.datev_export_date = datetime.utcnow()

        # Zahlungen exportieren
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

                # Zahlungseingang
                bank_account = STANDARD_ACCOUNTS["bank"]
                if payment.payment_method == PaymentMethod.BAR:
                    bank_account = STANDARD_ACCOUNTS["kasse"]

                writer.writerow([
                    str(payment.amount).replace('.', ','),
                    "S",
                    "EUR",
                    "",
                    "",
                    bank_account,
                    customer.datev_account or "10000",
                    "",
                    payment.payment_date.strftime("%d%m"),
                    invoice.invoice_number,
                    payment.reference or "",
                    f"Zahlung {customer.name}"
                ])
                record_count += 1

                payment.datev_exported = True

        return output.getvalue(), record_count, total_amount

    def get_revenue_summary(self, from_date: date, to_date: date) -> dict:
        """
        Umsatzübersicht für Zeitraum.
        """
        result = self.db.execute(
            select(
                func.sum(Invoice.total).label("total"),
                func.sum(Invoice.paid_amount).label("paid"),
                func.count(Invoice.id).label("count")
            )
            .where(
                Invoice.invoice_date.between(from_date, to_date),
                Invoice.status.notin_([InvoiceStatus.ENTWURF, InvoiceStatus.STORNIERT])
            )
        ).first()

        open_amount = self.db.execute(
            select(func.sum(Invoice.total - Invoice.paid_amount))
            .where(
                Invoice.status.in_([InvoiceStatus.OFFEN, InvoiceStatus.TEILBEZAHLT, InvoiceStatus.UEBERFAELLIG])
            )
        ).scalar() or Decimal("0")

        return {
            "total_revenue": result.total or Decimal("0"),
            "total_paid": result.paid or Decimal("0"),
            "invoice_count": result.count or 0,
            "open_amount": open_amount,
        }

    def _generate_next_invoice_number(self, invoice_type: InvoiceType) -> str:
        """
        Generiert die nächste Rechnungsnummer.
        Format: RE-2026-00001 oder GS-2026-00001 (Gutschrift)
        """
        year = date.today().year
        prefix = "GS" if invoice_type == InvoiceType.GUTSCHRIFT else "RE"

        last_number = self.db.execute(
            select(func.max(Invoice.invoice_number))
            .where(Invoice.invoice_number.like(f"{prefix}-{year}-%"))
        ).scalar()

        if last_number:
            sequence = int(last_number.split("-")[-1]) + 1
        else:
            sequence = 1

        return generate_invoice_number(year, sequence, prefix)
