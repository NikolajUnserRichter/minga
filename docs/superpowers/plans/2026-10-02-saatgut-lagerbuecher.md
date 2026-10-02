# Saatgut-Lagerbücher zusammenführen — Implementation Plan

> **For agentic workers:** Diesen Plan Task für Task abarbeiten. Schritte nutzen Checkbox-Syntax (`- [ ]`). Kein Task wird übersprungen oder zusammengefasst. Inhaltliche Widersprüche zwischen Plan und Code: stoppen und mit exakter Fehlerausgabe melden. Rein redaktionelle Unstimmigkeiten mit eindeutiger Absicht: selbst auflösen und in der Abschlussmeldung vermerken.

**Goal:** Saatgut-Bestand hat genau eine Wahrheit; das Aussaat-Formular findet vorhandene Chargen wieder, die Inventarliste verschluckt keine Wareneingänge, und eine Aussaat bucht das verbrauchte Saatgut ab.

**Architecture:** Heute führen zwei Tabellen dieselbe Menge, und jede bekommt nur die Hälfte der Buchungen mit. Das Lagerbuch `seed_inventory` wird die einzige Wahrheit für Mengen; das Chargenbuch `seed_batches` bleibt Träger von BIO-Nachweis, Wachstumsparametern und Ziel der Wachstumschargen. Ein expliziter Fremdschlüssel `seed_inventory.seed_batch_id` ersetzt die heutige Verknüpfung über die Chargennummer, und die verfügbare Menge einer Charge wird aus dem verknüpften Lagerbestand abgeleitet statt separat gebucht. Darauf sitzen drei kleine Reparaturen: Antwortschema, Listen-Kürzung, Fehleranzeige.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 (`Mapped`/`mapped_column`), SQLite je Mandant, Pydantic v2, React + TypeScript, TanStack Query.

**Spec:** Meldung Gernot Kleinberger vom 02.10.2026 plus die Analyse im Abschnitt „Verifizierter Ausgangsbefund" unten. Alle Zahlen dort sind am 02.10.2026 an der Produktionsdatenbank des Mandanten `minga` gemessen, nicht geschätzt.

## Verifizierter Ausgangsbefund

**Meldung:** (1) „Neue Aussaat" meldet „Für diese Sorte ist noch keine Saatgut-Charge im Lager", obwohl Chargen da sind (z. B. Amaranth, Borretsch). (2) Ein neuer Borretsch-Wareneingang ist nur sichtbar, wenn ein Lagerort gewählt ist, nicht bei „Alle Lagerorte".

**Ursache Fehler 1** — Gernots Historien-Import vom 17.09.2026 09:50 legt je Sorte absichtlich eine Platzhalter-Charge `IMPORT-<Sorte>` mit `menge_gramm = 0` an (`backend/app/api/v1/imports.py:687` und `:1024`; laut `2026-09-05-warenfluss-release-bestandsaufnahme.md` Zeile 62 bewusst „als Marker mit Menge 0, keine Bestandswirkung"). `SeedBatchResponse` erbt von `SeedBatchBase` die Eingaberegel `menge_gramm: Field(..., gt=0)` (`backend/app/schemas/seed.py:117`). Eine einzige solche Zeile lässt `GET /seeds/{seed_id}/batches` mit 500 scheitern; `SowingForm.tsx` macht daraus über `const { data: seedBatches = [] }` still eine leere Liste und zeigt die falsche Meldung. Betroffen: **18 von 21** aktiven Einzelsorten. Gegenprobe auf allen 48 Produktionschargen: Lockert man nur `menge_gramm` auf `≥ 0`, bestehen alle 48 — keine andere geerbte Regel wird von Altdaten verletzt.

**Ursache Fehler 2** — `GET /inventory/seeds` schneidet nach `page_size = 20` ab, **ohne `ORDER BY`**, und die Inventarseite blättert nicht. Gernot hat 30 aktive Saatgut-Bestände; die beiden Borretsch-Eingänge stehen auf Platz 29 und 30. Mit Lagerort LAG-01 allein sind es 17 Zeilen → passt auf eine Seite → sichtbar. `/inventory/packaging` hat dasselbe Muster, ist aber derzeit leer.

**Ursache Fehler 3 (nicht gemeldet, aber durch Fix 1 freigelegt)** — die zwei Lagerbücher:

| Vorgang | `seed_inventory` | `seed_batches` |
|---|---|---|
| Wareneingang | + | + (Spiegel) |
| Korrektur | ± | — |
| Manuelle Entnahme (Lager-Seite) | − | — |
| Aussaat normale Sorte | — | — |
| Aussaat Mischsorte | − | − (über `_spiegel_seed_batch`) |

Konkret: Gernot hat Borretsch `B20115` zweimal erfasst (12:49 und 12:51, weil er den ersten Eingang wegen Fehler 2 nicht sah) und den zweiten um 12:55 selbst auf 0 korrigiert („Korrektur: Eingabefehler"). Im Chargenbuch stehen beide weiter auf 10.000 g. Würde nur Fehler 1 behoben, böte das Aussaat-Formular 20 kg Borretsch an, wo 10 kg liegen.

Die heutige Verknüpfung ist eine `viewonly`-Beziehung über `seed_id` + Chargennummer (`backend/app/models/inventory.py:168-180`). **Sieben Chargennummern kommen doppelt vor**, für diese Lose ist sie bereits mehrdeutig.

**Rückfüllung gemessen:** 48 Chargen, 30 Bestände. 16 eindeutig über (Sorte, Chargennummer); 14 mehrdeutig, aber jeder Bestand liegt 2–19 ms neben genau einer Charge (gleicher Wareneingangs-Request); 18 ohne Gegenstück — exakt die Import-Platzhalter. Jeder der 30 Bestände findet genau eine Charge.

**Saatgutdichte:** alle 21 aktiven Einzelsorten haben `saatgut_pro_einheit_gramm` hinterlegt (28 bis 450 g/Kiste). Eine automatische Abbuchung beim Aussäen greift also nie auf einen geratenen Wert zurück.

## Global Constraints

- **Python ausschließlich** über `/Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python`. `backend/venv` und `backend/venv311` sind kaputt.
- **Vollauf:** `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py` — dauert ca. 19 Minuten.
- **Baseline main:** 15 failed / 484 passed / 2 skipped / 1 error. **Nur die Liste der Fehlernamen vergleichen, nie die Anzahl** — sie wächst mit jedem Release. Die 15 Altlasten: `test_api.py::TestHealth::test_root_endpoint`, `test_refinements.py::test_main_app_imports`, `test_auth_manual.py::test_auth_failure`, `test_auth_manual.py::test_auth_success`, `test_features.py::TestFeatures::test_subscription_processing`, `test_production_readiness.py::test_dunning_level1/2/3`, `test_production_readiness.py::test_quality_auto_approved`, `…::test_quality_rejected_high_loss`, `…::test_quality_rejected_low_note`, `test_services.py::TestInvoiceService` ×4, plus ERROR `test_production_automation.py::test_approve_suggestion_creates_grow_batch`.
- **Schema-Änderungen ausschließlich über `tenancy._auto_migrate()`**, nicht Alembic. UUID-Spalten liegen in SQLite als `CHAR(32)` (Vorbild: `_add_col_if_missing("inventory_movements", "trade_goods_id", "CHAR(32)")`).
- **Die Codex-Sandbox hat kein Netzwerk.** Kein `git pull`, kein `npm install`.
- **Kein Deploy in diesem Plan.** Vor dem Deploy wird extern ein WAL-sicheres Backup des Mandanten gezogen.
- **Vergangene Aussaaten werden nicht rückwirkend abgebucht.** Der Bestand ist dadurch heute zu hoch; das klärt eine Inventur, keine Neuberechnung.
- UI-Texte auf Deutsch.
- Neue Tests nach `backend/tests/test_gernot_261002.py` (Konvention `test_gernot_<JJMMTT>.py`).

## Review Focus

1. **Abbuchung scheitert → keine Wachstumscharge.** Reicht der Bestand nicht, muss die Aussaat mit 400 abbrechen und darf keine halbe Wachstumscharge hinterlassen. Getestet in Task 4.
2. **Zwei Wareneingänge mit derselben Chargennummer** werden je mit ihrer eigenen Charge verknüpft, nicht über Kreuz. Getestet in Task 2.
3. **Aussäen aus einem auf 0 korrigierten Los** wird verweigert, statt ins Minus zu laufen. Getestet in Task 4.
4. **`_auto_migrate` läuft bei jedem Start.** Die Rückfüllung muss idempotent sein und darf eine bestehende Verknüpfung nie umhängen. Getestet in Task 2.
5. **Platzhalter-Chargen** (0 g, kein Lagerbestand) dürfen die Liste nicht sprengen und nicht aussäbar sein. Getestet in Task 1 und Task 4.

## File Structure

| Datei | Verantwortung | Task |
|---|---|---|
| `backend/app/schemas/seed.py` | Antwortschema liest Altdaten | 1, 3 |
| `backend/app/models/inventory.py` | Fremdschlüssel + Beziehung am Lagerbestand | 2 |
| `backend/app/models/seed.py` | Rückbeziehung + abgeleitete Menge an der Charge | 2, 3 |
| `backend/app/services/saatgut_verknuepfung.py` | **neu** — Rückfüllung, einzeln testbar | 2 |
| `backend/app/tenancy.py` | Spalte + Aufruf der Rückfüllung beim Start | 2 |
| `backend/app/api/v1/inventory.py` | Wareneingang setzt Fremdschlüssel; Sortierung | 2, 5 |
| `backend/app/api/v1/production.py` | Aussaat bucht ab | 4 |
| `backend/tests/test_gernot_261002.py` | **neu** — alle Tests dieses Plans | 1–5 |
| `frontend/src/services/api.ts` | `page_size` für die Bestandslisten | 5 |
| `frontend/src/pages/Inventory.tsx` | volle Liste + Kürzungshinweis | 5 |
| `frontend/src/components/domain/SowingForm.tsx` | Fehler als Fehler anzeigen | 6 |

---

### Task 1: Die Chargenliste übersteht Platzhalter-Chargen

**Files:**
- Modify: `backend/app/schemas/seed.py:156-163` (`SeedBatchResponse`)
- Create: `backend/tests/test_gernot_261002.py`

**Interfaces:**
- Produces: Test-Helfer `_lagerort`, `_sorte`, `_wareneingang`, `_chargen`, `_platzhalter_charge` in `test_gernot_261002.py`, die Tasks 2–5 wiederverwenden.

- [ ] **Step 1: Testdatei mit Helfern und erstem Test anlegen**

```python
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
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261002.py -v`
Erwartet: `test_platzhalter_sprengt_die_liste_nicht` FAILS — der Endpunkt antwortet 500 (Assertion `200 != 500` im Helfer `_chargen`). `test_eingabe_bleibt_streng` ist bereits grün.

- [ ] **Step 3: Antwortschema lockern**

In `backend/app/schemas/seed.py`, Klasse `SeedBatchResponse`:

```python
class SeedBatchResponse(SeedBatchBase):
    """Schema für Saatgut-Charge-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    # Die Antwort muss alles lesen können, was in der Datenbank steht. Der
    # Historien-Import legt Platzhalter-Chargen mit 0 g an; die geerbte
    # Eingaberegel gt=0 ließ daran die ganze Liste scheitern. Eingabe bleibt streng.
    menge_gramm: Decimal = Field(..., ge=0, description="Gelieferte Menge in Gramm")

    id: UUID
    seed_id: UUID
    verbleibend_gramm: Decimal
    created_at: datetime
```

`SeedBatchBase`, `SeedBatchCreate` und `SeedBatchUpdate` **nicht** anfassen.

- [ ] **Step 4: Grün bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261002.py -v`
Erwartet: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/seed.py backend/tests/test_gernot_261002.py
git commit -m "fix(saatgut): Chargenliste scheiterte an Platzhalter-Chargen des Historien-Imports"
```

---

### Task 2: Expliziter Fremdschlüssel zwischen Lagerbestand und Charge

**Files:**
- Modify: `backend/app/models/inventory.py:103-180` (`SeedInventory`)
- Modify: `backend/app/models/seed.py` (`SeedBatch`, Rückbeziehung)
- Create: `backend/app/services/saatgut_verknuepfung.py`
- Modify: `backend/app/tenancy.py` (Spalte + Aufruf)
- Modify: `backend/app/api/v1/inventory.py:186-270` (`receive_seed_batch`)
- Test: `backend/tests/test_gernot_261002.py`

**Interfaces:**
- Consumes: Helfer aus Task 1.
- Produces:
  - `SeedInventory.seed_batch_id: Mapped[Optional[uuid.UUID]]` (FK auf `seed_batches.id`)
  - `SeedInventory.seed_batch: Mapped[Optional["SeedBatch"]]` — **ersetzt** die bisherige `viewonly`-Beziehung über die Chargennummer
  - `SeedBatch.bestaende: Mapped[list["SeedInventory"]]` — Rückbeziehung, Task 3 summiert darüber
  - `saatgut_verknuepfung.verknuepfe_saatgutbestaende(db: Session) -> dict` mit Schlüsseln `verknuepft`, `mehrdeutig_per_zeit`, `ohne_charge`, `zu_weit_auseinander`

- [ ] **Step 1: Failing Tests schreiben**

An `test_gernot_261002.py` anhängen:

```python
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
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261002.py -v`
Erwartet: alle neuen Tests FAIL — `SeedInventory` hat kein `seed_batch_id`, das Modul `saatgut_verknuepfung` existiert nicht.

- [ ] **Step 3: Fremdschlüssel und Beziehungen**

In `backend/app/models/inventory.py`, Klasse `SeedInventory`, neben `seed_id`:

```python
    # Expliziter Verweis auf die Charge (Rückverfolgbarkeit). Ersetzt die
    # frühere Verknüpfung über Sorte + Chargennummer, die bei doppelt
    # erfassten Chargennummern mehrdeutig war.
    seed_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("seed_batches.id"), nullable=True, index=True
    )
```

Die bestehende `viewonly`-Beziehung `seed_batch` (Zeilen ~168-180, mit `primaryjoin` über `charge_nummer`) **vollständig ersetzen** durch:

```python
    seed_batch: Mapped[Optional["SeedBatch"]] = relationship(
        "SeedBatch", back_populates="bestaende"
    )
```

Den Kommentarblock darüber („verbunden nur über Sorte + Chargennummer (kein Fremdschlüssel)") entfernen — er wäre danach falsch. Die einzige Leserin der Beziehung, die Property bei Zeile ~189 (`in_production_at`), bleibt unverändert und funktioniert weiter.

In `backend/app/models/seed.py`, Klasse `SeedBatch`:

```python
    # Lagerbestände dieser Charge (in der Regel genau einer je Wareneingang).
    bestaende: Mapped[list["SeedInventory"]] = relationship(
        "SeedInventory", back_populates="seed_batch"
    )
```

- [ ] **Step 4: Wareneingang setzt den Fremdschlüssel**

In `backend/app/api/v1/inventory.py`, `receive_seed_batch`, direkt nach `db.add(seed_batch)`:

```python
        db.flush()  # seed_batch.id vergeben
        inventory.seed_batch_id = seed_batch.id
```

- [ ] **Step 5: Rückfüllung als eigenes Modul**

Neue Datei `backend/app/services/saatgut_verknuepfung.py`:

```python
"""Verknüpft Altbestände mit ihrer Saatgut-Charge.

Vor der Einführung von seed_inventory.seed_batch_id legte der Wareneingang
Lagerbestand und Charge im selben Request an, verbunden nur über Sorte +
Chargennummer. Diese Funktion stellt die Verknüpfung nachträglich her.

Regeln:
- Nur Bestände ohne Verknüpfung werden angefasst. Eine bestehende wird nie
  umgehängt — die Funktion läuft bei jedem Start und muss idempotent sein.
- Kandidat ist eine Charge gleicher Sorte und gleicher Chargennummer, die noch
  keinem anderen Bestand gehört.
- Bei mehreren Kandidaten gewinnt der zeitlich nächste. Beide Zeilen entstanden
  im selben Request; in Produktion lagen sie 2-19 ms auseinander.
- Liegt der nächste Kandidat weiter als MAX_ABSTAND entfernt, wird nicht
  verknüpft. Lieber keine Verknüpfung als eine falsche.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import SeedInventory
from app.models.seed import SeedBatch

logger = logging.getLogger(__name__)

MAX_ABSTAND = timedelta(seconds=5)


def _utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def verknuepfe_saatgutbestaende(db: Session) -> dict:
    ergebnis = {"verknuepft": 0, "mehrdeutig_per_zeit": 0, "ohne_charge": 0, "zu_weit_auseinander": 0}

    vergeben = set(db.execute(
        select(SeedInventory.seed_batch_id).where(SeedInventory.seed_batch_id.is_not(None))
    ).scalars())

    offen = db.execute(
        select(SeedInventory).where(SeedInventory.seed_batch_id.is_(None)).order_by(SeedInventory.created_at)
    ).scalars().all()

    for inv in offen:
        kandidaten = [
            b for b in db.execute(
                select(SeedBatch).where(
                    SeedBatch.seed_id == inv.seed_id,
                    SeedBatch.charge_nummer == inv.batch_number,
                )
            ).scalars()
            if b.id not in vergeben
        ]
        if not kandidaten:
            ergebnis["ohne_charge"] += 1
            continue

        naechste = min(kandidaten, key=lambda b: abs(_utc(b.created_at) - _utc(inv.created_at)))
        if abs(_utc(naechste.created_at) - _utc(inv.created_at)) > MAX_ABSTAND:
            ergebnis["zu_weit_auseinander"] += 1
            logger.warning(
                "[saatgut] Bestand %s (Charge %s) nicht verknüpft: keine zeitnahe Charge",
                inv.id, inv.batch_number,
            )
            continue

        if len(kandidaten) > 1:
            ergebnis["mehrdeutig_per_zeit"] += 1
        inv.seed_batch_id = naechste.id
        vergeben.add(naechste.id)
        ergebnis["verknuepft"] += 1

    db.flush()
    if any(ergebnis.values()):
        logger.info("[saatgut] Rückfüllung: %s", ergebnis)
    return ergebnis
```

Über das ORM, nicht über rohes SQL: UUIDs liegen in SQLite als `CHAR(32)` ohne Bindestriche, ein Vergleich in rohem SQL scheitert leicht am Format.

- [ ] **Step 6: Spalte und Rückfüllung in `_auto_migrate`**

In `backend/app/tenancy.py` bei den übrigen `_add_col_if_missing`-Aufrufen:

```python
        _add_col_if_missing("seed_inventory", "seed_batch_id", "CHAR(32)")
```

Danach — **nach** allen `_add_col_if_missing`-Aufrufen, damit die Spalte sicher existiert — die Rückfüllung über eine Session auf derselben Engine:

```python
        # Altbestände mit ihrer Charge verknüpfen (idempotent, läuft bei jedem Start).
        from sqlalchemy.orm import Session as _Session
        from app.services.saatgut_verknuepfung import verknuepfe_saatgutbestaende
        if inspector.has_table("seed_inventory") and inspector.has_table("seed_batches"):
            with _Session(engine) as _s:
                verknuepfe_saatgutbestaende(_s)
                _s.commit()
```

Die Variablennamen `inspector` und `engine` an die tatsächlichen in `_auto_migrate` anpassen — die Funktion `_add_col_if_missing` (ca. Zeile 270) nutzt beide bereits. Achtung: `inspector` cacht Spalteninformationen; wird er vor dem `ADD COLUMN` erzeugt, kennt er die neue Spalte nicht. Die Rückfüllung arbeitet über das ORM und ist davon nicht betroffen, nur die `has_table`-Prüfung nutzt ihn.

- [ ] **Step 7: Grün bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261002.py -v`
Erwartet: alle Tests aus Task 1 und 2 passed.

- [ ] **Step 8: Vollauf gegen die Baseline**

Run: Vollauf aus den Global Constraints. Erwartet: dieselben 15 Fehlernamen. Besonders `test_import_chargen.py`, `test_inventur.py` und die Mischsorten-Tests prüfen — sie lesen die ersetzte Beziehung indirekt.

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/inventory.py backend/app/models/seed.py \
        backend/app/services/saatgut_verknuepfung.py backend/app/tenancy.py \
        backend/app/api/v1/inventory.py backend/tests/test_gernot_261002.py
git commit -m "feat(saatgut): Lagerbestand verweist per Fremdschlüssel auf seine Charge"
```

---

### Task 3: Verfügbare Menge einer Charge wird aus dem Lagerbestand abgeleitet

**Files:**
- Modify: `backend/app/models/seed.py` (`SeedBatch`)
- Modify: `backend/app/schemas/seed.py` (`SeedBatchResponse`)
- Test: `backend/tests/test_gernot_261002.py`

**Interfaces:**
- Consumes: `SeedBatch.bestaende` aus Task 2.
- Produces: `SeedBatch.verfuegbar_gramm -> Decimal` (Property). Vertrag: Das API-Feld `verbleibend_gramm` in jeder `SeedBatchResponse` liefert **diesen** Wert. Task 4 bucht genau dort ab, woher er stammt.

**Regel:** Hat die Charge verknüpfte Lagerbestände, ist die verfügbare Menge die Summe ihrer `current_quantity_kg × 1000` über alle Bestände mit `is_active` und **nicht** `is_blocked`. Hat sie keine (Import-Platzhalter, direkt über `/seeds/batches` angelegte Chargen), gilt die gespeicherte Spalte `verbleibend_gramm`.

- [ ] **Step 1: Failing Tests — Gernots Phantom-Charge**

```python
def _korrektur(client, inventory_id, kg, grund="Korrektur: Eingabefehler"):
    r = client.post("/api/v1/inventory/correction", params={
        "inventory_id": inventory_id, "inventory_type": "SAATGUT",
        "actual_quantity": kg, "reason": grund,
    })
    assert r.status_code == 200, r.text


class TestAbgeleiteteMenge:
    """Fehler 3: Korrekturen im Lager müssen im Aussaat-Formular ankommen."""

    def test_korrigierte_doppelbuchung_zeigt_keine_phantommenge(self, client):
        """Exakt Gernots B20115: zweimal 10 kg erfasst, den zweiten auf 0 korrigiert."""
        lort = _lagerort(client)
        sorte = _sorte(client)
        _wareneingang(client, sorte, lort)
        doppelt = _wareneingang(client, sorte, lort)
        _korrektur(client, doppelt["id"], 0)

        mengen = sorted(Decimal(str(c["verbleibend_gramm"])) for c in _chargen(client, sorte))
        assert mengen == [Decimal("0"), Decimal("10000")]

    def test_gesperrter_bestand_ist_nicht_verfuegbar(self, client):
        from app.models.inventory import SeedInventory
        lort = _lagerort(client)
        sorte = _sorte(client)
        inv = _wareneingang(client, sorte, lort)
        with TestingSessionLocal() as db:
            db.get(SeedInventory, uuid.UUID(inv["id"])).is_blocked = True
            db.commit()

        assert Decimal(str(_chargen(client, sorte)[0]["verbleibend_gramm"])) == Decimal("0")

    def test_platzhalter_ohne_bestand_nutzt_gespeicherten_wert(self, client):
        sorte = _sorte(client)
        _platzhalter_charge(sorte)
        assert Decimal(str(_chargen(client, sorte)[0]["verbleibend_gramm"])) == Decimal("0")
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261002.py::TestAbgeleiteteMenge -v`
Erwartet: `test_korrigierte_doppelbuchung_zeigt_keine_phantommenge` FAILS mit `[10000, 10000] != [0, 10000]` — genau die Phantommenge. `test_gesperrter_bestand_ist_nicht_verfuegbar` FAILS. Der Platzhalter-Test ist bereits grün.

- [ ] **Step 3: Property an der Charge**

In `backend/app/models/seed.py`, Klasse `SeedBatch`:

```python
    @property
    def verfuegbar_gramm(self) -> Decimal:
        """Tatsächlich verfügbare Menge in Gramm.

        Mit verknüpftem Lagerbestand ist dieser die einzige Wahrheit — er sieht
        Wareneingang, Korrektur und Entnahme. Gesperrte und inaktive Bestände
        zählen nicht. Ohne Lagerbestand (Import-Platzhalter, direkt angelegte
        Chargen) gilt der gespeicherte Wert.
        """
        if self.bestaende:
            return sum(
                (Decimal(str(b.current_quantity_kg)) * 1000
                 for b in self.bestaende if b.is_active and not b.is_blocked),
                Decimal("0"),
            )
        return Decimal(str(self.verbleibend_gramm or 0))
```

`Decimal` oben importieren, falls noch nicht vorhanden.

- [ ] **Step 4: Antwortfeld aus der Property speisen**

`verbleibend_gramm` ist eine gemappte Spalte; eine gleichnamige Property ist nicht möglich. Das API-Feld muss deshalb aus `verfuegbar_gramm` befüllt werden. Den Mechanismus wählst du — naheliegend ist ein `model_validator(mode="before")` in `SeedBatchResponse`, der bei einem ORM-Objekt `verfuegbar_gramm` liest und als `verbleibend_gramm` einsetzt. Bedingungen: Ein **Dict** als Eingabe muss weiterhin funktionieren (der Validierungstest gegen Produktionsdaten übergibt Dicts), und der Feldname in der API bleibt `verbleibend_gramm` — das Frontend liest ihn.

- [ ] **Step 5: Grün bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261002.py -v`
Erwartet: alle Tests aus Task 1–3 passed.

- [ ] **Step 6: Vollauf gegen die Baseline.** Erwartet: dieselben 15 Fehlernamen.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/seed.py backend/app/schemas/seed.py backend/tests/test_gernot_261002.py
git commit -m "fix(saatgut): verfügbare Chargenmenge aus dem Lagerbestand ableiten"
```

---

### Task 4: Die Aussaat bucht das verbrauchte Saatgut ab

**Files:**
- Modify: `backend/app/api/v1/production.py:67-150` (`create_grow_batch`)
- Test: `backend/tests/test_gernot_261002.py`

**Interfaces:**
- Consumes: `SeedBatch.bestaende` (Task 2), `SeedBatch.verfuegbar_gramm` (Task 3), vorhandenes `InventoryService(db).consume_seed_for_sowing(seed_inventory_id, quantity_kg, grow_batch_id=..., created_by=None, reason=None, reference_number=None)` in `backend/app/services/inventory_service.py` — wirft `ValueError` bei fehlendem, gesperrtem oder unzureichendem Bestand und schreibt eine Bewegung `MovementType.PRODUKTION`.

**Regel:** Nur der Pfad **mit** `seed_batch_id` (normale Sorte) ändert sich. Der Mischsorten-Pfad (`mische_charge`) bucht bereits ab und bleibt unverändert. Bedarf = `tray_anzahl × seed.saatgut_pro_einheit_gramm`. Abgebucht wird dort, woher `verfuegbar_gramm` stammt: hat die Charge Lagerbestände, aus dem ersten aktiven, nicht gesperrten mit ausreichender Menge über `consume_seed_for_sowing`; sonst aus der gespeicherten Spalte `verbleibend_gramm`. **Ist an der Sorte keine Saatgutdichte hinterlegt, wird nicht abgebucht** — es gibt keine verlässliche Menge, und ein geratener Wert würde den Bestand fälschen (in Produktion haben alle 21 Sorten eine Dichte). Reicht der Bestand nicht: 400, und es entsteht **keine** Wachstumscharge.

- [ ] **Step 1: Failing Tests**

```python
def _aussaat(client, charge_id, kisten):
    return client.post("/api/v1/production/grow-batches", json={
        "seed_batch_id": charge_id, "tray_anzahl": kisten, "aussaat_datum": "2026-10-02",
    })


def _lagermenge_kg(inventory_id):
    from app.models.inventory import SeedInventory
    with TestingSessionLocal() as db:
        return Decimal(str(db.get(SeedInventory, uuid.UUID(inventory_id)).current_quantity_kg))


def _anzahl_wachstumschargen():
    from app.models.production import GrowBatch
    with TestingSessionLocal() as db:
        return db.query(GrowBatch).count()


class TestAbbuchungBeimAussaeen:

    def test_aussaat_bucht_bedarf_ab(self, client):
        """10 Kisten Borretsch à 80 g = 800 g von 10 kg."""
        lort = _lagerort(client)
        sorte = _sorte(client, gramm_pro_kiste=80)
        inv = _wareneingang(client, sorte, lort, gramm=10000)
        charge_id = _chargen(client, sorte)[0]["id"]

        r = _aussaat(client, charge_id, 10)

        assert r.status_code in (200, 201), r.text
        assert _lagermenge_kg(inv["id"]) == Decimal("9.2")
        assert Decimal(str(_chargen(client, sorte)[0]["verbleibend_gramm"])) == Decimal("9200")

    def test_bewegung_verweist_auf_die_wachstumscharge(self, client):
        from app.models.inventory import InventoryMovement, MovementType
        lort = _lagerort(client)
        sorte = _sorte(client, gramm_pro_kiste=80)
        inv = _wareneingang(client, sorte, lort)
        wb = _aussaat(client, _chargen(client, sorte)[0]["id"], 10).json()

        with TestingSessionLocal() as db:
            bewegung = db.query(InventoryMovement).filter_by(
                seed_inventory_id=uuid.UUID(inv["id"]), movement_type=MovementType.PRODUKTION,
            ).one()
            assert str(bewegung.grow_batch_id) == wb["id"]

    def test_zu_wenig_saatgut_bricht_ohne_halbe_charge_ab(self, client):
        """Review Focus 1 + 3: Gernots auf 0 korrigiertes Los."""
        lort = _lagerort(client)
        sorte = _sorte(client, gramm_pro_kiste=80)
        inv = _wareneingang(client, sorte, lort)
        _korrektur(client, inv["id"], 0)
        vorher = _anzahl_wachstumschargen()

        r = _aussaat(client, _chargen(client, sorte)[0]["id"], 10)

        assert r.status_code == 400, r.text
        assert _anzahl_wachstumschargen() == vorher, "Keine Wachstumscharge bei gescheiterter Abbuchung"
        assert _lagermenge_kg(inv["id"]) == Decimal("0")

    def test_platzhalter_ist_nicht_aussaebar(self, client):
        """Review Focus 5."""
        sorte = _sorte(client, gramm_pro_kiste=80)
        platzhalter = _platzhalter_charge(sorte)
        r = _aussaat(client, platzhalter, 1)
        assert r.status_code == 400, r.text

    def test_ohne_saatgutdichte_wird_nicht_abgebucht(self, client):
        lort = _lagerort(client)
        sorte = _sorte(client, gramm_pro_kiste=None)
        inv = _wareneingang(client, sorte, lort)

        r = _aussaat(client, _chargen(client, sorte)[0]["id"], 10)

        assert r.status_code in (200, 201), r.text
        assert _lagermenge_kg(inv["id"]) == Decimal("10")
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261002.py::TestAbbuchungBeimAussaeen -v`
Erwartet: die ersten vier FAIL (heute wird nie abgebucht, also weder Minderung noch 400). `test_ohne_saatgutdichte_wird_nicht_abgebucht` ist bereits grün — er sichert das Bestandsverhalten.

- [ ] **Step 3: Abbuchung in `create_grow_batch`**

In `backend/app/api/v1/production.py`, `create_grow_batch`: direkt nach `db.add(grow_batch)` und **vor** dem Capacity-Block und `db.commit()`:

```python
    # Normale Sorte: verbrauchtes Saatgut abbuchen. Mischsorten bucht
    # mische_charge bereits ab. Scheitert die Abbuchung, entsteht keine
    # Wachstumscharge — daher vor dem Commit und mit Rollback.
    if data.seed_batch_id and seed.saatgut_pro_einheit_gramm:
        from app.services.inventory_service import InventoryService
        bedarf_g = Decimal(str(data.tray_anzahl)) * Decimal(str(seed.saatgut_pro_einheit_gramm))
        db.flush()  # grow_batch.id für den Bewegungsbeleg
        try:
            if seed_batch.bestaende:
                bestand = next(
                    (b for b in seed_batch.bestaende
                     if b.is_active and not b.is_blocked
                     and Decimal(str(b.current_quantity_kg)) * 1000 >= bedarf_g),
                    None,
                )
                if bestand is None:
                    raise ValueError(
                        f"Nicht genug Saatgut in Charge {seed_batch.charge_nummer}: "
                        f"benötigt {bedarf_g} g, verfügbar {seed_batch.verfuegbar_gramm} g"
                    )
                InventoryService(db).consume_seed_for_sowing(
                    seed_inventory_id=bestand.id,
                    quantity_kg=bedarf_g / 1000,
                    grow_batch_id=grow_batch.id,
                )
            else:
                rest = Decimal(str(seed_batch.verbleibend_gramm or 0))
                if rest < bedarf_g:
                    raise ValueError(
                        f"Nicht genug Saatgut in Charge {seed_batch.charge_nummer}: "
                        f"benötigt {bedarf_g} g, verfügbar {rest} g"
                    )
                seed_batch.verbleibend_gramm = rest - bedarf_g
        except ValueError as fehler:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(fehler))
```

`Decimal` oben importieren, falls nötig. Den Mischsorten-Zweig nicht anfassen.

- [ ] **Step 4: Grün bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261002.py -v`
Erwartet: alle Tests aus Task 1–4 passed.

- [ ] **Step 5: Vollauf gegen die Baseline**

Erwartet: dieselben 15 Fehlernamen. **Besonders auf `test_growroom_kapazitaet.py`, `test_gernot_260824.py` und `test_harvest_stueck.py` achten** — sie säen Chargen aus. Deren Sorten haben keine Saatgutdichte und werden deshalb nicht abgebucht; schlägt dort trotzdem etwas fehl, ist das ein inhaltlicher Befund: stoppen und melden.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/production.py backend/tests/test_gernot_261002.py
git commit -m "feat(aussaat): verbrauchtes Saatgut wird beim Aussäen abgebucht"
```

---

### Task 5: Die Inventarlisten sind vollständig und stabil sortiert

**Files:**
- Modify: `backend/app/api/v1/inventory.py` (`list_seed_inventory` und der `GET "/packaging"`-Handler)
- Modify: `frontend/src/services/api.ts:822-823` (`listSeedInventory`) sowie die Listenmethoden für Fertigware und Verpackung
- Modify: `frontend/src/pages/Inventory.tsx:74-111`
- Test: `backend/tests/test_gernot_261002.py`

**Interfaces:**
- Produces: `GET /inventory/seeds` liefert neueste Bestände zuerst (`created_at` absteigend, dann `id`).

- [ ] **Step 1: Failing Tests**

```python
class TestInventarliste:
    """Fehler 2: neue Wareneingänge fielen bei 'Alle Lagerorte' hinten ab."""

    def test_neuester_eingang_steht_vorn(self, client):
        lort = _lagerort(client)
        sorte = _sorte(client)
        for i in range(25):
            _wareneingang(client, sorte, lort, charge=f"ALT-{i:02d}")
        neu = _wareneingang(client, sorte, lort, charge="B20115")

        r = client.get("/api/v1/inventory/seeds")
        assert r.status_code == 200, r.text
        assert r.json()[0]["id"] == neu["id"]

    def test_volle_liste_mit_seitengroesse_100(self, client):
        lort = _lagerort(client)
        sorte = _sorte(client)
        for i in range(30):
            _wareneingang(client, sorte, lort, charge=f"L-{i:02d}")

        r = client.get("/api/v1/inventory/seeds", params={"page_size": 100})
        assert len(r.json()) == 30
```

- [ ] **Step 2: Rot bestätigen.** `test_neuester_eingang_steht_vorn` FAILS — ohne Sortierung steht der neueste hinten bzw. fehlt auf Seite 1.

- [ ] **Step 3: Sortierung**

In `list_seed_inventory` vor `offset`/`limit`:

```python
    # Neueste zuerst: ein frischer Wareneingang muss oben erscheinen und darf
    # nie von der Seitengrenze verschluckt werden. Ohne ORDER BY lieferte
    # SQLite die Einfügereihenfolge, und Neues fiel hinten ab.
    query = query.order_by(SeedInventory.created_at.desc(), SeedInventory.id)
```

Im `GET "/packaging"`-Handler analog eine stabile Sortierung ergänzen (nach Name, dann `id`).

- [ ] **Step 4: Frontend fordert die volle Liste an und warnt bei Kürzung**

In `frontend/src/services/api.ts` den Parametertyp von `listSeedInventory` (und den Listenmethoden für Fertigware und Verpackung) um `page_size?: number` erweitern.

In `frontend/src/pages/Inventory.tsx` die drei Bestandsabfragen (Zeilen ~74-111) jeweils mit `page_size: 100` aufrufen und eine Konstante ergänzen:

```tsx
  // Die Bestandslisten laden bis zu 100 Zeilen. Kommen exakt 100 zurück, ist
  // die Liste womöglich gekürzt — das muss sichtbar sein, nicht still passieren.
  const LISTENGRENZE = 100;
```

Über jeder der drei Tabellen, wenn die jeweilige Liste exakt `LISTENGRENZE` Einträge hat:

```tsx
        <p className="mb-2 text-sm text-amber-700 dark:text-amber-300">
          Es werden die neuesten {LISTENGRENZE} Einträge angezeigt. Bitte nach Lagerort filtern, um alle zu sehen.
        </p>
```

- [ ] **Step 5: Grün bestätigen** — Backend-Tests passed, `cd frontend && npm run build` ohne TypeScript-Fehler.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/inventory.py backend/tests/test_gernot_261002.py \
        frontend/src/services/api.ts frontend/src/pages/Inventory.tsx
git commit -m "fix(lager): Bestandslisten verschluckten neue Wareneingänge an der Seitengrenze"
```

---

### Task 6: Das Aussaat-Formular zeigt Fehler als Fehler

**Files:**
- Modify: `frontend/src/components/domain/SowingForm.tsx:67-71` (Abfrage) und `:260-265` (Hinweis)

- [ ] **Step 1: Fehlerzustand aus der Abfrage lesen**

```tsx
  const {
    data: seedBatches = [],
    isError: chargenFehler,
    error: chargenFehlerDetail,
    isLoading: chargenLaden,
  } = useQuery({
    queryKey: ['seed-batches', formData.seed_id],
    queryFn: () => seedsApi.listBatches(formData.seed_id),
    enabled: !!formData.seed_id && !istMix,
  });
```

- [ ] **Step 2: Drei Zustände statt einem**

Den bisherigen Block bei Zeile ~260 (`batchOptions.length === 0` → „keine Saatgut-Charge") ersetzen. Ein Serverfehler darf nie als „keine Charge im Lager" erscheinen — genau das hat Gernot dazu gebracht, Borretsch doppelt zu erfassen:

```tsx
      {!istMix && formData.seed_id && chargenFehler && (
        <div className="text-sm text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/20 p-3 rounded border border-red-200 dark:border-red-800">
          Die Saatgut-Chargen konnten nicht geladen werden.
          {(chargenFehlerDetail as any)?.response?.data?.detail
            ? ` (${(chargenFehlerDetail as any).response.data.detail})`
            : ''}
          {' '}Bitte nicht erneut einbuchen, sondern den Fehler melden.
        </div>
      )}
      {!istMix && formData.seed_id && !chargenFehler && !chargenLaden && batchOptions.length === 0 && (
        <div className="text-sm text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/20 p-3 rounded border border-amber-200 dark:border-amber-800">
          ⚠️ Für diese Sorte ist noch keine Saatgut-Charge im Lager.
          Bitte erst unter <b>Lager → Wareneingang Saatgut</b> eine Charge erfassen.
        </div>
      )}
```

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build` — ohne TypeScript-Fehler.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/domain/SowingForm.tsx
git commit -m "fix(aussaat): Ladefehler erschien als 'keine Saatgut-Charge im Lager'"
```

---

## Abnahme

Fertig ist der Plan, wenn alle zutreffen:

1. `test_gernot_261002.py` vollständig grün; Vollauf zeigt dieselben 15 Fehlernamen wie die Baseline.
2. `GET /seeds/{id}/batches` liefert für eine Sorte mit Import-Platzhalter 200.
3. Gernots `B20115`-Fall: zwei Chargen, die korrigierte zeigt 0 g.
4. Aussaat von 10 Kisten à 80 g mindert den verknüpften Bestand um 0,8 kg; zu wenig Bestand → 400 ohne neue Wachstumscharge.
5. `GET /inventory/seeds` liefert den neuesten Eingang zuerst.
6. `npm run build` ohne Fehler.

**Nach dem Deploy (nicht Teil dieses Plans):** Rückfüllung in Produktion prüfen — erwartet sind 30 verknüpfte Bestände (16 direkt, 14 per Zeitstempel) und 18 Platzhalter ohne Bestand, `zu_weit_auseinander` = 0. Weicht das ab, Logausgabe `[saatgut] Rückfüllung` lesen, bevor Gernot sät.
