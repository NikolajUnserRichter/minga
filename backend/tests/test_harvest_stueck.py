"""
Tests: Ernte-Erfassung in Stück (ganze Schalen) vs. Gramm.

Minga erntet nicht geschnitten — eine Anzuchtkiste enthält 15 Stk (Standard)
bzw. 21 Stk (anderes Format). Ernten können daher in STK erfasst werden;
menge_gramm wird dabei als 0 gespeichert (Spalte ist NOT NULL).
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.seed import Seed, SeedBatch
from app.models.production import GrowBatch, GrowBatchStatus


@pytest.fixture()
def grow_batch(client):
    """Erntereife Charge mit 3 Kisten in der Test-DB."""
    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    seed = Seed(
        name="Erbse Test",
        keimdauer_tage=2,
        wachstumsdauer_tage=10,
        erntefenster_min_tage=11,
        erntefenster_optimal_tage=13,
        erntefenster_max_tage=16,
        ertrag_gramm_pro_tray=Decimal("400"),
    )
    db.add(seed)
    db.flush()

    seed_batch = SeedBatch(
        seed_id=seed.id,
        charge_nummer="SB-TEST-001",
        menge_gramm=Decimal("1000"),
        verbleibend_gramm=Decimal("1000"),
    )
    db.add(seed_batch)
    db.flush()

    batch = GrowBatch(
        seed_batch_id=seed_batch.id,
        tray_anzahl=3,
        aussaat_datum=date.today() - timedelta(days=13),
        erwartete_ernte_min=date.today() - timedelta(days=2),
        erwartete_ernte_optimal=date.today(),
        erwartete_ernte_max=date.today() + timedelta(days=3),
        status=GrowBatchStatus.ERNTEREIF,
    )
    db.add(batch)
    db.commit()
    batch_id = str(batch.id)
    db.close()
    return batch_id


class TestHarvestStueck:
    def test_create_harvest_in_stueck(self, grow_batch, client):
        """STK-Ernte: 45 Stk aus 3 Kisten à 15 Stk."""
        response = client.post("/api/v1/production/harvests", json={
            "grow_batch_id": grow_batch,
            "ernte_datum": date.today().isoformat(),
            "einheit": "STK",
            "menge_stueck": 45,
            "verlust_stueck": 2,
            "stueck_pro_kiste": 15,
            "qualitaet_note": 4,
        })
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["einheit"] == "STK"
        assert data["menge_stueck"] == 45
        assert data["verlust_stueck"] == 2
        assert data["stueck_pro_kiste"] == 15
        # Kein erfundenes Gewicht — 0 statt Fantasiewert
        assert float(data["menge_gramm"]) == 0
        # Verlustquote aus Stückzahlen: 2/47
        assert abs(float(data["verlustquote"]) - (2 / 47 * 100)) < 0.1

    def test_create_harvest_in_gramm_weiterhin(self, grow_batch, client):
        """G-Ernte (Bestandsverhalten) funktioniert unverändert."""
        response = client.post("/api/v1/production/harvests", json={
            "grow_batch_id": grow_batch,
            "ernte_datum": date.today().isoformat(),
            "menge_gramm": 950,
            "verlust_gramm": 50,
            "qualitaet_note": 5,
        })
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["einheit"] == "G"
        assert float(data["menge_gramm"]) == 950

    def test_stueck_ohne_menge_wird_abgelehnt(self, grow_batch, client):
        response = client.post("/api/v1/production/harvests", json={
            "grow_batch_id": grow_batch,
            "ernte_datum": date.today().isoformat(),
            "einheit": "STK",
        })
        assert response.status_code == 422

    def test_gramm_ohne_menge_wird_abgelehnt(self, grow_batch, client):
        response = client.post("/api/v1/production/harvests", json={
            "grow_batch_id": grow_batch,
            "ernte_datum": date.today().isoformat(),
            "einheit": "G",
        })
        assert response.status_code == 422

    def test_stueck_mit_gramm_wird_genullt(self, grow_batch, client):
        """STK-Ernte mit mitgeschickten Gramm: Gramm werden auf 0 gezwungen,
        damit keine erfundenen Gewichte in g-Aggregationen landen."""
        response = client.post("/api/v1/production/harvests", json={
            "grow_batch_id": grow_batch,
            "ernte_datum": date.today().isoformat(),
            "einheit": "STK",
            "menge_stueck": 45,
            "menge_gramm": 5000,
            "verlust_gramm": 500,
        })
        assert response.status_code == 200, response.text
        data = response.json()
        assert float(data["menge_gramm"]) == 0
        assert float(data["verlust_gramm"]) == 0

    def test_notizen_werden_gespeichert(self, grow_batch, client):
        response = client.post("/api/v1/production/harvests", json={
            "grow_batch_id": grow_batch,
            "ernte_datum": date.today().isoformat(),
            "einheit": "STK",
            "menge_stueck": 45,
            "notizen": "Blattränder leicht gelb",
        })
        assert response.status_code == 200, response.text
        assert response.json()["quality_notes"] == "Blattränder leicht gelb"

    def test_dashboard_summary_zaehlt_stueck(self, grow_batch, client):
        client.post("/api/v1/production/harvests", json={
            "grow_batch_id": grow_batch,
            "ernte_datum": date.today().isoformat(),
            "einheit": "STK",
            "menge_stueck": 45,
            "stueck_pro_kiste": 15,
        })
        response = client.get("/api/v1/production/dashboard/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["weekly_harvest_stueck"] == 45
        assert float(data["weekly_harvest_kg"]) == 0.0
