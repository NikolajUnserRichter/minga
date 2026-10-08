import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus
from tests.conftest import TestingSessionLocal
from tests.test_gernot_261008_paket2 import _bestellung, _kunde
from tests.test_gernot_261008 import _s6_lieferschein, _s6_lauf, S6_PREVIEW, S6_COMMIT


@pytest.fixture(autouse=True)
def ohne_externe_dienste(monkeypatch):
    monkeypatch.setattr("app.api.v1.sales._trigger_forecast_update", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.api.v1.invoices.send_email", lambda **kwargs: None)
    monkeypatch.setattr("app.services.pdf_service.PDFService.generate_invoice_pdf",
                        lambda *args, **kwargs: b"PDF")


def _altrechnung(order, nummer, status):
    with TestingSessionLocal() as db:
        invoice = Invoice(
            customer_id=uuid.UUID(order["customer_id"]), order_id=uuid.UUID(order["id"]),
            invoice_number=nummer, status=InvoiceStatus(status), due_date=date(2026, 10, 31),
        )
        invoice.lines = [InvoiceLine(
            position=1, description="Erbsen-Schale", quantity=Decimal("2"),
            unit="STK", unit_price=Decimal("3"),
        )]
        db.add(invoice)
        db.flush()
        invoice.calculate_totals()
        db.commit()
        return {"id": str(invoice.id), "invoice_number": invoice.invoice_number}


def _festschreiben(client, invoice, weg):
    url = f"/api/v1/invoices/{invoice['id']}"
    if weg == "patch":
        return client.patch(url, json={"status": "OFFEN"})
    if weg == "send":
        return client.post(f"{url}/send", params={"to_email": "test@example.com"})
    return client.post(f"{url}/finalize")


class TestFestschreiben:
    @pytest.mark.parametrize("weg", ["finalize", "send", "patch"])
    @pytest.mark.parametrize("status", ["OFFEN", "BEZAHLT", "TEILBEZAHLT", "UEBERFAELLIG", "MAHNVERFAHREN"])
    def test_altfall_andere_aktive_rechnung_blockiert(self, client, weg, status):
        order = _bestellung(client, _kunde(client))
        _altrechnung(order, "RE-2026-00001", "ENTWURF")
        andere = _altrechnung(order, "RE-2026-00002", status)
        entwurf = _altrechnung(order, "RE-2026-00003", "ENTWURF")
        response = _festschreiben(client, entwurf, weg)
        assert response.status_code == 409, response.text
        assert response.json()["detail"] == (
            f"Zur Bestellung {order['order_number']} gibt es schon die Rechnung "
            f"{andere['invoice_number']} — diesen Entwurf verwerfen oder die andere Rechnung erst stornieren"
        )
        gespeichert = client.get(f"/api/v1/invoices/{entwurf['id']}").json()
        assert gespeichert["status"] == "ENTWURF"
        assert gespeichert["sent_at"] is None

    def test_nach_storno_ist_finalisieren_erlaubt(self, client):
        order = _bestellung(client, _kunde(client))
        andere = _altrechnung(order, "RE-2026-00002", "OFFEN")
        entwurf = _altrechnung(order, "RE-2026-00003", "ENTWURF")
        response = client.post(f"/api/v1/invoices/{andere['id']}/cancel", json={"reason": "Doppelt"})
        assert response.status_code == 200, response.text
        response = _festschreiben(client, entwurf, "finalize")
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "OFFEN"

    @pytest.mark.parametrize("status", ["BEZAHLT", "TEILBEZAHLT", "STORNIERT", "UEBERFAELLIG", "MAHNVERFAHREN"])
    def test_patch_umgeht_keine_zahlung_oder_stornierung(self, client, status):
        order = _bestellung(client, _kunde(client))
        entwurf = _altrechnung(order, "RE-2026-00003", "ENTWURF")
        response = client.patch(f"/api/v1/invoices/{entwurf['id']}", json={"status": status})
        assert response.status_code == 422, response.text

    def test_sammellauf_ueberspringt_altfall(self, client):
        order = _bestellung(client, _kunde(client), liefertag=date(2026, 3, 5))
        _s6_lieferschein(client, order)
        _altrechnung(order, "RE-2026-00002", "OFFEN")
        _altrechnung(order, "RE-2026-00003", "ENTWURF")
        assert _s6_lauf(client, S6_PREVIEW)["kunden"] == []
        assert _s6_lauf(client, S6_COMMIT)["rechnungen"] == []


def _positionsaenderung(client, order, methode):
    url = f"/api/v1/sales/orders/{order['id']}/lines"
    if methode == "post":
        return client.post(url, json={
            "product_name": "Kresse", "quantity": 1, "unit": "STK", "unit_price": 4,
        })
    url += f"/{order['lines'][0]['id']}"
    if methode == "patch":
        return client.patch(url, json={"quantity": 9, "unit_price": 99})
    return client.delete(url)


def _berechnet_hinweis(invoice):
    return (f"Bestellung ist bereits berechnet ({invoice['invoice_number']}) — "
            "erst die Rechnung stornieren bzw. den Entwurf verwerfen")


class TestPositionssperre:
    @pytest.mark.parametrize("methode", ["post", "patch", "delete"])
    @pytest.mark.parametrize("status", ["ENTWURF", "OFFEN", "BEZAHLT", "TEILBEZAHLT", "UEBERFAELLIG", "MAHNVERFAHREN"])
    @pytest.mark.parametrize("bezug", ["bestellung", "lieferschein"])
    def test_berechnete_positionen_unveraenderlich(self, client, methode, status, bezug):
        order = _bestellung(client, _kunde(client))
        invoice = _altrechnung(order, "RE-2026-00002", status)
        if bezug == "lieferschein":
            from app.models.documents import DeliveryNote
            note = _s6_lieferschein(client, order)
            with TestingSessionLocal() as db:
                db.get(Invoice, uuid.UUID(invoice["id"])).order_id = None
                db.get(DeliveryNote, uuid.UUID(note["id"])).invoice_id = uuid.UUID(invoice["id"])
                db.commit()
        response = _positionsaenderung(client, order, methode)
        assert response.status_code == 409, response.text
        assert response.json()["detail"] == _berechnet_hinweis(invoice)
        nachher = client.get(f"/api/v1/sales/orders/{order['id']}").json()
        assert nachher["lines"] == order["lines"]
        assert nachher["total_gross"] == order["total_gross"]

    @pytest.mark.parametrize("status", [None, "ENTWURF", "OFFEN", "STORNIERT"])
    def test_bestellantwort_enthaelt_aktive_rechnungsnummer(self, client, status):
        order = _bestellung(client, _kunde(client))
        if status:
            _altrechnung(order, "RE-2026-00002", status)
        nummer = "RE-2026-00002" if status in ("ENTWURF", "OFFEN") else None
        detail = client.get(f"/api/v1/sales/orders/{order['id']}").json()
        liste = client.get("/api/v1/sales/orders").json()["items"]
        assert "rechnung_nummer" in detail
        assert detail["rechnung_nummer"] == nummer
        assert next(item for item in liste if item["id"] == order["id"])["rechnung_nummer"] == nummer

    def test_kopfdaten_und_lieferdatum_bleiben_editierbar(self, client):
        order = _bestellung(client, _kunde(client))
        _altrechnung(order, "RE-2026-00002", "OFFEN")
        kopf = {"notes": "Neue Notiz", "customer_reference": "PO-42",
                "requested_delivery_date": "2026-10-12"}
        response = client.patch(f"/api/v1/sales/orders/{order['id']}", json=kopf)
        assert response.status_code == 200, response.text
        for feld, wert in kopf.items():
            assert response.json()[feld] == wert

    @pytest.mark.parametrize("methode", ["post", "patch", "delete"])
    def test_nach_storno_wieder_editierbar(self, client, methode):
        order = _bestellung(client, _kunde(client))
        invoice = _altrechnung(order, "RE-2026-00002", "ENTWURF")
        response = client.post(f"/api/v1/invoices/{invoice['id']}/cancel", json={
            "reason": "Verwerfen", "create_credit_note": False,
        })
        assert response.status_code == 200, response.text
        response = _positionsaenderung(client, order, methode)
        assert response.status_code == {"post": 201, "patch": 200, "delete": 204}[methode], response.text


class TestStornierteBestellung:
    def test_rechnung_aus_stornierter_bestellung_abgelehnt(self, client):
        order = _bestellung(client, _kunde(client))
        response = client.post(f"/api/v1/sales/orders/{order['id']}/status", json={
            "status": "STORNIERT", "reason": "Abgesagt",
        })
        assert response.status_code == 200, response.text
        response = client.post(f"/api/v1/invoices/from-order/{order['id']}")
        assert response.status_code == 409, response.text
        assert response.json()["detail"] == "Bestellung ist storniert"
        with TestingSessionLocal() as db:
            assert db.query(Invoice).count() == 0

    def test_sammellauf_schliesst_stornierte_bestellung_aus(self, client):
        kunde = _kunde(client)
        storniert = _bestellung(client, kunde, liefertag=date(2026, 3, 5))
        aktiv = _bestellung(client, kunde, liefertag=date(2026, 3, 6))
        note = _s6_lieferschein(client, storniert)
        _s6_lieferschein(client, aktiv)
        response = client.post(f"/api/v1/sales/orders/{storniert['id']}/status", json={
            "status": "STORNIERT", "reason": "Abgesagt",
        })
        assert response.status_code == 200, response.text
        vorschau = _s6_lauf(client, S6_PREVIEW)["kunden"]
        assert len(vorschau) == 1
        assert vorschau[0]["anzahl_lieferscheine"] == 1
        assert Decimal(vorschau[0]["summe_netto"]) == Decimal("6.00")
        rechnungen = _s6_lauf(client, S6_COMMIT)["rechnungen"]
        assert len(rechnungen) == 1
        assert Decimal(rechnungen[0]["subtotal"]) == Decimal("6.00")
        from app.models.documents import DeliveryNote
        with TestingSessionLocal() as db:
            assert db.get(DeliveryNote, uuid.UUID(note["id"])).invoice_id is None


class TestLoeschsperre:
    @pytest.mark.parametrize("status", ["ENTWURF", "OFFEN", "BEZAHLT", "TEILBEZAHLT", "UEBERFAELLIG", "MAHNVERFAHREN"])
    @pytest.mark.parametrize("bezug", ["bestellung", "lieferschein"])
    def test_bestellung_mit_aktiver_rechnung_nicht_loeschbar(self, client, status, bezug):
        order = _bestellung(client, _kunde(client))
        invoice = _altrechnung(order, "RE-2026-00002", status)
        if bezug == "lieferschein":
            from app.models.documents import DeliveryNote
            note = _s6_lieferschein(client, order)
            with TestingSessionLocal() as db:
                db.get(Invoice, uuid.UUID(invoice["id"])).order_id = None
                db.get(DeliveryNote, uuid.UUID(note["id"])).invoice_id = uuid.UUID(invoice["id"])
                db.commit()
        response = client.delete(f"/api/v1/sales/orders/{order['id']}")
        assert response.status_code == 409, response.text
        assert response.json()["detail"] == _berechnet_hinweis(invoice)
        response = client.get(f"/api/v1/sales/orders/{order['id']}")
        assert response.status_code == 200, response.text
        assert response.json()["lines"] == order["lines"]
        with TestingSessionLocal() as db:
            gespeichert = db.get(Invoice, uuid.UUID(invoice["id"]))
            assert gespeichert.status.value == status
            if bezug == "bestellung":
                assert str(gespeichert.order_id) == order["id"]
            else:
                assert db.get(DeliveryNote, uuid.UUID(note["id"])).invoice_id == gespeichert.id

    @pytest.mark.parametrize("rechnung_status", [None, "STORNIERT"])
    def test_ohne_aktive_rechnung_loeschbar(self, client, rechnung_status):
        order = _bestellung(client, _kunde(client))
        if rechnung_status:
            _altrechnung(order, "RE-2026-00002", rechnung_status)
        response = client.delete(f"/api/v1/sales/orders/{order['id']}")
        assert response.status_code == 204, response.text
        assert client.get(f"/api/v1/sales/orders/{order['id']}").status_code == 404
