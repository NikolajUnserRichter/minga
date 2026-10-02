"""Gernot-Feedback vom 02.10.2026 — Saatgut-Lagerbücher.

(1) Aussaat meldete "keine Saatgut-Charge im Lager", obwohl Chargen da waren.
(2) Neue Wareneingänge fehlten bei "Alle Lagerorte".
(3) Lager- und Chargenbuch liefen auseinander; Aussaat buchte nichts ab.
"""
import uuid
from decimal import Decimal

import pytest

from tests.conftest import TestingSessionLocal


def _lagerort(client, code="LAG-01"):
    r = client.post("/api/v1/inventory/locations", json={
        "code": code, "name": f"Lager {code}", "location_type": "LAGER",
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _sorte(client, name="Borretsch", gramm_pro_kiste=80):
    body = {
        "name": name, "keimdauer_tage": 2, "wachstumsdauer_tage": 8,
        "erntefenster_min_tage": 9, "erntefenster_optimal_tage": 11,
        "erntefenster_max_tage": 14, "ertrag_gramm_pro_tray": 350,
    }
    if gramm_pro_kiste is not None:
        body["saatgut_pro_einheit_gramm"] = gramm_pro_kiste
    r = client.post("/api/v1/seeds", json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _wareneingang(client, sorte, lagerort, charge="B20115", gramm=10000):
    """Wareneingang wie in der Oberfläche. Liefert den Lagerbestand (SeedInventory)."""
    r = client.post("/api/v1/inventory/seeds/receive", params={
        "seed_id": sorte["id"], "batch_number": charge,
        "quantity": gramm, "unit": "G", "location_id": lagerort["id"],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _chargen(client, sorte):
    r = client.get(f"/api/v1/seeds/{sorte['id']}/batches")
    assert r.status_code == 200, r.text
    return r.json()


def _platzhalter_charge(sorte, nummer=None):
    """Legt eine Charge so an wie der Historien-Import: 0 g, kein Lagerbestand.

    Über die API geht das nicht — das Eingabeschema verlangt menge_gramm > 0.
    Genau deshalb direkt über das ORM, wie imports.py es tut.
    """
    from app.models.seed import SeedBatch
    with TestingSessionLocal() as db:
        b = SeedBatch(
            seed_id=uuid.UUID(sorte["id"]),
            charge_nummer=nummer or f"IMPORT-{sorte['name']}",
            menge_gramm=Decimal("0"),
            verbleibend_gramm=Decimal("0"),
        )
        db.add(b)
        db.commit()
        return str(b.id)


class TestChargenlisteMitPlatzhaltern:
    """Fehler 1: eine 0-g-Platzhalter-Charge sprengte die ganze Liste."""

    def test_platzhalter_sprengt_die_liste_nicht(self, client):
        lort = _lagerort(client)
        sorte = _sorte(client)
        _wareneingang(client, sorte, lort)
        _platzhalter_charge(sorte)

        chargen = _chargen(client, sorte)
        nummern = sorted(c["charge_nummer"] for c in chargen)
        assert nummern == ["B20115", "IMPORT-Borretsch"]

    def test_eingabe_bleibt_streng(self, client):
        """Die Lockerung gilt nur für die Antwort. Eine neue Charge mit 0 g bleibt verboten."""
        sorte = _sorte(client)
        r = client.post("/api/v1/seeds/batches", json={
            "seed_id": sorte["id"], "charge_nummer": "NULL-1", "menge_gramm": "0",
        })
        assert r.status_code == 422, r.text
