"""
Shopify Self-Service-Connector Tests (httpx.MockTransport).
"""
import httpx
import pytest

from app.services.shopify_service import (
    ShopifyConnector,
    ShopifyError,
    normalize_shop_domain,
)


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
