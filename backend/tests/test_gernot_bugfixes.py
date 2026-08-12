"""
Regressionstests für das Gernot-Feedback vom 12.08.2026 (Bugs 3, 4, 6, 7, 8).

Bug 3: Erntefenster-Tage zählen ab Aussaat — Keimdauer darf nicht doppelt
       addiert werden (Gartenkresse: Aussaat+7 = optimale Ernte).
Bug 4: Chargen-Liste muss den Sortennamen liefern (kein "Unbekannt").
Bug 6: Status-Sammelfilter OFFEN bei Bestellungen (statt 422).
Bug 7: DATEV-Export über die HTTP-Route (DI war kaputt, Tests umgingen sie).
Bug 8: Verpackungsplan zeigt Lieferungen von morgen (Packtag = Vortag),
       Same-Day-Bestellungen und Entwürfe.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest


@pytest.fixture()
def seed_gartenkresse(client):
    r = client.post("/api/v1/seeds", json={
        "name": "Gartenkresse",
        "keimdauer_tage": 3,
        "wachstumsdauer_tage": 3,
        "erntefenster_min_tage": 6,
        "erntefenster_optimal_tage": 7,
        "erntefenster_max_tage": 8,
        "ertrag_gramm_pro_tray": 300,
        "verlustquote_prozent": 5.0,
    })
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def seed_batch(client, seed_gartenkresse):
    r = client.post("/api/v1/seeds/batches", json={
        "seed_id": seed_gartenkresse["id"],
        "charge_nummer": "GK-001",
        "menge_gramm": 5000,
    })
    assert r.status_code == 201, r.text
    return r.json()


class TestBug3Erntedaten:
    def test_erntefenster_zaehlt_ab_aussaat(self, client, seed_batch):
        aussaat = date(2026, 8, 14)
        r = client.post("/api/v1/production/grow-batches", json={
            "seed_batch_id": seed_batch["id"],
            "tray_anzahl": 2,
            "aussaat_datum": aussaat.isoformat(),
        })
        assert r.status_code == 201, r.text
        b = r.json()
        assert b["erwartete_ernte_min"] == "2026-08-20"      # +6
        assert b["erwartete_ernte_optimal"] == "2026-08-21"  # +7 (nicht 24.08!)
        assert b["erwartete_ernte_max"] == "2026-08-22"      # +8


class TestBug4SeedName:
    def test_liste_liefert_sortenname(self, client, seed_batch):
        client.post("/api/v1/production/grow-batches", json={
            "seed_batch_id": seed_batch["id"],
            "tray_anzahl": 2,
            "aussaat_datum": date.today().isoformat(),
        })
        r = client.get("/api/v1/production/grow-batches")
        assert r.status_code == 200
        batches = r.json()
        assert len(batches) == 1
        assert batches[0]["seed_name"] == "Gartenkresse"


@pytest.fixture()
def customer(client):
    r = client.post("/api/v1/sales/customers", json={"name": "Testkunde", "typ": "GASTRO"})
    assert r.status_code == 201
    return r.json()


def _order(client, customer_id, delivery: date):
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": customer_id,
        "requested_delivery_date": delivery.isoformat(),
        "lines": [{"product_name": "Erbsen-Schale", "quantity": 5, "unit": "STK",
                   "unit_price": 2.5, "tax_rate": "REDUZIERT"}],
    })
    assert r.status_code == 201, r.text
    return r.json()


class TestBug6OffenFilter:
    def test_offen_sammelfilter(self, client, customer):
        _order(client, customer["id"], date.today())
        r = client.get("/api/v1/sales/orders", params={"status": "OFFEN"})
        assert r.status_code == 200, r.text
        assert r.json()["total"] == 1

    def test_ungueltiger_status_gibt_lesbaren_fehler(self, client):
        r = client.get("/api/v1/sales/orders", params={"status": "QUATSCH"})
        assert r.status_code == 422
        assert "Ungültiger Status" in r.json()["detail"]

    def test_enum_status_funktioniert_weiter(self, client, customer):
        _order(client, customer["id"], date.today())
        r = client.get("/api/v1/sales/orders", params={"status": "ENTWURF"})
        assert r.status_code == 200
        assert r.json()["total"] == 1


class TestBug7DatevExport:
    def test_datev_export_route(self, client, customer):
        # Rechnung mit Position, damit der Export etwas findet
        inv = client.post("/api/v1/invoices", json={
            "customer_id": customer["id"],
            "invoice_date": date.today().isoformat(),
        }).json()
        client.post(f"/api/v1/invoices/{inv['id']}/lines", json={
            "description": "Erbsen-Schale", "quantity": 5, "unit": "STK",
            "unit_price": 2.5, "tax_rate": "REDUZIERT",
        })
        r = client.post("/api/v1/invoices/datev-export", json={
            "from_date": (date.today() - timedelta(days=1)).isoformat(),
            "to_date": (date.today() + timedelta(days=1)).isoformat(),
        })
        assert r.status_code == 200, r.text
        assert "csv_content" in r.json()


class TestBug8Verpackungsplan:
    def test_lieferung_morgen_erscheint_heute(self, client, customer):
        _order(client, customer["id"], date.today() + timedelta(days=1))
        r = client.get("/api/v1/production/packaging-plan",
                       params={"target_date": date.today().isoformat()})
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        order_ref = items[0]["orders"][0]
        assert order_ref["customer_name"] == "Testkunde"
        assert order_ref["status"] == "Entwurf"
        assert order_ref["same_day"] is False

    def test_same_day_bestellung_erscheint(self, client, customer):
        _order(client, customer["id"], date.today())
        r = client.get("/api/v1/production/packaging-plan",
                       params={"target_date": date.today().isoformat()})
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["orders"][0]["same_day"] is True

    def test_uebermorgen_erscheint_nicht(self, client, customer):
        _order(client, customer["id"], date.today() + timedelta(days=2))
        r = client.get("/api/v1/production/packaging-plan",
                       params={"target_date": date.today().isoformat()})
        assert r.json()["items"] == []
