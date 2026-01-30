import pytest
from datetime import date
from decimal import Decimal
from app.models.product import Product, ProductCategory, TaxRate
from app.models.invoice import Invoice
from app.models.customer import Customer, CustomerType

def test_deposit_logic(db):
    # Setup Products
    # 1. Regular Product (Microgreens)
    greens = Product(
        sku="MG-TEST-DEP",
        name="Microgreens Test",
        category=ProductCategory.MICROGREEN,
        base_unit_id="00000000-0000-0000-0000-000000000000", # Mock ID, hopefully not FK constrained in tests or we need real unit
        # Wait, product.base_unit_id IS constrained. We need a unit.
        is_deposit=False
    )
    # We need a unit. Tests usually need full setup.
    # Let's import UnitOfMeasure and create one.
    from app.models.unit import UnitOfMeasure, UnitCategory
    unit = UnitOfMeasure(name="Stück", code="STK", symbol="Stk", category=UnitCategory.COUNT)
    db.add(unit)
    db.flush()
    
    greens.base_unit_id = unit.id
    
    # 2. Deposit Product (Crate)
    crate = Product(
        sku="DEP-CRATE",
        name="Pfandkiste",
        category=ProductCategory.PACKAGING,
        base_unit_id=unit.id,
        base_price=Decimal("5.00"),
        tax_rate=TaxRate.STANDARD, # Pfand usually standard tax or none? Let's assume Standard (19%)
        is_deposit=True,
        deposit_value=Decimal("5.00")
    )
    
    db.add(greens)
    db.add(crate)
    
    # Setup Customer
    customer = Customer(name="Deposit Customer", typ=CustomerType.GASTRO, aktiv=True)
    db.add(customer)
    db.flush()
    
    # Create Invoice
    from app.services.invoice_service import InvoiceService
    service = InvoiceService(db)
    invoice = service.create_invoice(
        customer_id=customer.id,
        invoice_date=date.today()
    )
    
    # Add Lines
    # 2 Crates @ 5.00
    service.add_line(
        invoice_id=invoice.id,
        description="Pfandkiste",
        product_id=crate.id,
        quantity=Decimal("2"),
        unit="Stk",
        unit_price=Decimal("5.00"),
        tax_rate=TaxRate.STANDARD
    )
    
    # 10 Greens @ 2.00
    service.add_line(
        invoice_id=invoice.id,
        description="Greens",
        product_id=greens.id,
        quantity=Decimal("10"),
        unit="Stk",
        unit_price=Decimal("2.00"),
        tax_rate=TaxRate.REDUZIERT
    )
    
    # Finalize (triggers calculation)
    invoice = service.finalize_invoice(invoice.id)
    db.refresh(invoice) # Ensure lines are loaded
    
    # Verify
    # Total Deposit = 2 * 5.00 * 1.19 (Gross) = 11.90
    deposit_net = Decimal("10.00")
    deposit_gross = (deposit_net * Decimal("1.19")).quantize(Decimal("0.01"))
    
    assert invoice.total_deposit == deposit_gross
    
    # Verify Lines
    deposit_line = next(p for p in invoice.lines if p.product_id == crate.id)
    assert deposit_line.is_deposit == True
    
    greens_line = next(p for p in invoice.lines if p.product_id == greens.id)
    assert greens_line.is_deposit == False
