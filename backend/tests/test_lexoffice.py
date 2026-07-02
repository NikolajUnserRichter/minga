"""
Lexware Office (lexoffice) Self-Service-Connector Tests.

Nutzt httpx.MockTransport statt echter API — verifiziert Auth-Header,
Endpunkte, Fehlerbehandlung (401) und das Rechnungs-Mapping.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from app.services.lexoffice_service import (
    LexofficeConnector,
    LexofficeError,
    invoice_to_lexoffice,
    pull_payment_status,
    sync_invoice,
)


class _FakeConnector:
    def __init__(self):
        self.calls = 0

    def create_invoice(self, payload, finalize=False):
        self.calls += 1
        return {"id": "lex-999"}


class _FakeDB:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def _fake_invoice(**overrides):
    line = SimpleNamespace(position=1, description="Ware", sku="X",
                           quantity=Decimal("1"), unit="STK",
                           unit_price=Decimal("10.00"),
                           tax_rate=SimpleNamespace(value="STANDARD"))
    inv = SimpleNamespace(invoice_date=date(2026, 7, 1), currency="EUR",
                          header_text="", footer_text="", lines=[line],
                          lexoffice_id=None, lexoffice_synced_at=None)
    for k, v in overrides.items():
        setattr(inv, k, v)
    return inv


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.lexoffice.io")


def test_missing_key_raises():
    with pytest.raises(LexofficeError):
        LexofficeConnector("")


def test_test_connection_success():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("Authorization")
        captured["path"] = request.url.path
        return httpx.Response(200, json={"organizationId": "org-1", "companyName": "Muster GmbH"})

    conn = LexofficeConnector("KEY123", client=_client(handler))
    result = conn.test_connection()
    assert result["ok"] is True
    assert result["company_name"] == "Muster GmbH"
    assert result["organization_id"] == "org-1"
    assert captured["auth"] == "Bearer KEY123"
    assert captured["path"] == "/v1/profile"


def test_test_connection_invalid_key():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "unauthorized"})

    conn = LexofficeConnector("BAD", client=_client(handler))
    with pytest.raises(LexofficeError, match="Ungültiger API-Key"):
        conn.test_connection()


def test_create_invoice_posts_payload_and_returns_id():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["finalize"] = request.url.params.get("finalize")
        import json
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "inv-42", "resourceUri": "https://api.lexoffice.io/v1/invoices/inv-42"})

    conn = LexofficeConnector("KEY", client=_client(handler))
    out = conn.create_invoice({"lineItems": []}, finalize=False)
    assert out["id"] == "inv-42"
    assert captured["path"] == "/v1/invoices"
    assert captured["finalize"] == "false"


def test_invoice_mapping():
    line = SimpleNamespace(
        position=1, description="Kaffeebohnen", sku="KAF-1",
        quantity=Decimal("10"), unit="KG", unit_price=Decimal("15.00"),
        tax_rate=SimpleNamespace(value="STANDARD"),
    )
    invoice = SimpleNamespace(
        invoice_date=date(2026, 7, 1), currency="EUR",
        header_text="Danke", footer_text="Zahlbar in 14 Tagen",
        lines=[line],
    )
    payload = invoice_to_lexoffice(invoice, customer_name="Café Central")
    assert payload["voucherDate"] == "2026-07-01"
    assert payload["address"]["name"] == "Café Central"
    assert payload["taxConditions"] == {"taxType": "net"}
    item = payload["lineItems"][0]
    assert item["name"] == "Kaffeebohnen"
    assert item["quantity"] == 10.0
    assert item["unitPrice"]["netAmount"] == 15.0
    assert item["unitPrice"]["taxRatePercentage"] == 19


def test_sync_invoice_stamps_status():
    db, conn, inv = _FakeDB(), _FakeConnector(), _fake_invoice()
    result = sync_invoice(db, inv, conn, customer_name="Café Central")
    assert result["status"] == "created"
    assert inv.lexoffice_id == "lex-999"
    assert inv.lexoffice_synced_at is not None
    assert conn.calls == 1
    assert db.commits == 1


def test_sync_invoice_idempotent_skips():
    db, conn = _FakeDB(), _FakeConnector()
    inv = _fake_invoice(lexoffice_id="already-there")
    result = sync_invoice(db, inv, conn, customer_name="X")
    assert result["status"] == "already_synced"
    assert conn.calls == 0  # kein erneuter API-Call
    assert db.commits == 0


def test_sync_invoice_force_resyncs():
    db, conn = _FakeDB(), _FakeConnector()
    inv = _fake_invoice(lexoffice_id="old")
    result = sync_invoice(db, inv, conn, customer_name="X", force=True)
    assert result["status"] == "created"
    assert inv.lexoffice_id == "lex-999"
    assert conn.calls == 1


# ---------- Zahlungsstatus zurückholen ----------

def test_get_invoice_status():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/invoices/inv-1"
        return httpx.Response(200, json={"voucherStatus": "paid"})

    conn = LexofficeConnector("KEY", client=_client(handler))
    assert conn.get_invoice_status("inv-1") == "paid"


def test_pull_payment_status_marks_paid():
    from decimal import Decimal
    from app.models.invoice import InvoiceStatus

    class Conn:
        def get_invoice_status(self, _id):
            return "paid"

    db = _FakeDB()
    inv = SimpleNamespace(lexoffice_id="inv-1", status=InvoiceStatus.OFFEN,
                          total=Decimal("100.00"), paid_amount=Decimal("0"))
    result = pull_payment_status(db, inv, Conn())
    assert result["updated"] is True
    assert inv.status == InvoiceStatus.BEZAHLT
    assert inv.paid_amount == Decimal("100.00")
    assert db.commits == 1


def test_pull_payment_status_open_no_change():
    from decimal import Decimal
    from app.models.invoice import InvoiceStatus

    class Conn:
        def get_invoice_status(self, _id):
            return "open"

    db = _FakeDB()
    inv = SimpleNamespace(lexoffice_id="inv-1", status=InvoiceStatus.OFFEN,
                          total=Decimal("100.00"), paid_amount=Decimal("0"))
    result = pull_payment_status(db, inv, Conn())
    assert result["updated"] is False
    assert inv.status == InvoiceStatus.OFFEN
