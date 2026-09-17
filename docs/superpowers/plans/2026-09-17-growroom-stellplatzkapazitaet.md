# Growroom-Stellplatzkapazität — Implementation Plan

> **For agentic workers:** Diesen Plan Task für Task abarbeiten. Schritte nutzen Checkbox-Syntax (`- [ ]`). Kein Task wird übersprungen oder zusammengefasst; wenn ein Schritt nicht funktioniert, melden statt umplanen.

**Goal:** Die Kapazitätsübersicht zeigt die tatsächliche Belegung der Growroom-Regale in Kisten, ohne dass beim Umräumen Regalplätze nachgepflegt werden müssen.

**Architecture:** Belegung wird **berechnet, nicht gezählt.** Es gibt keinen Zähler, der hoch- und runtergebucht wird — ein solcher Zähler driftet bei jedem Abbruch, Doppelklick oder Import auseinander. Stattdessen ergibt sich die Belegung jederzeit aus den Chargendaten: Eine Charge belegt Stellplätze, sobald sie im Growroom steht (Status `WACHSTUM` oder `ERNTEREIF`), und zwar so viele, wie sie Kisten hat abzüglich der bereits entnommenen. Dafür braucht die Ernte ein einziges neues Feld: wie viele Kisten sie geleert hat. Die Gesamtzahl der Stellplätze liegt als `Capacity`-Datensatz in der bestehenden Kapazitätstabelle.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 (Mapped/mapped_column), SQLite pro Mandant, React + TypeScript, TanStack Query, Tailwind.

**Spec:** Anforderung „Stellplatzkapazität im Growroom anhand der tatsächlichen Belegung erfassen", Gernot Kleinberger, 17.09.2026.

## Global Constraints

- **Testumgebung:** Ausschließlich `/Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python`. Vollauf: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py`
- **Test-Baseline: 15 failed / 457 passed / 2 skipped / 1 error.** Nach jeder Änderung die *Liste* der Fehlernamen vergleichen, nicht die Zahl.
- **Migrationen laufen über `tenancy._auto_migrate()`, NICHT über Alembic.** Die Alembic-Revisionen unter `backend/alembic/versions/` sind Legacy aus der Postgres-Ära. Eine neue Spalte, die nur dort landet, erreicht die Produktiv-Mandanten (minga, demo) **nie** und erzeugt nach dem Deploy „no such column"-Fehler. Task 1 Step 2 ist deshalb nicht optional.
- **SQLite kann NOT NULL nicht nachrüsten.** Jede neue Spalte ist nullable oder hat einen DEFAULT.
- **Sprache:** UI-Texte, Fehlermeldungen und Commits auf Deutsch. Gernots Vokabular übernehmen: „Kiste", „Stellplatz", „Growroom", „Keimung".
- **Bestandsdaten nicht verfälschen.** Es gibt bereits importierte Alt-Chargen (`source = 'import'`). Die neue Spalte bleibt bei ihnen leer; die Berechnung muss damit umgehen, ohne zu raten.

---

### Task 1: Ernte erfasst, wie viele Kisten sie geleert hat

Heute erfasst `Harvest` Gramm und Stück (`menge_gramm`, `menge_stueck`, `stueck_pro_kiste`), aber nirgends die Kistenzahl. Ohne sie ist Gernots Teilmengen-Fall („8 von 20 Kisten geerntet") nicht abbildbar.

**Files:**
- Modify: `backend/app/models/production.py:105-135` (Harvest-Modell)
- Modify: `backend/app/tenancy.py:284-292` (`_auto_migrate`)
- Modify: `backend/app/schemas/production.py:104-122` (`HarvestCreate`, `HarvestResponse`)
- Modify: `backend/app/api/v1/production.py:303-332` (`create_harvest` — inklusive Ersetzung des unbedingten `GEERNTET`-Blocks in Zeile 314-328)
- Test: `backend/tests/test_growroom_kapazitaet.py` (neu)

**Interfaces:**
- Produces: `Harvest.entleerte_kisten: Optional[int]` — Anzahl der durch diese Ernte geleerten Kisten. `None` bei Alt- und Importdaten. Task 2 rechnet damit.

- [ ] **Step 1: Spalte ins Modell**

In `backend/app/models/production.py`, Klasse `Harvest`, direkt nach `stueck_pro_kiste` (ca. Zeile 132):

```python
    # Wie viele Kisten diese Ernte im Growroom geleert hat. Steuert die
    # Freigabe von Stellplätzen. None bei Alt- und Importdaten — dort ist
    # die Kistenzahl nicht rekonstruierbar.
    entleerte_kisten: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
```

- [ ] **Step 2: `_auto_migrate` ergänzen — sonst bricht Prod nach dem Deploy**

In `backend/app/tenancy.py` zu den bestehenden `_add_col_if_missing`-Aufrufen (ca. Zeile 292):

```python
        _add_col_if_missing("harvests", "entleerte_kisten", "INTEGER")
```

Kein DEFAULT: `NULL` bedeutet hier „unbekannt" und ist von „0 Kisten geleert" fachlich zu unterscheiden.

- [ ] **Step 3: Schema erweitern**

In `backend/app/schemas/production.py`, `HarvestCreate` (ca. Zeile 104):

```python
    entleerte_kisten: Optional[int] = Field(
        None, ge=0,
        description="Wie viele Kisten diese Ernte im Growroom geleert hat. "
                    "Leer = alle noch belegten Kisten der Charge.",
    )
```

Und in `HarvestResponse` (ca. Zeile 118):

```python
    entleerte_kisten: Optional[int] = None
```

- [ ] **Step 4: Failing Test schreiben**

Neue Datei `backend/tests/test_growroom_kapazitaet.py`:

```python
"""Growroom-Stellplatzkapazität — Anforderung Gernot vom 17.09.2026.

Kisten belegen Stellplätze erst ab dem Transfer in den Growroom und geben
sie bei Ernte oder Auslagerung wieder frei, auch in Teilmengen.
"""
from datetime import date, timedelta

import pytest


def _sorte(client, name="Erbse"):
    r = client.post("/api/v1/seeds", json={
        "name": name, "keimdauer_tage": 2, "wachstumsdauer_tage": 8,
        "erntefenster_min_tage": 9, "erntefenster_optimal_tage": 11,
        "erntefenster_max_tage": 14, "ertrag_gramm_pro_tray": 350,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _saatgut_charge(client, seed, nummer="CH-1", gramm="5000"):
    """Echte SeedBatch. NICHT /inventory/seeds/receive nehmen — das liefert
    einen Bestandssatz, dessen ID die Aussaat mit 404 'Saatgut-Charge nicht
    gefunden' ablehnt. Pflichtfelder heißen charge_nummer und menge_gramm."""
    r = client.post("/api/v1/seeds/batches", json={
        "seed_id": seed["id"], "charge_nummer": nummer, "menge_gramm": gramm,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _charge(client, trays=20):
    """Aussaat mit `trays` Kisten, Status KEIMUNG.

    `seed_id` statt `seed_batch_id` funktioniert NUR bei Mischsorten — eine
    normale Sorte quittiert das mit 400 "ist keine Mischsorte".
    """
    seed = _sorte(client)
    saatgut = _saatgut_charge(client, seed)
    r = client.post("/api/v1/production/grow-batches", json={
        "seed_batch_id": saatgut["id"],
        "tray_anzahl": trays,
        "aussaat_datum": date.today().isoformat(),
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


class TestKistenFreigabe:
    """Die Ernte gibt Kisten frei — ganz oder teilweise."""

    def test_ernte_ohne_angabe_leert_alle_kisten(self, client):
        charge = _charge(client, trays=20)
        client.post(f"/api/v1/production/grow-batches/{charge['id']}/status/WACHSTUM")

        r = client.post("/api/v1/production/harvests", json={
            "grow_batch_id": charge["id"],
            "ernte_datum": date.today().isoformat(),
            "menge_gramm": "4200",
        })
        assert r.status_code in (200, 201), r.text
        assert r.json()["entleerte_kisten"] == 20

    def test_teilernte_leert_nur_die_angegebenen_kisten(self, client):
        charge = _charge(client, trays=20)
        client.post(f"/api/v1/production/grow-batches/{charge['id']}/status/WACHSTUM")

        r = client.post("/api/v1/production/harvests", json={
            "grow_batch_id": charge["id"],
            "ernte_datum": date.today().isoformat(),
            "menge_gramm": "1680",
            "entleerte_kisten": 8,
        })
        assert r.status_code in (200, 201), r.text
        assert r.json()["entleerte_kisten"] == 8

    def test_zwei_teilernten_rechnen_aufeinander_auf(self, client):
        """Fängt die Lazy-Loading-Falle: wird batch.harvests nicht geladen,
        ergibt die Summe still 0 und die zweite Ernte darf zu viel entnehmen."""
        charge = _charge(client, trays=20)
        client.post(f"/api/v1/production/grow-batches/{charge['id']}/status/WACHSTUM")

        for kisten in (8, 7):
            r = client.post("/api/v1/production/harvests", json={
                "grow_batch_id": charge["id"],
                "ernte_datum": date.today().isoformat(),
                "menge_gramm": "1400", "entleerte_kisten": kisten,
            })
            assert r.status_code in (200, 201), r.text

        # 20 - 8 - 7 = 5 übrig; 6 müssen abgelehnt werden.
        r = client.post("/api/v1/production/harvests", json={
            "grow_batch_id": charge["id"],
            "ernte_datum": date.today().isoformat(),
            "menge_gramm": "1200", "entleerte_kisten": 6,
        })
        assert r.status_code == 400, r.text
        assert "5" in r.json()["detail"]

    def test_charge_bleibt_nach_teilernte_im_growroom(self, client):
        """Regression gegen das unbedingte GEERNTET in create_harvest."""
        charge = _charge(client, trays=20)
        client.post(f"/api/v1/production/grow-batches/{charge['id']}/status/WACHSTUM")
        client.post("/api/v1/production/harvests", json={
            "grow_batch_id": charge["id"],
            "ernte_datum": date.today().isoformat(),
            "menge_gramm": "1680", "entleerte_kisten": 8,
        })

        status = client.get(f"/api/v1/production/grow-batches/{charge['id']}").json()["status"]
        assert status != "GEERNTET", "Teilgeerntete Charge steht weiter im Growroom"

    def test_letzte_kiste_beendet_die_charge(self, client):
        charge = _charge(client, trays=20)
        client.post(f"/api/v1/production/grow-batches/{charge['id']}/status/WACHSTUM")
        for kisten in (8, 12):
            client.post("/api/v1/production/harvests", json={
                "grow_batch_id": charge["id"],
                "ernte_datum": date.today().isoformat(),
                "menge_gramm": "1680", "entleerte_kisten": kisten,
            })

        status = client.get(f"/api/v1/production/grow-batches/{charge['id']}").json()["status"]
        assert status == "GEERNTET"

    def test_mehr_kisten_als_vorhanden_wird_abgelehnt(self, client):
        charge = _charge(client, trays=20)
        client.post(f"/api/v1/production/grow-batches/{charge['id']}/status/WACHSTUM")

        r = client.post("/api/v1/production/harvests", json={
            "grow_batch_id": charge["id"],
            "ernte_datum": date.today().isoformat(),
            "menge_gramm": "4200",
            "entleerte_kisten": 25,
        })
        assert r.status_code == 400, r.text
        assert "20" in r.json()["detail"]
```

Die Tests brauchen nur die `client`-Fixture, keine Lagerort-Fixture — die Aussaat hängt an der Saatgut-Charge, nicht am Bestand. Die gesamte Kette (Sorte → `/seeds/batches` → `/production/grow-batches` → `status/WACHSTUM` → `/harvests`) wurde am 17.09.2026 gegen die echte App durchgespielt und liefert 201/201/200/200.

- [ ] **Step 5: Tests laufen lassen, Fehlschlag bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_growroom_kapazitaet.py -v`
Erwartet: alle sechs FAIL — `entleerte_kisten` fehlt in der Antwort, wird nicht validiert, und `test_charge_bleibt_nach_teilernte_im_growroom` scheitert am unbedingten `GEERNTET`.

- [ ] **Step 6: Endpunkt implementieren**

**Das ist der heikelste Schritt des Plans.** `create_harvest` (`backend/app/api/v1/production.py:303-332`) setzt heute bei **jeder** Ernte den Chargenstatus hart auf `GEERNTET`:

```python
    batch = db.get(GrowBatch, data.grow_batch_id)
    if batch and batch.status != GrowBatchStatus.GEERNTET:
        # Markiere Charge als geerntet (vereinfachte Annahme: eine Ernte pro Charge)
        batch.status = GrowBatchStatus.GEERNTET
```

Am 17.09.2026 gegen die echte App gemessen: Charge mit 20 Kisten → `status/WACHSTUM` → Teilernte über 1680 g → **Status danach `GEERNTET`**. Bliebe diese Zeile stehen, fiele die Charge sofort aus dem Filter des neuen Service und die Belegung stürzte nach Gernots Teilernte von 0 auf … 0 statt auf 12. Die Kernanforderung wäre unerfüllbar, obwohl alle neuen Dateien korrekt aussähen.

Der ganze Block wird ersetzt. Beachte die Reihenfolge: die Charge muss **vor** dem Anlegen der Ernte geladen werden, heute passiert das danach.

```python
    batch = db.get(GrowBatch, data.grow_batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Wachstumscharge nicht gefunden")

    # Wie viele Kisten dieser Charge stehen noch im Growroom?
    bereits_entleert = sum(h.entleerte_kisten or 0 for h in batch.harvests)
    verbleibend = max(0, (batch.tray_anzahl or 0) - bereits_entleert)

    entleerte = data.entleerte_kisten
    if entleerte is None:
        # Keine Angabe = die Charge wird vollständig abgeerntet (bisheriges Verhalten).
        entleerte = verbleibend
    elif entleerte > verbleibend:
        raise HTTPException(
            status_code=400,
            detail=f"Die Charge hat nur noch {verbleibend} Kisten im Growroom, "
                   f"{entleerte} wurden angegeben.",
        )

    payload = data.model_dump()
    notizen = payload.pop("notizen", None)
    payload["entleerte_kisten"] = entleerte
    harvest = Harvest(**payload, quality_notes=notizen)
    db.add(harvest)

    # Status erst wechseln, wenn wirklich nichts mehr im Growroom steht.
    # Vorher stand hier ein unbedingtes GEERNTET mit dem Kommentar
    # "vereinfachte Annahme: eine Ernte pro Charge" — genau diese Annahme
    # bricht bei Teilernten.
    if verbleibend - entleerte <= 0 and batch.status != GrowBatchStatus.GEERNTET:
        batch.status = GrowBatchStatus.GEERNTET

        # Alt-Verhalten unverändert: der regalbezogene Zähler wird weiterhin
        # genau einmal je Charge freigegeben, nämlich beim vollständigen Abernten.
        if batch.regal_position:
            cap = db.execute(
                select(Capacity).where(
                    Capacity.name == batch.regal_position,
                    Capacity.ressource_typ == ResourceType.REGAL,
                )
            ).scalar_one_or_none()
            if cap:
                cap.aktuell_belegt = max(0, (cap.aktuell_belegt or 0) - batch.tray_anzahl)
```

Zwei Dinge, die der Worker wissen muss:

- `batch.harvests` muss beim Summieren wirklich geladen sein. Eine Summe über eine leere Lazy-Collection ergibt still 0 und damit eine zu hohe Restmenge. Im Zweifel die Ernten explizit nachladen und das im Test mit **zwei aufeinanderfolgenden Teilernten** absichern.
- Dieser `Capacity`-Satz wird über `batch.regal_position` gefunden, der Growroom-Satz aus Task 2 über den Namen `"Growroom"`. Das sind verschiedene Zeilen und dürfen es bleiben. Ein Regalplatz darf deshalb **niemals** „Growroom" heißen — sonst zieht die Altlogik am selben Datensatz, den die neue Berechnung nur liest.

- [ ] **Step 7: Tests grün bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_growroom_kapazitaet.py -v`
Erwartet: 6 passed.

- [ ] **Step 8: Gesamtsuite gegen die Baseline**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py`
Erwartet: dieselben 15 Altlast-Namen, keine neuen. Besonders auf `test_harvest_stueck.py` und `test_import_chargen.py` achten — beide legen Ernten an.

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/production.py backend/app/tenancy.py backend/app/schemas/production.py backend/app/api/v1/production.py backend/tests/test_growroom_kapazitaet.py
git commit -m "feat(growroom): Ernte erfasst die Anzahl geleerter Kisten"
```

---

### Task 2: Belegung berechnen und als Übersicht ausliefern

**Files:**
- Create: `backend/app/services/growroom_capacity_service.py`
- Modify: `backend/app/api/v1/production.py` (zwei Endpunkte)
- Test: `backend/tests/test_growroom_kapazitaet.py` (erweitern)

**Interfaces:**
- Consumes: `Harvest.entleerte_kisten` aus Task 1
- Produces:
  - `growroom_capacity_service.belegte_stellplaetze(db) -> int`
  - `growroom_capacity_service.kapazitaets_uebersicht(db) -> dict` mit `{"gesamt": int | None, "belegt": int, "frei": int | None}`
  - `GET /api/v1/production/growroom-capacity` → dieses dict
  - `PUT /api/v1/production/growroom-capacity` mit Body `{"gesamt": int}` → dasselbe dict

- [ ] **Step 1: Failing Test schreiben**

An `backend/tests/test_growroom_kapazitaet.py` anhängen:

```python
class TestKapazitaetsUebersicht:
    """Gernots Beispiel: 20 Kisten, davon 8 entnommen → 12 bleiben belegt."""

    def test_keimung_belegt_keine_stellplaetze(self, client):
        client.put("/api/v1/production/growroom-capacity", json={"gesamt": 100})
        _charge(client, trays=20)  # bleibt in KEIMUNG

        r = client.get("/api/v1/production/growroom-capacity")
        assert r.status_code == 200, r.text
        assert r.json() == {"gesamt": 100, "belegt": 0, "frei": 100}

    def test_transfer_belegt_alle_kisten(self, client):
        client.put("/api/v1/production/growroom-capacity", json={"gesamt": 100})
        charge = _charge(client, trays=20)
        client.post(f"/api/v1/production/grow-batches/{charge['id']}/status/WACHSTUM")

        r = client.get("/api/v1/production/growroom-capacity")
        assert r.json() == {"gesamt": 100, "belegt": 20, "frei": 80}

    def test_teilernte_gibt_nur_entnommene_frei(self, client):
        client.put("/api/v1/production/growroom-capacity", json={"gesamt": 100})
        charge = _charge(client, trays=20)
        client.post(f"/api/v1/production/grow-batches/{charge['id']}/status/WACHSTUM")
        client.post("/api/v1/production/harvests", json={
            "grow_batch_id": charge["id"],
            "ernte_datum": date.today().isoformat(),
            "menge_gramm": "1680", "entleerte_kisten": 8,
        })

        r = client.get("/api/v1/production/growroom-capacity")
        assert r.json() == {"gesamt": 100, "belegt": 12, "frei": 88}

    def test_ohne_hinterlegte_gesamtzahl_bleibt_frei_unbekannt(self, client):
        charge = _charge(client, trays=20)
        client.post(f"/api/v1/production/grow-batches/{charge['id']}/status/WACHSTUM")

        r = client.get("/api/v1/production/growroom-capacity")
        assert r.json() == {"gesamt": None, "belegt": 20, "frei": None}
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_growroom_kapazitaet.py::TestKapazitaetsUebersicht -v`
Erwartet: alle vier FAIL mit 404 — die Endpunkte gibt es noch nicht.

- [ ] **Step 3: Service anlegen**

Neue Datei `backend/app/services/growroom_capacity_service.py`:

```python
"""Stellplatzbelegung im Growroom.

Die Belegung wird bei jedem Aufruf aus den Chargendaten berechnet und
nirgends als Zähler geführt. Ein Zähler würde bei abgebrochenen Ernten,
Doppelklicks und Datenimporten auseinanderdriften; eine Berechnung kann
das nicht.

Eine Charge belegt Stellplätze, solange sie im Growroom steht. Das ist
genau der Zeitraum zwischen dem Transfer aus der Keimung (Status WACHSTUM)
und dem vollständigen Abernten. KEIMUNG belegt nichts, GEERNTET und
VERLUST ebenfalls nicht.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.capacity import Capacity, ResourceType
from app.models.production import GrowBatch, GrowBatchStatus

# Kennung des Kapazitätsdatensatzes für den Growroom.
GROWROOM_NAME = "Growroom"

# Chargen in diesen Status stehen physisch im Growroom.
STATUS_IM_GROWROOM = (GrowBatchStatus.WACHSTUM, GrowBatchStatus.ERNTEREIF)


def belegte_stellplaetze(db: Session) -> int:
    """Summe der Kisten, die aktuell im Growroom stehen."""
    batches = db.execute(
        select(GrowBatch)
        .options(selectinload(GrowBatch.harvests))
        .where(GrowBatch.status.in_(STATUS_IM_GROWROOM))
    ).scalars().all()

    belegt = 0
    for batch in batches:
        entleert = sum(h.entleerte_kisten or 0 for h in batch.harvests)
        belegt += max(0, (batch.tray_anzahl or 0) - entleert)
    return belegt


def get_growroom_capacity(db: Session) -> Optional[Capacity]:
    """Der Kapazitätsdatensatz des Growrooms, falls hinterlegt."""
    return db.execute(
        select(Capacity).where(
            Capacity.ressource_typ == ResourceType.REGAL,
            Capacity.name == GROWROOM_NAME,
        )
    ).scalar_one_or_none()


def set_gesamt(db: Session, gesamt: int) -> Capacity:
    """Legt die Gesamtzahl der Stellplätze fest (legt den Satz bei Bedarf an)."""
    cap = get_growroom_capacity(db)
    if cap is None:
        cap = Capacity(
            ressource_typ=ResourceType.REGAL,
            name=GROWROOM_NAME,
            max_kapazitaet=gesamt,
        )
        db.add(cap)
    else:
        cap.max_kapazitaet = gesamt
    db.commit()
    db.refresh(cap)
    return cap


def kapazitaets_uebersicht(db: Session) -> dict:
    """Gesamt, belegt und frei. `gesamt`/`frei` sind None, solange die
    Gesamtzahl nicht hinterlegt ist — geraten wird nicht."""
    cap = get_growroom_capacity(db)
    belegt = belegte_stellplaetze(db)
    gesamt = cap.max_kapazitaet if cap else None
    return {
        "gesamt": gesamt,
        "belegt": belegt,
        "frei": (gesamt - belegt) if gesamt is not None else None,
    }
```

`aktuell_belegt` auf dem `Capacity`-Satz wird bewusst **nicht** geschrieben. Das Feld existiert im Modell, wäre aber genau der driftende Zähler, den dieser Service vermeidet.

- [ ] **Step 4: Endpunkte anlegen**

In `backend/app/api/v1/production.py` neben den übrigen Endpunkten:

```python
from pydantic import BaseModel, Field as PydanticField

from app.services import growroom_capacity_service


class GrowroomCapacityUpdate(BaseModel):
    gesamt: int = PydanticField(..., ge=0, description="Gesamtzahl der Kistenstellplätze im Growroom")


@router.get("/growroom-capacity")
def read_growroom_capacity(db: DBSession):
    """Stellplätze im Growroom: insgesamt, belegt, frei."""
    return growroom_capacity_service.kapazitaets_uebersicht(db)


@router.put("/growroom-capacity")
def set_growroom_capacity(data: GrowroomCapacityUpdate, db: DBSession):
    """Legt die Gesamtzahl der Kistenstellplätze fest."""
    growroom_capacity_service.set_gesamt(db, data.gesamt)
    return growroom_capacity_service.kapazitaets_uebersicht(db)
```

Importstil an die Datei anpassen — wenn dort Schemas aus `app.schemas.production` kommen, `GrowroomCapacityUpdate` dorthin legen statt in die Router-Datei.

- [ ] **Step 5: Tests grün bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_growroom_kapazitaet.py -v`
Erwartet: 10 passed (6 aus Task 1, 4 neue).

- [ ] **Step 6: Rollen prüfen**

Seit 03.09.2026 werden Rollen grob je Router über `_rollen(...)` in `app/main.py` durchgesetzt. Prüfen, welche Rollen der Production-Router hat, und bestätigen, dass Produktionsmitarbeiter die Kapazitätsübersicht lesen dürfen — sie ist für die Halle gedacht. Ist der Router für sie gesperrt, **melden statt die Matrix eigenmächtig ändern.**

- [ ] **Step 7: Gesamtsuite gegen die Baseline**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py`
Erwartet: dieselben 15 Altlast-Namen.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/growroom_capacity_service.py backend/app/api/v1/production.py backend/tests/test_growroom_kapazitaet.py
git commit -m "feat(growroom): Stellplatzbelegung berechnen und als Übersicht ausliefern"
```

---

### Task 3: Oberfläche — Übersicht, Kistenfeld, optionaler Regalplatz

**Files:**
- Modify: `frontend/src/services/api.ts` (zwei Methoden)
- Modify: die Ernte-Erfassung (`HarvestForm`, aus der Konsolidierung von drei Erfassungswegen entstanden — vor dem Ändern mit `grep -rl "harvests" frontend/src` den tatsächlichen Pfad bestimmen)
- Modify: die Produktions-/Dashboard-Seite, auf der die Übersicht erscheint
- Modify: das Aussaat-Formular (Regalplatz)

**Interfaces:**
- Consumes: `GET`/`PUT /production/growroom-capacity` aus Task 2

- [ ] **Step 1: API-Methoden ergänzen**

In `frontend/src/services/api.ts` beim Produktions-Client:

```ts
  getGrowroomCapacity: () =>
    api.get<{ gesamt: number | null; belegt: number; frei: number | null }>(
      '/production/growroom-capacity'
    ).then(r => r.data),

  setGrowroomCapacity: (gesamt: number) =>
    api.put<{ gesamt: number | null; belegt: number; frei: number | null }>(
      '/production/growroom-capacity', { gesamt }
    ).then(r => r.data),
```

- [ ] **Step 2: Kistenfeld in die Ernte-Erfassung**

Das Feld wird mit den noch belegten Kisten der Charge vorbelegt, damit der Normalfall (ganze Charge abernten) ohne Eingabe funktioniert und nur die Teilernte korrigiert werden muss:

```tsx
                <label className="block">
                    <span className="text-sm font-medium">Entleerte Kisten</span>
                    <input
                        type="number"
                        min={0}
                        max={verbleibendeKisten}
                        value={entleerteKisten}
                        onChange={(e) => setEntleerteKisten(Number(e.target.value))}
                        className="input mt-1"
                    />
                    <span className="mt-1 block text-xs text-gray-500">
                        {verbleibendeKisten} Kisten stehen noch im Growroom.
                        Bei Teilernte die tatsächlich entnommene Anzahl eintragen.
                    </span>
                </label>
```

`verbleibendeKisten` kommt aus der Charge: `tray_anzahl` minus die Summe der `entleerte_kisten` ihrer bisherigen Ernten. Liefert die Chargen-Antwort die Ernten nicht mit, den Wert dort ergänzen lassen — **nicht** im Frontend schätzen.

- [ ] **Step 3: Kapazitätsübersicht anzeigen**

Drei Zahlen, wie in der Anforderung benannt. Kein Diagramm, kein Regallayout — Gernot hat ausdrücklich Stellplatzzahlen verlangt, keine Positionen:

```tsx
    const { data: kapazitaet } = useQuery({
        queryKey: ['growroom-capacity'],
        queryFn: productionApi.getGrowroomCapacity,
    });

    // ...

    <div className="card">
        <h3 className="text-sm font-medium text-gray-500">Stellplätze Growroom</h3>
        {kapazitaet?.gesamt === null ? (
            <p className="mt-2 text-sm text-gray-500">
                {kapazitaet.belegt} Kisten belegt. Gesamtzahl der Stellplätze noch nicht hinterlegt.
            </p>
        ) : (
            <div className="mt-2 flex gap-6">
                <div>
                    <div className="text-2xl font-semibold">{kapazitaet?.gesamt}</div>
                    <div className="text-xs text-gray-500">insgesamt</div>
                </div>
                <div>
                    <div className="text-2xl font-semibold">{kapazitaet?.belegt}</div>
                    <div className="text-xs text-gray-500">belegt</div>
                </div>
                <div>
                    <div className="text-2xl font-semibold text-green-700">{kapazitaet?.frei}</div>
                    <div className="text-xs text-gray-500">frei</div>
                </div>
            </div>
        )}
    </div>
```

Nach einer erfassten Ernte und nach einem Statuswechsel `queryClient.invalidateQueries({ queryKey: ['growroom-capacity'] })` auslösen, sonst steht eine veraltete Zahl auf dem Tablet.

- [ ] **Step 4: Gesamtzahl hinterlegbar machen**

Ein Zahlenfeld mit Speichern-Button, das `setGrowroomCapacity` ruft — in den Einstellungen oder direkt an der Übersicht. Die Zahl ändert sich selten; ein aufwändiger Dialog ist unnötig.

- [ ] **Step 5: Regalplatz bei der Aussaat optional**

Gernot: „Ein genauer Regalplatz muss noch nicht zugeordnet werden." `GrowBatch.regal_position` ist im Modell bereits `Optional`. Im Aussaat-Formular prüfen, ob das Feld als Pflichtfeld markiert ist (`required`, Validierung, Sternchen im Label). Falls ja: optional machen und mit „(optional)" beschriften. Das Feld wird **nicht entfernt** — die genaue Zuordnung soll laut Anforderung weiterhin möglich sein.

- [ ] **Step 6: Gernots Beispiel im Browser durchspielen**

`cd frontend && npm run build` muss sauber sein. Dann:

1. Gesamtzahl der Stellplätze hinterlegen.
2. Aussaat mit 20 Kisten anlegen, **ohne** Regalplatz → Übersicht zeigt weiterhin 0 belegt.
3. Charge in den Growroom transferieren (Status WACHSTUM) → 20 belegt.
4. Ernte mit 8 entleerten Kisten erfassen → 12 belegt, freie Plätze entsprechend gestiegen.
5. Restliche 12 ernten → 0 belegt.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "feat(growroom): Stellplatzübersicht, Kistenfeld in der Ernte, Regalplatz optional"
```

---

## Abnahme

1. Eine Aussaat in der Keimung belegt 0 Stellplätze, auch ohne Regalplatz.
2. Der Transfer von 20 Kisten in den Growroom belegt 20 Stellplätze.
3. Eine Ernte von 8 Kisten gibt 8 Stellplätze frei, 12 bleiben belegt.
4. Umräumen innerhalb des Growrooms verändert die Belegung nicht — es gibt keinen Pfad, auf dem eine Positionsänderung die Zahl anfasst.
5. Die Übersicht zeigt insgesamt / belegt / frei.
6. Die Gesamtsuite zeigt dieselben 15 Altlast-Fehler wie die Baseline.

**Bewusste Grenze dieser Lösung:** Stellplätze werden über die Ernte freigegeben. Die Anforderung nennt „Ernte **oder** Transfer in die Kühlung" — solange beides derselbe Arbeitsgang ist (schneiden und wegstellen), deckt die Ernteerfassung beide Fälle ab. Sollte Gernot Kisten regelmäßig *ungeerntet* in die Kühlung stellen, fehlt dafür ein eigener Auslager-Schritt; das ist dann eine Folgeanforderung und kein Fehler dieser Umsetzung. Bei der Abnahme mit ihm ausdrücklich ansprechen.

**Vor dem Deploy zwingend:** Backup des Mandanten `minga` über die SQLite-Backup-API im Container ziehen (nicht `docker cp` der `.db` — die Datei allein ist wegen WAL wochenalt), mit `PRAGMA integrity_check` verifizieren. Erst danach deployen, damit `_auto_migrate` die neue Spalte anlegt.
