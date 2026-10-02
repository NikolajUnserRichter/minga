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


def _bestand(inventory_id):
    from app.models.inventory import SeedInventory
    with TestingSessionLocal() as db:
        inv = db.get(SeedInventory, uuid.UUID(inventory_id))
        return inv.seed_batch_id, (inv.seed_batch.charge_nummer if inv.seed_batch else None)


class TestVerknuepfung:
    """Fehler 3, Grundlage: jeder Lagerbestand kennt seine Charge per Fremdschlüssel."""

    def test_wareneingang_verknuepft_bestand_und_charge(self, client):
        lort = _lagerort(client)
        sorte = _sorte(client)
        inv = _wareneingang(client, sorte, lort)

        batch_id, nummer = _bestand(inv["id"])
        assert batch_id is not None
        assert nummer == "B20115"

    def test_doppelte_chargennummer_wird_nicht_ueber_kreuz_verknuepft(self, client):
        """Gernots Fall: B20115 zweimal erfasst. Jeder Bestand gehört zu seiner eigenen Charge."""
        lort = _lagerort(client)
        sorte = _sorte(client)
        inv1 = _wareneingang(client, sorte, lort)
        inv2 = _wareneingang(client, sorte, lort)

        b1, _ = _bestand(inv1["id"])
        b2, _ = _bestand(inv2["id"])
        assert b1 is not None and b2 is not None
        assert b1 != b2


class TestRueckfuellung:
    """Altbestände ohne Fremdschlüssel werden beim Start deterministisch verknüpft."""

    def _ohne_verknuepfung(self, client, *inventory_ids):
        """Setzt den Fremdschlüssel zurück, um den Zustand vor der Migration nachzustellen."""
        from app.models.inventory import SeedInventory
        with TestingSessionLocal() as db:
            for iid in inventory_ids:
                db.get(SeedInventory, uuid.UUID(iid)).seed_batch_id = None
            db.commit()

    def _lauf(self):
        from app.services.saatgut_verknuepfung import verknuepfe_saatgutbestaende
        with TestingSessionLocal() as db:
            ergebnis = verknuepfe_saatgutbestaende(db)
            db.commit()
            return ergebnis

    def test_eindeutige_und_mehrdeutige_faelle(self, client):
        lort = _lagerort(client)
        sorte = _sorte(client)
        einzel = _wareneingang(client, sorte, lort, charge="SAAM5123A")
        doppelt1 = _wareneingang(client, sorte, lort, charge="B20115")
        doppelt2 = _wareneingang(client, sorte, lort, charge="B20115")
        _platzhalter_charge(sorte)

        soll = {iid: _bestand(iid)[0] for iid in (einzel["id"], doppelt1["id"], doppelt2["id"])}
        self._ohne_verknuepfung(client, *soll)

        self._lauf()

        ist = {iid: _bestand(iid)[0] for iid in soll}
        assert ist == soll, "Rückfüllung muss exakt die Verknüpfung des Wareneingangs wiederherstellen"

    def test_idempotent_und_haengt_nie_um(self, client):
        lort = _lagerort(client)
        sorte = _sorte(client)
        inv = _wareneingang(client, sorte, lort)
        vorher = _bestand(inv["id"])[0]

        self._lauf()
        self._lauf()

        assert _bestand(inv["id"])[0] == vorher

    def test_zu_weit_auseinander_bleibt_unverknuepft(self, client):
        """Liegt keine Charge zeitnah, wird lieber nicht verknüpft als falsch."""
        from app.models.seed import SeedBatch
        from datetime import datetime, timedelta, timezone
        lort = _lagerort(client)
        sorte = _sorte(client)
        inv = _wareneingang(client, sorte, lort)
        batch_id = _bestand(inv["id"])[0]
        self._ohne_verknuepfung(client, inv["id"])
        with TestingSessionLocal() as db:
            db.get(SeedBatch, batch_id).created_at = datetime.now(timezone.utc) - timedelta(days=2)
            db.commit()

        ergebnis = self._lauf()

        assert _bestand(inv["id"])[0] is None
        assert ergebnis["zu_weit_auseinander"] == 1
