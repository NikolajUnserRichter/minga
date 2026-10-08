import pytest
from datetime import date, timedelta
from decimal import Decimal
from app.services.datev_service import DatevService
from app.models.invoice import Invoice, InvoiceStatus, InvoiceType, Payment, PaymentMethod, STANDARD_ACCOUNTS
from app.models.customer import Customer, CustomerType
from app.models.product import Product

def test_datev_export_customers(db):
    # Setup
    datev_account = "10005"
    customer = Customer(
        name="Test Datev Customer",
        customer_number="KD-999",
        datev_account=datev_account,
        typ=CustomerType.GASTRO,
        aktiv=True
    )
    db.add(customer)
    db.commit()

    # Execute
    service = DatevService(db)
    csv_content = service.export_customers_csv()

    # Verify
    assert "Konto;Name;Strasse;PLZ;Ort;Land;USt-IdNr;IBAN" in csv_content
    assert f"{datev_account};Test Datev Customer" in csv_content

def test_datev_export_invoices_and_payments(db):
    # Setup
    customer = Customer(
        name="Invoice Customer",
        customer_number="KD-888",
        datev_account="10008",
        typ=CustomerType.GASTRO,
        aktiv=True
    )
    db.add(customer)
    db.flush()

    # Create Invoice via Service
    from app.services.invoice_service import InvoiceService
    inv_service = InvoiceService(db)
    invoice = inv_service.create_invoice(
        customer_id=customer.id,
        invoice_date=date.today(),
        header_text="Test Invoice"
    )
    invoice.invoice_number = "RE-TEST-001"
    

    # Actually add_line defaults to REDUZIERT (7%). Let's force STANDARD.
    # We need TaxRate enum.
    from app.models.invoice import TaxRate
    inv_service.add_line(
        invoice_id=invoice.id,
        description="Standard Item",
        quantity=Decimal("1"),
        unit="Stk",
        unit_price=Decimal("100.00"),
        tax_rate=TaxRate.STANDARD
    )
    
    inv_service.finalize_invoice(invoice.id)
    
    # Add payment
    inv_service.record_payment(
        invoice_id=invoice.id,
        amount=Decimal("119.00"),
        payment_date=date.today(),
        payment_method=PaymentMethod.UEBERWEISUNG
    )

    db.commit()

    # Execute
    service = DatevService(db)
    csv_content, count, total = service.export_invoices_csv(
        from_date=date.today(), 
        to_date=date.today()
    )

    # Verify — spaltengenau: eine Erlöszeile (Debitor an 8400, S) und eine
    # Zahlungszeile (Bank an Debitor, S). Keine Zeile auf 1400, kein Kopfkonto 8300.
    import csv
    import io
    tag = date.today().strftime("%d%m")
    zeilen = list(csv.reader(io.StringIO(csv_content), delimiter=";"))
    assert zeilen == [
        ["Umsatz", "Soll/Haben", "WKZ", "Kurs", "Basisumsatz", "Konto", "Gegenkonto",
         "BU-Schlüssel", "Belegdatum", "Belegfeld 1", "Belegfeld 2", "Buchungstext"],
        ["119,00", "S", "EUR", "", "", "10008", "8400", "", tag, "RE-TEST-001", "",
         "Rechnung 19 % Invoice Customer"],
        ["119,00", "S", "EUR", "", "", "1200", "10008", "", tag, "RE-TEST-001", "",
         "Zahlung Invoice Customer"],
    ]
    assert count == 2
    assert total == Decimal("119.00")
