import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from app.tasks.invoice_tasks import send_payment_reminders
from app.models.invoice import Invoice, InvoiceStatus, InvoiceType
from app.models.customer import Customer, CustomerType

def test_dunning_email_sending(db, monkeypatch):
    # Setup
    today = date.today()
    overdue_date = today - timedelta(days=4) # 4 days overdue (> 3 days threshold)
    
    customer = Customer(name="Dunning Customer", typ=CustomerType.GASTRO, email="dunning@example.com", aktiv=True)
    db.add(customer)
    db.flush()
    
    # Create Invoice via Service
    from app.services.invoice_service import InvoiceService
    inv_service = InvoiceService(db)
    invoice = inv_service.create_invoice(
        customer_id=customer.id,
        invoice_date=overdue_date - timedelta(days=14),
        due_date=overdue_date
    )
    invoice.invoice_number="RE-DUNNING-001"
    from decimal import Decimal
    inv_service.add_line(invoice.id, "Test", Decimal("1"), "Stk", Decimal("100.00"))
    inv_service.finalize_invoice(invoice.id)
    
    # Manually set to OVERDUE conform to logic
    invoice.status = InvoiceStatus.UEBERFAELLIG
    db.commit()
    
    # Mock EmailService
    mock_email_service = MagicMock()
    mock_email_service.send_email.return_value = True
    
    # Patch the imported email_service AND SessionLocal in invoice_tasks module
    with patch("app.tasks.invoice_tasks.email_service", mock_email_service), \
         patch("app.tasks.invoice_tasks.SessionLocal", return_value=db):
        result = send_payment_reminders()
        
    # Verify
    assert result["status"] == "success"
    assert result["reminders_sent"] == 1
    mock_email_service.send_email.assert_called_once()
    args, kwargs = mock_email_service.send_email.call_args
    assert kwargs["email_to"] == "dunning@example.com"
    assert "RE-DUNNING-001" in kwargs["subject"]
