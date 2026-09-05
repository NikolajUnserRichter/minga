"""Warenfluss-Release, AP1: Stornorechnung.

Der Storno-Grundpfad existierte (cancel_invoice → Gutschrift mit negativen
Positionen). Gefehlt haben: Grund-Auswahlliste, die Freigabe der Lieferscheine,
die Sperre gegen Storno-eines-Stornos und die Verweise in beiden Richtungen.
"""
from decimal import Decimal

import pytest


@pytest.fixture
def offene_rechnung(client, sample_customer):
    """Rechnung mit einer Position, finalisiert → OFFEN mit Nummer."""
    from datetime import date
    r = client.post("/api/v1/invoices", json={
        "customer_id": sample_customer["id"],
        "invoice_date": date.today().isoformat(),
    })
    assert r.status_code == 201, r.text
    rechnung = r.json()

    r = client.post(f"/api/v1/invoices/{rechnung['id']}/lines", json={
        "description": "Erbsen-Schale", "quantity": 10, "unit": "STK",
        "unit_price": 2.50, "tax_rate": "REDUZIERT",
    })
    assert r.status_code == 201, r.text

    r = client.post(f"/api/v1/invoices/{rechnung['id']}/finalize")
    assert r.status_code == 200, r.text
    return r.json()


def _storniere(client, invoice_id, **extra):
    return client.post(f"/api/v1/invoices/{invoice_id}/cancel", json={
        "reason": "Falsche Menge geliefert",
        "reason_code": "FALSCHE_MENGE",
        **extra,
    })


class TestStorno:
    def test_summe_original_plus_storno_ist_null(self, client, offene_rechnung):
        r = _storniere(client, offene_rechnung["id"])

        assert r.status_code == 200, r.text
        storno = r.json()["credit_note"]
        assert (Decimal(str(offene_rechnung["total"]))
                + Decimal(str(storno["total"]))) == Decimal("0")

    def test_storno_bekommt_naechste_nummer_aus_dem_regulaeren_kreis(self, client, offene_rechnung):
        storno = _storniere(client, offene_rechnung["id"]).json()["credit_note"]

        assert storno["invoice_number"] != offene_rechnung["invoice_number"]
        # gleicher Kreis, gleiches Präfix — keine eigene Storno-Nummernwelt
        assert storno["invoice_number"].split("-")[0] == offene_rechnung["invoice_number"].split("-")[0]

    def test_verweise_in_beide_richtungen(self, client, offene_rechnung):
        storno = _storniere(client, offene_rechnung["id"]).json()["credit_note"]

        original = client.get(f"/api/v1/invoices/{offene_rechnung['id']}").json()
        assert original["status"] == "STORNIERT"
        assert original["cancelled_by_invoice_id"] == storno["id"]
        assert storno["original_invoice_id"] == offene_rechnung["id"]

    def test_original_ist_schreibgeschuetzt(self, client, offene_rechnung):
        _storniere(client, offene_rechnung["id"])

        r = client.patch(f"/api/v1/invoices/{offene_rechnung['id']}",
                         json={"header_text": "nachträglich geändert"})
        assert r.status_code == 400, r.text

    def test_stornogrund_landet_am_storno(self, client, offene_rechnung):
        storno = _storniere(client, offene_rechnung["id"]).json()["credit_note"]
        detail = client.get(f"/api/v1/invoices/{storno['id']}").json()
        assert "Falsche Menge geliefert" in (detail.get("internal_notes") or "")

    def test_doppelstorno_wird_abgelehnt(self, client, offene_rechnung):
        _storniere(client, offene_rechnung["id"])
        r = _storniere(client, offene_rechnung["id"])
        assert r.status_code == 400, r.text

    def test_storno_eines_stornos_wird_abgelehnt(self, client, offene_rechnung):
        storno = _storniere(client, offene_rechnung["id"]).json()["credit_note"]
        r = _storniere(client, storno["id"])
        assert r.status_code == 400, r.text
        assert "Stornorechnung" in r.json()["detail"]

    def test_storno_pdf_kommt(self, client, offene_rechnung):
        storno = _storniere(client, offene_rechnung["id"]).json()["credit_note"]
        r = client.get(f"/api/v1/invoices/{storno['id']}/pdf")
        assert r.status_code == 200, r.text
        assert r.content.startswith(b"%PDF")


class TestLieferscheinFreigabe:
    """R1.6: Lieferscheine der stornierten Rechnung werden wieder abrechenbar."""

    def test_lieferschein_wird_freigegeben(self, client, db, sample_customer, offene_rechnung):
        from datetime import date
        r = client.post("/api/v1/sales/orders", json={
            "customer_id": sample_customer["id"],
            "requested_delivery_date": date.today().isoformat(),
            "lines": [{"product_name": "Erbsen-Schale", "quantity": 10, "unit": "STK",
                       "unit_price": 2.50, "tax_rate": "REDUZIERT"}],
        })
        assert r.status_code == 201, r.text
        note = client.post(f"/api/v1/sales/orders/{r.json()['id']}/delivery-notes", json={})
        assert note.status_code == 201, note.text

        # Zuordnung wie sie der Sammelrechnungslauf setzt
        from app.models.documents import DeliveryNote
        from uuid import UUID
        ls = db.get(DeliveryNote, UUID(note.json()["id"]))
        ls.invoice_id = UUID(offene_rechnung["id"])
        db.commit()

        _storniere(client, offene_rechnung["id"])

        db.expire_all()
        ls = db.get(DeliveryNote, UUID(note.json()["id"]))
        assert ls.invoice_id is None
