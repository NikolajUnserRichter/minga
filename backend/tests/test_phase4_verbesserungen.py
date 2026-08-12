"""
Tests: Phase-4-Verbesserungen aus dem Gernot-Feedback.

(1) Chargen-Abweichung (zusatz_tage) verschiebt das Erntefenster
(2) Winterzyklus (SEASON_MODE + Seed.winter_extra_tage)
(3) Saatgut-Stammdaten editierbar (BIO-Flag), gespiegelt in SeedBatch
(6) Tagesplan-Endpoint
(7) Wachstumschargen-Import (Excel)
"""
import io
from datetime import date, timedelta

import pytest


@pytest.fixture()
def seed(client):
    r = client.post("/api/v1/seeds", json={
        "name": "Rucola",
        "keimdauer_tage": 2,
        "wachstumsdauer_tage": 5,
        "erntefenster_min_tage": 7,
        "erntefenster_optimal_tage": 8,
        "erntefenster_max_tage": 10,
        "ertrag_gramm_pro_tray": 250,
        "verlustquote_prozent": 5.0,
        "substrat": "Hanfmatte",
        "winter_extra_tage": 2,
    })
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def seed_batch(client, seed):
    r = client.post("/api/v1/seeds/batches", json={
        "seed_id": seed["id"],
        "charge_nummer": "RU-001",
        "menge_gramm": 2000,
    })
    assert r.status_code == 201, r.text
    return r.json()


class TestChargenAbweichung:
    def test_zusatz_tage_verschiebt_erntefenster(self, client, seed_batch):
        aussaat = date(2026, 9, 1)
        r = client.post("/api/v1/production/grow-batches", json={
            "seed_batch_id": seed_batch["id"],
            "tray_anzahl": 2,
            "aussaat_datum": aussaat.isoformat(),
            "zusatz_tage": 1,
        })
        assert r.status_code == 201, r.text
        b = r.json()
        assert b["erwartete_ernte_optimal"] == "2026-09-10"  # 01.09. + 8 (Sorte) + 1 (Charge)

    def test_substrat_am_seed(self, client, seed):
        r = client.get(f"/api/v1/seeds/{seed['id']}")
        assert r.json()["substrat"] == "Hanfmatte"


class TestWinterzyklus:
    def test_winter_verlaengert_fenster(self, client, seed_batch):
        r = client.patch("/api/v1/admin/settings", json={"SEASON_MODE": "WINTER"})
        assert r.status_code == 200, r.text
        aussaat = date(2026, 11, 1)
        r = client.post("/api/v1/production/grow-batches", json={
            "seed_batch_id": seed_batch["id"],
            "tray_anzahl": 2,
            "aussaat_datum": aussaat.isoformat(),
        })
        assert r.status_code == 201, r.text
        # +8 optimal +2 winter_extra_tage
        assert r.json()["erwartete_ernte_optimal"] == "2026-11-11"
        # zurücksetzen für andere Tests
        client.patch("/api/v1/admin/settings", json={"SEASON_MODE": "SOMMER"})


class TestSaatgutStammdaten:
    def test_bio_flag_nachpflegen(self, client, seed, seed_batch):
        # Wareneingang anlegen (ohne BIO)
        loc = client.post("/api/v1/inventory/locations", json={
            "code": "L1", "name": "Lager", "location_type": "LAGER",
        }).json()
        inv = client.post("/api/v1/inventory/seeds/receive", params={
            "seed_id": seed["id"],
            "batch_number": "RU-002",
            "quantity": 500,
            "unit": "G",
            "location_id": loc["id"],
        })
        assert inv.status_code == 201, inv.text
        inv_id = inv.json()["id"]
        assert inv.json()["is_organic"] is False

        # BIO nachträglich setzen
        r = client.patch(f"/api/v1/inventory/seeds/{inv_id}", json={
            "is_organic": True,
            "organic_certificate": "DE-ÖKO-006",
        })
        assert r.status_code == 200, r.text
        assert r.json()["is_organic"] is True

        # Spiegel-SeedBatch wurde mitgezogen
        batches = client.get(f"/api/v1/seeds/{seed['id']}/batches").json()
        mirror = next(b for b in (batches if isinstance(batches, list) else batches["items"]) if b["charge_nummer"] == "RU-002")
        assert mirror["bio_zertifiziert"] is True


class TestTagesplan:
    def test_day_plan_liefert_sektionen(self, client, seed_batch):
        cu = client.post("/api/v1/sales/customers", json={"name": "Gastro T", "typ": "GASTRO"}).json()
        client.post("/api/v1/sales/orders", json={
            "customer_id": cu["id"],
            "requested_delivery_date": (date.today() + timedelta(days=1)).isoformat(),
            "lines": [{"product_name": "Schale", "quantity": 3, "unit": "STK",
                       "unit_price": 2.5, "tax_rate": "REDUZIERT"}],
        })
        r = client.get("/api/v1/production/day-plan", params={"target_date": date.today().isoformat()})
        assert r.status_code == 200, r.text
        plan = r.json()
        for key in ("aussaat", "ernte", "verpacken", "ausliefern"):
            assert key in plan
        assert len(plan["verpacken"]) == 1  # Lieferung morgen → heute packen
        assert plan["ausliefern"] == []


class TestGrowBatchImport:
    def test_import_wachstumschargen(self, client, seed):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["sorte", "aussaat_datum", "tray_anzahl", "status", "charge_nummer",
                   "regal_position", "ernte_datum", "ernte_menge_stueck", "ernte_menge_gramm"])
        ws.append(["Rucola", "01.07.2026", 4, "GEERNTET", "", "", "09.07.2026", 60, ""])
        ws.append(["Rucola", date.today().isoformat(), 6, "", "", "R1", "", "", ""])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        r = client.post("/api/v1/imports/grow_batches",
                        files={"file": ("chargen.xlsx", buf.getvalue(),
                                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert r.status_code == 200, r.text
        assert r.json()["created"] == 2

        batches = client.get("/api/v1/production/grow-batches").json()
        assert len(batches) == 2
        # Idempotenz: zweiter Upload legt nichts doppelt an
        buf.seek(0)
        r2 = client.post("/api/v1/imports/grow_batches",
                         files={"file": ("chargen.xlsx", buf.getvalue(),
                                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert r2.json()["created"] == 0
