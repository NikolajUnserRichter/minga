"""
Procurement (Einkauf) Tests — Purchase Orders + Wareneingang.

Direktes DB-Session-Fixture (wie test_services.py), umgeht das
tenant-geroutete API-Client-Setup. Testet die Kern-Business-Logik:
Zeilen-/Gesamtsummen, Bestellanlage, Teil-/Vollwareneingang + Status.
"""
import pytest
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.seed import Supplier
from app.models.invoice import TaxRate
from app.models.procurement import (
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
)
from app.services.procurement_service import ProcurementService


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def supplier(db):
    s = Supplier(name="Großhandel Müller GmbH")
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


# ---------- Modell-Ebene: Summen ----------

def test_line_totals_standard_vat():
    line = PurchaseOrderLine(
        position=1,
        beschreibung="Kaffeebohnen 1kg",
        quantity=Decimal("10"),
        unit="KG",
        unit_price=Decimal("15.00"),
        tax_rate=TaxRate.STANDARD,  # 19 %
    )
    line.calculate_line_totals()
    assert line.line_net == Decimal("150.00")
    assert line.line_vat == Decimal("28.50")
    assert line.line_gross == Decimal("178.50")


def test_line_totals_with_discount():
    line = PurchaseOrderLine(
        position=1, beschreibung="Ware", quantity=Decimal("10"),
        unit="STK", unit_price=Decimal("10.00"),
        tax_rate=TaxRate.STANDARD, discount_percent=Decimal("10"),
    )
    line.calculate_line_totals()
    assert line.line_net == Decimal("90.00")      # 100 - 10 %
    assert line.line_vat == Decimal("17.10")      # 19 % von 90
    assert line.line_gross == Decimal("107.10")


def test_purchase_order_totals_sum_lines():
    po = PurchaseOrder(po_number="EK-2026-0001")
    for i, (qty, price) in enumerate([(Decimal("10"), Decimal("15.00")),
                                      (Decimal("5"), Decimal("4.00"))], start=1):
        ln = PurchaseOrderLine(
            position=i, beschreibung=f"Pos {i}", quantity=qty, unit="STK",
            unit_price=price, tax_rate=TaxRate.STANDARD,
        )
        ln.calculate_line_totals()
        po.lines.append(ln)
    po.calculate_totals()
    assert po.total_net == Decimal("170.00")       # 150 + 20
    assert po.total_vat == Decimal("32.30")        # 19 % von 170
    assert po.total_gross == Decimal("202.30")


# ---------- Service-Ebene ----------

def test_create_purchase_order(db, supplier):
    svc = ProcurementService(db)
    po = svc.create_purchase_order(
        supplier_id=supplier.id,
        lines=[
            {"beschreibung": "Kaffeebohnen 1kg", "quantity": Decimal("10"),
             "unit": "KG", "unit_price": Decimal("15.00"), "tax_rate": TaxRate.STANDARD},
        ],
        notes="Erste Bestellung",
    )
    assert po.id is not None
    assert po.po_number.startswith("EK-")
    assert po.status == PurchaseOrderStatus.ENTWURF
    assert po.supplier_id == supplier.id
    assert len(po.lines) == 1
    assert po.total_net == Decimal("150.00")
    assert po.total_gross == Decimal("178.50")
    assert po.can_be_modified() is True


def test_po_numbers_are_unique_and_sequential(db, supplier):
    svc = ProcurementService(db)
    line = [{"beschreibung": "X", "quantity": Decimal("1"), "unit": "STK",
             "unit_price": Decimal("1.00"), "tax_rate": TaxRate.STANDARD}]
    po1 = svc.create_purchase_order(supplier_id=supplier.id, lines=line)
    po2 = svc.create_purchase_order(supplier_id=supplier.id, lines=line)
    assert po1.po_number != po2.po_number


def test_receive_goods_partial_sets_status(db, supplier):
    svc = ProcurementService(db)
    po = svc.create_purchase_order(
        supplier_id=supplier.id,
        lines=[{"beschreibung": "Ware", "quantity": Decimal("10"), "unit": "STK",
                "unit_price": Decimal("2.00"), "tax_rate": TaxRate.STANDARD}],
    )
    line = po.lines[0]
    svc.receive_goods(po.id, [{"line_id": line.id, "quantity": Decimal("4")}])
    db.refresh(po)
    db.refresh(line)
    assert line.quantity_received == Decimal("4")
    assert line.quantity_open == Decimal("6")
    assert line.is_fully_received is False
    assert po.status == PurchaseOrderStatus.TEILWEISE_ERHALTEN


def test_receive_goods_full_sets_status(db, supplier):
    svc = ProcurementService(db)
    po = svc.create_purchase_order(
        supplier_id=supplier.id,
        lines=[{"beschreibung": "Ware", "quantity": Decimal("10"), "unit": "STK",
                "unit_price": Decimal("2.00"), "tax_rate": TaxRate.STANDARD}],
    )
    line = po.lines[0]
    svc.receive_goods(po.id, [{"line_id": line.id, "quantity": Decimal("10")}])
    db.refresh(po)
    db.refresh(line)
    assert line.is_fully_received is True
    assert po.status == PurchaseOrderStatus.ERHALTEN


def test_receive_more_than_ordered_is_rejected(db, supplier):
    svc = ProcurementService(db)
    po = svc.create_purchase_order(
        supplier_id=supplier.id,
        lines=[{"beschreibung": "Ware", "quantity": Decimal("5"), "unit": "STK",
                "unit_price": Decimal("2.00"), "tax_rate": TaxRate.STANDARD}],
    )
    line = po.lines[0]
    with pytest.raises(ValueError):
        svc.receive_goods(po.id, [{"line_id": line.id, "quantity": Decimal("6")}])


# ---------- API-Ebene (Router + Serialisierung + Marge) ----------
# Umgeht das projektweit kaputte tenant-geroutete Client-Setup, indem die
# DB-Dependency (_tenant_db) und Auth (get_current_user) direkt überschrieben
# werden und dieselbe In-Memory-Session wie das db-Fixture genutzt wird.

@pytest.fixture
def api_client(db):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.deps import _tenant_db, get_current_user

    app.dependency_overrides[_tenant_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "00000000-0000-0000-0000-000000000001",
        "username": "test", "roles": ["admin"],
    }
    # localhost → Default-Tenant, damit die Tenant-Middleware den Request durchlässt.
    yield TestClient(app, base_url="http://localhost")
    app.dependency_overrides.pop(_tenant_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_api_create_and_receive_flow(api_client, supplier):
    # Anlegen
    resp = api_client.post("/api/v1/procurement/purchase-orders", json={
        "supplier_id": str(supplier.id),
        "lines": [
            {"beschreibung": "Kaffeebohnen", "quantity": "10", "unit": "KG",
             "unit_price": "15.00", "tax_rate": "STANDARD"},
        ],
    })
    assert resp.status_code == 201, resp.text
    po = resp.json()
    assert po["po_number"].startswith("EK-")
    assert po["status"] == "ENTWURF"
    assert po["supplier_name"] == "Großhandel Müller GmbH"
    assert po["total_gross"] == "178.50"
    line_id = po["lines"][0]["id"]

    # Teil-Wareneingang
    resp = api_client.post(f"/api/v1/procurement/purchase-orders/{po['id']}/receive", json={
        "receipts": [{"line_id": line_id, "quantity": "4"}],
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "TEILWEISE_ERHALTEN"
    assert resp.json()["lines"][0]["quantity_open"] == "6.000"

    # Übermenge wird abgelehnt
    resp = api_client.post(f"/api/v1/procurement/purchase-orders/{po['id']}/receive", json={
        "receipts": [{"line_id": line_id, "quantity": "999"}],
    })
    assert resp.status_code == 400


def test_api_create_unknown_supplier_404(api_client):
    resp = api_client.post("/api/v1/procurement/purchase-orders", json={
        "supplier_id": "00000000-0000-0000-0000-0000000000ff",
        "lines": [],
    })
    assert resp.status_code == 404
