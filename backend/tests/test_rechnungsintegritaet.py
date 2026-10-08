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
