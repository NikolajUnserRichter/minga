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

    # Verify
    assert count >= 2 # 1 Invoice (Debit), 1 Revenue (Credit), 1 Payment (Debit Bank) = 3 lines actually.
    # Wait, my logic: 1 Debit + N Revenues. So 2 lines for invoice. +1 for Payment. Total 3.
    
    # Invoice Lines
    assert "RE-TEST-001" in csv_content
    assert "119,00" in csv_content
    assert "S" in csv_content # Debit
    assert "H" in csv_content # Credit
    
    # Payment Lines
    assert "Zahlung Invoice Customer" in csv_content
