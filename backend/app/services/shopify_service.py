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
        orders = resp.json().get("orders", [])
        return [_summarize_order(o) for o in orders]


def _summarize_order(o: dict) -> dict:
    """Shopify-Bestellung → schlanke Vorschau (kein voller ERP-Import)."""
    customer = o.get("customer") or {}
    name = " ".join(filter(None, [customer.get("first_name"), customer.get("last_name")])) or o.get("email")
    return {
        "order_number": o.get("name"),
        "created_at": o.get("created_at"),
        "customer": name,
        "total": o.get("total_price"),
        "currency": o.get("currency"),
        "financial_status": o.get("financial_status"),
        "fulfillment_status": o.get("fulfillment_status"),
    }
