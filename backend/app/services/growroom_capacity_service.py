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
