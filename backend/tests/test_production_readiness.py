"""
Tests for /health/detailed endpoint, credit limit enforcement,
multi-level dunning, and quality control.
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from app.models.invoice import Invoice, InvoiceStatus, InvoiceType
from app.models.customer import Customer, CustomerType
from app.models.order import Order, OrderStatus


# =========================================
# Health Endpoint Tests
# =========================================

def test_health_basic(client):
    """Basic health returns 200."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_health_detailed_structure(client):
    """Detailed health returns expected keys."""
    response = client.get("/health/detailed")
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "redis" in data
    assert "keycloak" in data
    assert "version" in data


# =========================================
# Credit Limit Tests
# =========================================

def test_order_within_credit_limit(client):
    """Order creation succeeds within credit limit."""
    # Create customer with limit
    cust = client.post("/api/v1/sales/customers", json={
        "name": "Credit Test GmbH",
        "typ": "GASTRO",
        "credit_limit": 1000.00,
    })
    assert cust.status_code == 201
    customer_id = cust.json()["id"]

    # Create small order
    order = client.post("/api/v1/sales/orders", json={
        "customer_id": customer_id,
        "requested_delivery_date": (date.today() + timedelta(days=3)).isoformat(),
        "lines": [{
            "product_name": "Sonnenblume 100g",
            "quantity": 1,
            "unit": "STK",
            "unit_price": 5.0,
        }]
    })
    assert order.status_code == 201


def test_order_exceeds_credit_limit(client):
    """Order creation fails when credit limit is exceeded."""
    cust = client.post("/api/v1/sales/customers", json={
        "name": "Overcredit GmbH",
        "typ": "GASTRO",
        "credit_limit": 10.00,
    })
    assert cust.status_code == 201
    customer_id = cust.json()["id"]

    # Order that exceeds the 10 EUR limit
    order = client.post("/api/v1/sales/orders", json={
        "customer_id": customer_id,
        "requested_delivery_date": (date.today() + timedelta(days=3)).isoformat(),
        "lines": [{
            "product_name": "Expensive Item",
            "quantity": 10,
            "unit": "STK",
            "unit_price": 50.0,
        }]
    })
    assert order.status_code == 400
    assert "Kreditlimit" in order.json()["detail"]


def test_order_no_credit_limit(client):
    """Order creation succeeds when no credit limit is set."""
    cust = client.post("/api/v1/sales/customers", json={
        "name": "NoLimit GmbH",
        "typ": "GASTRO",
    })
    assert cust.status_code == 201
    customer_id = cust.json()["id"]

    order = client.post("/api/v1/sales/orders", json={
        "customer_id": customer_id,
        "requested_delivery_date": (date.today() + timedelta(days=3)).isoformat(),
        "lines": [{
            "product_name": "Sonnenblume 100g",
            "quantity": 100,
            "unit": "STK",
            "unit_price": 999.0,
        }]
    })
    assert order.status_code == 201


# =========================================
# Multi-Level Dunning Tests
# =========================================

def test_dunning_level1(db, monkeypatch):
    """Level 1 reminder is sent after dunning_level1_days."""
    from app.tasks.invoice_tasks import send_payment_reminders

    today = date.today()
    # Invoice overdue by 4 days (> default 3)
    due = today - timedelta(days=4)

    customer = Customer(
        name="Dunning L1", typ=CustomerType.GASTRO,
        email="l1@example.com", aktiv=True,
    )
    db.add(customer)
    db.flush()

    from app.services.invoice_service import InvoiceService
    svc = InvoiceService(db)
    inv = svc.create_invoice(customer_id=customer.id, invoice_date=due - timedelta(days=14), due_date=due)
    inv.invoice_number = "RE-DUN-L1"
    svc.add_line(inv.id, "Test", Decimal("1"), "Stk", Decimal("100.00"))
    svc.finalize_invoice(inv.id)
    inv.status = InvoiceStatus.UEBERFAELLIG
    inv.reminder_level = 0
    db.commit()

    mock_email = MagicMock()
    mock_email.send_email.return_value = True

    with patch("app.tasks.invoice_tasks.email_service", mock_email), \
         patch("app.tasks.invoice_tasks.SessionLocal", return_value=db):
        result = send_payment_reminders()

    assert result["reminders_sent"] == 1
    db.refresh(inv)
    assert inv.reminder_level == 1


def test_dunning_level2(db, monkeypatch):
    """Level 2 reminder is sent after dunning_level2_days."""
    from app.tasks.invoice_tasks import send_payment_reminders

    today = date.today()
    due = today - timedelta(days=15)  # > default 14

    customer = Customer(
        name="Dunning L2", typ=CustomerType.GASTRO,
        email="l2@example.com", aktiv=True,
    )
    db.add(customer)
    db.flush()

    from app.services.invoice_service import InvoiceService
    svc = InvoiceService(db)
    inv = svc.create_invoice(customer_id=customer.id, invoice_date=due - timedelta(days=14), due_date=due)
    inv.invoice_number = "RE-DUN-L2"
    svc.add_line(inv.id, "Test", Decimal("1"), "Stk", Decimal("100.00"))
    svc.finalize_invoice(inv.id)
    inv.status = InvoiceStatus.UEBERFAELLIG
    inv.reminder_level = 1  # Already had level 1
    db.commit()

    mock_email = MagicMock()
    mock_email.send_email.return_value = True

    with patch("app.tasks.invoice_tasks.email_service", mock_email), \
         patch("app.tasks.invoice_tasks.SessionLocal", return_value=db):
        result = send_payment_reminders()

    assert result["reminders_sent"] == 1
    db.refresh(inv)
    assert inv.reminder_level == 2
    assert inv.status == InvoiceStatus.MAHNVERFAHREN


def test_dunning_level3(db, monkeypatch):
    """Level 3 (final warning) is sent after dunning_level3_days."""
    from app.tasks.invoice_tasks import send_payment_reminders

    today = date.today()
    due = today - timedelta(days=30)  # > default 28

    customer = Customer(
        name="Dunning L3", typ=CustomerType.GASTRO,
        email="l3@example.com", aktiv=True,
    )
    db.add(customer)
    db.flush()

    from app.services.invoice_service import InvoiceService
    svc = InvoiceService(db)
    inv = svc.create_invoice(customer_id=customer.id, invoice_date=due - timedelta(days=14), due_date=due)
    inv.invoice_number = "RE-DUN-L3"
    svc.add_line(inv.id, "Test", Decimal("1"), "Stk", Decimal("100.00"))
    svc.finalize_invoice(inv.id)
    inv.status = InvoiceStatus.MAHNVERFAHREN
    inv.reminder_level = 2
    db.commit()

    mock_email = MagicMock()
    mock_email.send_email.return_value = True

    with patch("app.tasks.invoice_tasks.email_service", mock_email), \
         patch("app.tasks.invoice_tasks.SessionLocal", return_value=db):
        result = send_payment_reminders()

    assert result["reminders_sent"] == 1
    db.refresh(inv)
    assert inv.reminder_level == 3


def test_dunning_no_escalation_before_threshold(db):
    """No reminder sent if not enough days have passed."""
    from app.tasks.invoice_tasks import send_payment_reminders

    today = date.today()
    due = today - timedelta(days=1)  # Only 1 day overdue (< 3)

    customer = Customer(
        name="Too Early", typ=CustomerType.GASTRO,
        email="early@example.com", aktiv=True,
    )
    db.add(customer)
    db.flush()

    from app.services.invoice_service import InvoiceService
    svc = InvoiceService(db)
    inv = svc.create_invoice(customer_id=customer.id, invoice_date=due - timedelta(days=14), due_date=due)
    inv.invoice_number = "RE-EARLY-001"
    svc.add_line(inv.id, "Test", Decimal("1"), "Stk", Decimal("50.00"))
    svc.finalize_invoice(inv.id)
    inv.status = InvoiceStatus.UEBERFAELLIG
    inv.reminder_level = 0
    db.commit()

    mock_email = MagicMock()

    with patch("app.tasks.invoice_tasks.email_service", mock_email), \
         patch("app.tasks.invoice_tasks.SessionLocal", return_value=db):
        result = send_payment_reminders()

    assert result["reminders_sent"] == 0
    assert mock_email.send_email.call_count == 0


# =========================================
# Quality Control Tests
# =========================================

def test_quality_auto_approved(db):
    """Harvest with good quality is auto-approved."""
    from app.services.production import ProductionService
    from app.models.seed import Seed, SeedBatch

    seed = Seed(
        name="QC-Test", sorte="Standard",
        lieferant="TestLieferant",
        keimdauer_tage=2, wachstumsdauer_tage=8,
        erntefenster_min_tage=9, erntefenster_optimal_tage=11,
        erntefenster_max_tage=14, ertrag_gramm_pro_tray=350,
        verlustquote_prozent=5.0,
    )
    db.add(seed)
    db.flush()

    sb = SeedBatch(
        seed_id=seed.id, charge_nummer="QC-BATCH-001",
        menge_gramm=1000, eingang_datum=date.today() - timedelta(days=30),
    )
    db.add(sb)
    db.flush()

    svc = ProductionService(db)
    gb = svc.create_grow_batch(
        seed_batch_id=sb.id, tray_anzahl=5,
        aussaat_datum=date.today() - timedelta(days=10),
    )
    db.flush()

    harvest = svc.record_harvest(
        grow_batch_id=gb.id,
        ernte_datum=date.today(),
        menge_gramm=Decimal("1500"),
        verlust_gramm=Decimal("50"),
        qualitaet_note=4,
    )
    db.flush()

    assert harvest.quality_approved is True
    assert harvest.quality_notes is None


def test_quality_rejected_low_note(db):
    """Harvest with low quality note is rejected."""
    from app.services.production import ProductionService
    from app.models.seed import Seed, SeedBatch

    seed = Seed(
        name="QC-Low", sorte="Bad",
        lieferant="TestLieferant",
        keimdauer_tage=2, wachstumsdauer_tage=8,
        erntefenster_min_tage=9, erntefenster_optimal_tage=11,
        erntefenster_max_tage=14, ertrag_gramm_pro_tray=350,
        verlustquote_prozent=5.0,
    )
    db.add(seed)
    db.flush()

    sb = SeedBatch(
        seed_id=seed.id, charge_nummer="QC-LOW-001",
        menge_gramm=1000, eingang_datum=date.today() - timedelta(days=30),
    )
    db.add(sb)
    db.flush()

    svc = ProductionService(db)
    gb = svc.create_grow_batch(
        seed_batch_id=sb.id, tray_anzahl=5,
        aussaat_datum=date.today() - timedelta(days=10),
    )
    db.flush()

    harvest = svc.record_harvest(
        grow_batch_id=gb.id,
        ernte_datum=date.today(),
        menge_gramm=Decimal("1000"),
        verlust_gramm=Decimal("50"),
        qualitaet_note=1,  # Below min of 2
    )
    db.flush()

    assert harvest.quality_approved is False
    assert "Mindestanforderung" in harvest.quality_notes


def test_quality_rejected_high_loss(db):
    """Harvest with high loss rate is rejected."""
    from app.services.production import ProductionService
    from app.models.seed import Seed, SeedBatch

    seed = Seed(
        name="QC-Loss", sorte="Lossy",
        lieferant="TestLieferant",
        keimdauer_tage=2, wachstumsdauer_tage=8,
        erntefenster_min_tage=9, erntefenster_optimal_tage=11,
        erntefenster_max_tage=14, ertrag_gramm_pro_tray=350,
        verlustquote_prozent=5.0,
    )
    db.add(seed)
    db.flush()

    sb = SeedBatch(
        seed_id=seed.id, charge_nummer="QC-LOSS-001",
        menge_gramm=1000, eingang_datum=date.today() - timedelta(days=30),
    )
    db.add(sb)
    db.flush()

    svc = ProductionService(db)
    gb = svc.create_grow_batch(
        seed_batch_id=sb.id, tray_anzahl=5,
        aussaat_datum=date.today() - timedelta(days=10),
    )
    db.flush()

    harvest = svc.record_harvest(
        grow_batch_id=gb.id,
        ernte_datum=date.today(),
        menge_gramm=Decimal("500"),
        verlust_gramm=Decimal("500"),  # 50% loss >> 20% max
        qualitaet_note=4,
    )
    db.flush()

    assert harvest.quality_approved is False
    assert "Verlustquote" in harvest.quality_notes
