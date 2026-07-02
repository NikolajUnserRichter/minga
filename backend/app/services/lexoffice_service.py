"""
Lexware Office (lexoffice) — Self-Service-Connector.

Kunden hinterlegen ihren **eigenen** lexoffice-API-Key (Einstellungen →
Integrationen). Der Connector nutzt diesen Key, um die Verbindung zu testen
und Rechnungen in das lexoffice-Konto des Kunden zu übertragen. Es werden
keine zentralen/geteilten Credentials verwendet — jede Firma verbindet ihr
eigenes Konto.

API-Referenz: https://developers.lexoffice.io  (Basis https://api.lexoffice.io)
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

import httpx

BASE_URL = "https://api.lexoffice.io"

# interne Steuersätze → lexoffice-Prozentwert
_TAX_PERCENT = {"STANDARD": 19, "REDUZIERT": 7, "STEUERFREI": 0}


class LexofficeError(Exception):
    """Fehler bei der lexoffice-Kommunikation (inkl. ungültiger Key)."""


def _tax_percent(tax_rate: Any) -> int:
    key = getattr(tax_rate, "value", tax_rate)
    return _TAX_PERCENT.get(str(key), 19)


def invoice_to_lexoffice(invoice: Any, *, customer_name: str) -> dict:
    """Interne Rechnung → lexoffice-Invoice-Payload (net, nicht finalisiert)."""
    line_items = []
    for line in sorted(invoice.lines, key=lambda l: getattr(l, "position", 0)):
        line_items.append({
            "type": "custom",
            "name": line.description or line.sku or "Position",
            "quantity": float(line.quantity),
            "unitName": line.unit or "Stück",
            "unitPrice": {
                "currency": invoice.currency or "EUR",
                "netAmount": float(line.unit_price),
                "taxRatePercentage": _tax_percent(line.tax_rate),
            },
        })

    return {
        "voucherDate": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "address": {"name": customer_name},
        "lineItems": line_items,
        "totalPrice": {"currency": invoice.currency or "EUR"},
        "taxConditions": {"taxType": "net"},
        "title": "Rechnung",
        "introduction": invoice.header_text or "",
        "remark": invoice.footer_text or "",
    }


class LexofficeConnector:
    def __init__(self, api_key: str, *, base_url: str | None = None, client: Optional[httpx.Client] = None):
        if not api_key or not api_key.strip():
            raise LexofficeError("Kein lexoffice-API-Key hinterlegt")
        self.api_key = api_key.strip()
        self.base_url = base_url or BASE_URL
        self._client = client

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._client is not None:
            return self._client.request(method, path, headers=headers, **kwargs)
        with httpx.Client(base_url=self.base_url, timeout=20) as client:
            return client.request(method, path, headers=headers, **kwargs)

    def test_connection(self) -> dict:
        """GET /v1/profile — prüft Key und liefert Firmennamen."""
        try:
            resp = self._request("GET", "/v1/profile")
        except httpx.HTTPError as e:
            raise LexofficeError(f"Verbindung fehlgeschlagen: {e}") from e
        if resp.status_code == 401:
            raise LexofficeError("Ungültiger API-Key")
        if resp.status_code >= 400:
            raise LexofficeError(f"lexoffice-Fehler {resp.status_code}")
        data = resp.json()
        return {
            "ok": True,
            "company_name": data.get("companyName"),
            "organization_id": data.get("organizationId"),
        }

    def create_invoice(self, payload: dict, *, finalize: bool = False) -> dict:
        """POST /v1/invoices — legt eine Rechnung im lexoffice-Konto an."""
        try:
            resp = self._request(
                "POST", "/v1/invoices",
                params={"finalize": str(finalize).lower()},
                json=payload,
            )
        except httpx.HTTPError as e:
            raise LexofficeError(f"Übertragung fehlgeschlagen: {e}") from e
        if resp.status_code == 401:
            raise LexofficeError("Ungültiger API-Key")
        if resp.status_code >= 400:
            raise LexofficeError(f"lexoffice-Fehler {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return {"id": data.get("id"), "resource_uri": data.get("resourceUri")}

    def get_invoice_status(self, lexoffice_id: str) -> str:
        """GET /v1/invoices/{id} — voucherStatus (draft/open/paid/voided)."""
        try:
            resp = self._request("GET", f"/v1/invoices/{lexoffice_id}")
        except httpx.HTTPError as e:
            raise LexofficeError(f"Statusabruf fehlgeschlagen: {e}") from e
        if resp.status_code == 401:
            raise LexofficeError("Ungültiger API-Key")
        if resp.status_code == 404:
            raise LexofficeError("Rechnung in lexoffice nicht gefunden")
        if resp.status_code >= 400:
            raise LexofficeError(f"lexoffice-Fehler {resp.status_code}")
        return resp.json().get("voucherStatus", "unknown")


def sync_invoice(db, invoice, connector, *, customer_name: str, force: bool = False) -> dict:
    """Rechnung nach lexoffice übertragen und den Status auf der Rechnung
    stempeln. Idempotent: bereits übertragene Rechnungen werden ohne erneuten
    API-Call übersprungen (außer ``force=True``)."""
    if getattr(invoice, "lexoffice_id", None) and not force:
        return {
            "status": "already_synced",
            "lexoffice_id": invoice.lexoffice_id,
            "synced_at": invoice.lexoffice_synced_at,
        }

    payload = invoice_to_lexoffice(invoice, customer_name=customer_name)
    result = connector.create_invoice(payload, finalize=False)

    invoice.lexoffice_id = result["id"]
    invoice.lexoffice_synced_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "created", "lexoffice_id": result["id"], "synced_at": invoice.lexoffice_synced_at}


def pull_payment_status(db, invoice, connector) -> dict:
    """Zahlungsstatus einer übertragenen Rechnung aus lexoffice zurückholen.
    Bei ``paid`` wird die ERP-Rechnung auf BEZAHLT gesetzt (paid_amount=total)."""
    if not getattr(invoice, "lexoffice_id", None):
        raise LexofficeError("Rechnung wurde nicht nach lexoffice übertragen")

    status = connector.get_invoice_status(invoice.lexoffice_id)
    from app.models.invoice import InvoiceStatus

    updated = False
    if status == "paid" and invoice.status != InvoiceStatus.BEZAHLT:
        invoice.status = InvoiceStatus.BEZAHLT
        invoice.paid_amount = invoice.total
        updated = True
        db.commit()
    return {"lexoffice_status": status, "erp_status": invoice.status.value, "updated": updated}
