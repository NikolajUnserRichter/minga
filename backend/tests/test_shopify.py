"""
Shopify Self-Service-Connector Tests (httpx.MockTransport).
"""
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.services.shopify_service import (
    ShopifyConnector,
    ShopifyError,
    import_shopify_order,
    normalize_shop_domain,
    push_products,
)


engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    s = TestingSessionLocal()
    yield s
    s.close()
    Base.metadata.drop_all(bind=engine)


def _shopify_order():
    return {
        "id": 12345, "name": "#1001", "currency": "EUR",
        "customer": {"first_name": "Max", "last_name": "Müller", "email": "max@example.com"},
        "line_items": [
            {"title": "Kaffee 1kg", "sku": "KAF-1", "quantity": 2, "price": "15.00"},
            {"title": "Tasse", "sku": None, "quantity": 1, "price": "9.00"},
        ],
    }


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://x.myshopify.com")


def test_normalize_shop_domain():
    assert normalize_shop_domain("meinshop") == "meinshop.myshopify.com"
    assert normalize_shop_domain("meinshop.myshopify.com") == "meinshop.myshopify.com"
    assert normalize_shop_domain("https://meinshop.myshopify.com/") == "meinshop.myshopify.com"


def test_missing_token_raises():
    with pytest.raises(ShopifyError):
        ShopifyConnector("shop", "")


def test_test_connection_success():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["token"] = request.headers.get("X-Shopify-Access-Token")
        captured["path"] = request.url.path
        return httpx.Response(200, json={"shop": {"name": "Mein Shop", "myshopify_domain": "meinshop.myshopify.com", "currency": "EUR"}})

    conn = ShopifyConnector("meinshop", "tok-123", client=_client(handler))
    result = conn.test_connection()
    assert result["ok"] is True
    assert result["shop_name"] == "Mein Shop"
    assert result["currency"] == "EUR"
    assert captured["token"] == "tok-123"
    assert captured["path"] == "/admin/api/2024-01/shop.json"


def test_test_connection_invalid_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"errors": "Unauthorized"})

    conn = ShopifyConnector("shop", "bad", client=_client(handler))
    with pytest.raises(ShopifyError, match="Ungültiger Access-Token"):
        conn.test_connection()


def test_list_recent_orders_summarizes():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/admin/api/2024-01/orders.json"
        return httpx.Response(200, json={"orders": [
            {"name": "#1001", "created_at": "2026-07-01T10:00:00Z",
             "customer": {"first_name": "Max", "last_name": "Müller"},
             "total_price": "49.90", "currency": "EUR",
             "financial_status": "paid", "fulfillment_status": None},
        ]})

    conn = ShopifyConnector("shop", "tok", client=_client(handler))
    orders = conn.list_recent_orders()
    assert len(orders) == 1
    assert orders[0]["order_number"] == "#1001"
    assert orders[0]["customer"] == "Max Müller"
    assert orders[0]["total"] == "49.90"


# ---------- Import: Shop → ERP ----------

def test_import_creates_customer_and_order(db):
    result = import_shopify_order(db, _shopify_order())
    assert result["status"] == "imported"
    assert result["order_number"].startswith("BE-")

    from app.models.customer import Customer
    from app.models.order import Order
    cust = db.query(Customer).filter_by(email="max@example.com").one()
    assert cust.name == "Max Müller"
    assert cust.customer_number.startswith("KD-")
    order = db.query(Order).filter_by(customer_reference="#1001").one()
    assert order.customer_id == cust.id
    assert len(order.lines) == 2
    # 2*15 + 1*9 = 39 netto
    assert order.total_net == Decimal("39.00")


def test_import_is_idempotent(db):
    import_shopify_order(db, _shopify_order())
    result = import_shopify_order(db, _shopify_order())
    assert result["status"] == "already_imported"
    from app.models.order import Order
    assert db.query(Order).count() == 1


def test_import_reuses_existing_customer_by_email(db):
    from app.models.customer import Customer, CustomerType
    existing = Customer(name="Bestandskunde", typ=CustomerType.GEWERBE, email="max@example.com")
    db.add(existing); db.commit()
    import_shopify_order(db, _shopify_order())
    assert db.query(Customer).filter_by(email="max@example.com").count() == 1


# ---------- Push: ERP → Shop ----------

def test_push_products_posts_sellable_with_stock(db):
    from app.models.unit import UnitOfMeasure, UnitCategory
    from app.models.product import Product, ProductCategory
    from app.models.procurement import TradeGoodsInventory

    unit = UnitOfMeasure(code="STK", name="Stück", category=UnitCategory.COUNT)
    db.add(unit); db.flush()
    p = Product(sku="KAF-1", name="Kaffee", category=ProductCategory.PACKAGING,
                base_unit_id=unit.id, base_price=Decimal("25.00"), is_active=True, is_sellable=True)
    db.add(p); db.flush()
    db.add(TradeGoodsInventory(product_id=p.id, sku="KAF-1", name="Kaffee",
                              quantity_on_hand=Decimal("7"), unit="STK", is_active=True))
    db.commit()

    posted = []

    class FakeConn:
        def create_product(self, payload):
            posted.append(payload)
            return {"id": 1}

    result = push_products(db, FakeConn())
    assert result["pushed"] == 1
    assert posted[0]["variants"][0]["sku"] == "KAF-1"
    assert posted[0]["variants"][0]["price"] == "25.00"
    assert posted[0]["variants"][0]["inventory_quantity"] == 7
