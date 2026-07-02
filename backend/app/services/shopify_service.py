"""
Shopify — Self-Service-Connector.

Kunden mit eigenem Shopify-Shop hinterlegen ihre **Shop-Domain** und einen
**Admin-API-Access-Token** (aus einer eigenen Custom-App im Shopify-Admin).
Der Connector nutzt diese, um die Verbindung zu prüfen und eingegangene
Online-Bestellungen ins ERP zu holen. Keine geteilten Credentials — jede
Firma verbindet ihren eigenen Shop.

API-Referenz: https://shopify.dev/docs/api/admin-rest
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

import httpx

API_VERSION = "2024-01"


class ShopifyError(Exception):
    """Fehler bei der Shopify-Kommunikation (inkl. ungültiger Token/Domain)."""


def normalize_shop_domain(domain: str) -> str:
    """Akzeptiert 'shop', 'shop.myshopify.com' oder eine volle URL und liefert
    die kanonische '<shop>.myshopify.com'-Form."""
    if not domain or not domain.strip():
        raise ShopifyError("Keine Shop-Domain angegeben")
    d = domain.strip().lower()
    d = d.replace("https://", "").replace("http://", "").rstrip("/")
    d = d.split("/")[0]
    if not d.endswith(".myshopify.com"):
        d = d.split(".")[0] + ".myshopify.com"
    return d


class ShopifyConnector:
    def __init__(self, shop_domain: str, access_token: str, *,
                 base_url: str | None = None, client: Optional[httpx.Client] = None):
        if not access_token or not access_token.strip():
            raise ShopifyError("Kein Shopify-Access-Token hinterlegt")
        self.shop_domain = normalize_shop_domain(shop_domain)
        self.access_token = access_token.strip()
        self.base_url = base_url or f"https://{self.shop_domain}"
        self._client = client

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._client is not None:
            return self._client.request(method, path, headers=headers, **kwargs)
        with httpx.Client(base_url=self.base_url, timeout=20) as client:
            return client.request(method, path, headers=headers, **kwargs)

    def test_connection(self) -> dict:
        """GET /shop.json — prüft Token/Domain und liefert den Shop-Namen."""
        try:
            resp = self._request("GET", f"/admin/api/{API_VERSION}/shop.json")
        except httpx.HTTPError as e:
            raise ShopifyError(f"Verbindung fehlgeschlagen: {e}") from e
        if resp.status_code in (401, 403):
            raise ShopifyError("Ungültiger Access-Token")
        if resp.status_code == 404:
            raise ShopifyError("Shop nicht gefunden — Domain prüfen")
        if resp.status_code >= 400:
            raise ShopifyError(f"Shopify-Fehler {resp.status_code}")
        shop = resp.json().get("shop", {})
        return {
            "ok": True,
            "shop_name": shop.get("name"),
            "domain": shop.get("myshopify_domain") or self.shop_domain,
            "currency": shop.get("currency"),
        }

    def list_recent_orders(self, *, limit: int = 20, status: str = "any") -> list[dict]:
        """GET /orders.json — jüngste Bestellungen (schlanke Vorschau)."""
        orders = self.fetch_orders(limit=limit, status=status)
        return [_summarize_order(o) for o in orders]

    def fetch_orders(self, *, limit: int = 20, status: str = "any") -> list[dict]:
        """GET /orders.json — volle Bestell-Objekte (für Import)."""
        try:
            resp = self._request(
                "GET", f"/admin/api/{API_VERSION}/orders.json",
                params={"limit": limit, "status": status},
            )
        except httpx.HTTPError as e:
            raise ShopifyError(f"Abruf fehlgeschlagen: {e}") from e
        if resp.status_code in (401, 403):
            raise ShopifyError("Ungültiger Access-Token")
        if resp.status_code >= 400:
            raise ShopifyError(f"Shopify-Fehler {resp.status_code}")
        return resp.json().get("orders", [])

    def create_product(self, payload: dict) -> dict:
        """POST /products.json — Produkt im Shop anlegen/aktualisieren."""
        try:
            resp = self._request("POST", f"/admin/api/{API_VERSION}/products.json", json={"product": payload})
        except httpx.HTTPError as e:
            raise ShopifyError(f"Produkt-Push fehlgeschlagen: {e}") from e
        if resp.status_code in (401, 403):
            raise ShopifyError("Ungültiger Access-Token")
        if resp.status_code >= 400:
            raise ShopifyError(f"Shopify-Fehler {resp.status_code}: {resp.text[:200]}")
        return resp.json().get("product", {})


def _summarize_order(o: dict) -> dict:
    """Shopify-Bestellung → schlanke Vorschau (kein voller ERP-Import)."""
    customer = o.get("customer") or {}
    name = " ".join(filter(None, [customer.get("first_name"), customer.get("last_name")])) or o.get("email")
    return {
        "shopify_id": o.get("id"),
        "order_number": o.get("name"),
        "created_at": o.get("created_at"),
        "customer": name,
        "total": o.get("total_price"),
        "currency": o.get("currency"),
        "financial_status": o.get("financial_status"),
        "fulfillment_status": o.get("fulfillment_status"),
    }


# ---------- Import: Shopify-Bestellung → ERP-Kunde + Order ----------

def _next_customer_number(db) -> str:
    from sqlalchemy import select
    from app.models.customer import Customer
    last = db.execute(
        select(Customer.customer_number)
        .where(Customer.customer_number.like("KD-%"))
        .order_by(Customer.customer_number.desc()).limit(1)
    ).scalar_one_or_none()
    try:
        n = int(last.split("-")[-1]) if last else 10000
    except (ValueError, AttributeError):
        n = 10000
    return f"KD-{n + 1:05d}"


def _next_order_number(db) -> str:
    from sqlalchemy import select
    from app.models.order import Order
    prefix = f"BE-{date.today().strftime('%Y%m%d')}"
    last = db.execute(
        select(Order.order_number)
        .where(Order.order_number.like(f"{prefix}-%"))
        .order_by(Order.order_number.desc()).limit(1)
    ).scalar_one_or_none()
    try:
        n = int(last.split("-")[-1]) if last else 0
    except (ValueError, AttributeError):
        n = 0
    return f"{prefix}-{n + 1:04d}"


def import_shopify_order(db, order_json: dict) -> dict:
    """Eine Shopify-Bestellung ins ERP übernehmen: Kunde finden/anlegen +
    Order (Status ENTWURF). Idempotent über Order.customer_reference."""
    from sqlalchemy import select
    from app.models.customer import Customer, CustomerType
    from app.models.order import Order, OrderLine, OrderStatus
    from app.models.product import Product
    from app.models.enums import TaxRate

    ref = order_json.get("name") or (f"#{order_json.get('id')}" if order_json.get("id") else None)
    if ref is None:
        raise ValueError("Shopify-Bestellung ohne Nummer/ID")

    existing = db.execute(select(Order).where(Order.customer_reference == ref)).scalar_one_or_none()
    if existing:
        return {"status": "already_imported", "order_id": str(existing.id),
                "order_number": existing.order_number}

    cust = order_json.get("customer") or {}
    email = cust.get("email") or order_json.get("email")
    customer = None
    if email:
        customer = db.execute(select(Customer).where(Customer.email == email)).scalar_one_or_none()
    if customer is None:
        name = " ".join(filter(None, [cust.get("first_name"), cust.get("last_name")])) or email or "Shopify-Kunde"
        customer = Customer(name=name, typ=CustomerType.PRIVAT, email=email,
                            customer_number=_next_customer_number(db))
        db.add(customer)
        db.flush()

    order = Order(
        order_number=_next_order_number(db),
        customer_id=customer.id,
        customer_reference=ref,
        requested_delivery_date=date.today() + timedelta(days=3),
        status=OrderStatus.ENTWURF,
        currency=order_json.get("currency", "EUR"),
    )
    db.add(order)
    db.flush()

    for idx, li in enumerate(order_json.get("line_items", []), start=1):
        product = None
        if li.get("sku"):
            product = db.execute(select(Product).where(Product.sku == li["sku"])).scalar_one_or_none()
        line = OrderLine(
            order_id=order.id,
            position=idx,
            product_id=product.id if product else None,
            beschreibung=li.get("title") or "Position",
            quantity=Decimal(str(li.get("quantity", 1))),
            unit="STK",
            unit_price=Decimal(str(li.get("price", "0"))),
            discount_percent=Decimal("0"),
            tax_rate=TaxRate.STANDARD,
        )
        line.calculate_line_totals()
        order.lines.append(line)

    order.calculate_totals()
    db.commit()
    db.refresh(order)
    return {"status": "imported", "order_id": str(order.id),
            "order_number": order.order_number, "customer_id": str(customer.id)}


# ---------- Push: ERP-Produkte + Bestand → Shopify ----------

def push_products(db, connector: "ShopifyConnector") -> dict:
    """Verkaufbare Produkte (mit Handelsware-Bestand) als Katalog in den Shop
    pushen. Read-only Bestandssync ist ein Folgeschritt (Inventory-Level-API)."""
    from sqlalchemy import select
    from app.models.product import Product
    from app.models.procurement import TradeGoodsInventory

    rows = db.execute(
        select(Product, TradeGoodsInventory)
        .where(
            Product.is_active.is_(True),
            Product.is_sellable.is_(True),
            Product.id == TradeGoodsInventory.product_id,
            TradeGoodsInventory.is_active.is_(True),
        )
        .order_by(Product.sku)
    ).all()

    pushed = 0
    for product, inv in rows:
        payload = {
            "title": product.name,
            "status": "active",
            "variants": [{
                "sku": product.sku,
                "price": str(product.base_price) if product.base_price is not None else "0",
                "inventory_quantity": int(inv.quantity_on_hand or 0),
            }],
        }
        connector.create_product(payload)
        pushed += 1
    return {"pushed": pushed}
