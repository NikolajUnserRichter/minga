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
)


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
