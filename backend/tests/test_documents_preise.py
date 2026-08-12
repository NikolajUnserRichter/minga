"""
Tests: Rabatt-Ausweis auf Rechnung + Preise auf Lieferschein (per Kunde).

- Rechnung: hinterlegter Rabatt (z.B. 3,8 %) muss als eigene Zeile
  (Zwischensumme / Rabatt / Netto) auf dem PDF erscheinen (§ 14 Abs. 4
  Nr. 7 UStG — vereinbarte Entgeltminderung).
- Lieferschein: Preisspalten nur, wenn Customer.show_prices_on_delivery_note
  gesetzt ist; Default bleibt der preisfreie Lieferschein.
"""
import base64
import zlib
from datetime import date

import pytest


def _pdf_text(pdf_bytes: bytes) -> bytes:
    """Extrahiert Text grob aus PDF.

    ReportLab kodiert Content-Streams als ASCII85+Flate — beide Stufen
    dekodieren, damit Text-Assertions möglich sind.
    """
    out = [pdf_bytes]
    pos = 0
    while True:
        start = pdf_bytes.find(b"stream", pos)
        if start == -1:
            break
        start = pdf_bytes.find(b"\n", start) + 1
        end = pdf_bytes.find(b"endstream", start)
        if end == -1:
            break
        seg = pdf_bytes[start:end].strip()
        for decoder in (
            lambda d: zlib.decompress(d),
            lambda d: zlib.decompress(base64.a85decode(d, adobe=True)),
        ):
            try:
                out.append(decoder(seg))
                break
            except Exception:
                continue
        pos = end + 1
    return b"\n".join(out)


@pytest.fixture()
def customer_mit_rabatt(client):
    r = client.post("/api/v1/sales/customers", json={
        "name": "Fruchthof Test",
        "typ": "HANDEL",
        "discount_percent": 3.8,
    })
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def customer_mit_ls_preisen(client):
    r = client.post("/api/v1/sales/customers", json={
        "name": "Gastro mit Preisen",
        "typ": "GASTRO",
        "show_prices_on_delivery_note": True,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _create_order(client, customer_id: str) -> str:
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": customer_id,
        "requested_delivery_date": date.today().isoformat(),
        "lines": [{
            "product_name": "Erbsen-Schale",
            "quantity": 10,
            "unit": "STK",
            "unit_price": 2.50,
            "tax_rate": "REDUZIERT",
        }],
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


class TestRechnungRabatt:
    def test_rabatt_erscheint_auf_rechnung(self, client, customer_mit_rabatt):
        inv = client.post("/api/v1/invoices", json={
            "customer_id": customer_mit_rabatt["id"],
            "invoice_date": date.today().isoformat(),
            "discount_percent": 3.8,
        })
        assert inv.status_code == 201, inv.text
        invoice_id = inv.json()["id"]

        line = client.post(f"/api/v1/invoices/{invoice_id}/lines", json={
            "description": "Erbsen-Schale",
            "quantity": 10,
            "unit": "STK",
            "unit_price": 2.50,
            "tax_rate": "REDUZIERT",
        })
        assert line.status_code == 201, line.text

        pdf = client.get(f"/api/v1/invoices/{invoice_id}/pdf")
        assert pdf.status_code == 200, pdf.text
        text = _pdf_text(pdf.content)
        assert b"Zwischensumme" in text
        assert b"Rabatt" in text
        assert b"3.8" in text

    def test_ohne_rabatt_keine_rabattzeile(self, client):
        # Kunde OHNE Jahresrabatt (Kundenrabatt würde sonst automatisch greifen)
        r = client.post("/api/v1/sales/customers", json={
            "name": "Kunde ohne Rabatt",
            "typ": "HANDEL",
        })
        assert r.status_code == 201
        inv = client.post("/api/v1/invoices", json={
            "customer_id": r.json()["id"],
            "invoice_date": date.today().isoformat(),
        })
        assert inv.status_code == 201, inv.text
        invoice_id = inv.json()["id"]
        client.post(f"/api/v1/invoices/{invoice_id}/lines", json={
            "description": "Erbsen-Schale",
            "quantity": 1,
            "unit": "STK",
            "unit_price": 2.50,
            "tax_rate": "REDUZIERT",
        })
        pdf = client.get(f"/api/v1/invoices/{invoice_id}/pdf")
        assert pdf.status_code == 200
        text = _pdf_text(pdf.content)
        assert b"Zwischensumme" not in text


class TestLieferscheinPreise:
    def test_preise_wenn_kunde_flag_gesetzt(self, client, customer_mit_ls_preisen):
        order_id = _create_order(client, customer_mit_ls_preisen["id"])
        ls = client.post(f"/api/v1/sales/orders/{order_id}/delivery-notes", json={})
        assert ls.status_code == 201, ls.text
        pdf = client.get(f"/api/v1/sales/delivery-notes/{ls.json()['id']}/pdf")
        assert pdf.status_code == 200, pdf.text
        text = _pdf_text(pdf.content)
        assert b"Einzelpreis" in text
        assert b"Zwischensumme" in text
        assert b"Endbetrag" in text
        assert b"2.50" in text

    def test_keine_preise_ohne_flag(self, client):
        r = client.post("/api/v1/sales/customers", json={
            "name": "Gastro ohne Preise",
            "typ": "GASTRO",
        })
        assert r.status_code == 201
        order_id = _create_order(client, r.json()["id"])
        ls = client.post(f"/api/v1/sales/orders/{order_id}/delivery-notes", json={})
        assert ls.status_code == 201, ls.text
        pdf = client.get(f"/api/v1/sales/delivery-notes/{ls.json()['id']}/pdf")
        assert pdf.status_code == 200
        text = _pdf_text(pdf.content)
        assert b"Einzelpreis" not in text
        assert b"Charge" in text
