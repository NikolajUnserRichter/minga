"""Verknüpft Altbestände mit ihrer Saatgut-Charge.

Nur Bestände ohne Verknüpfung werden angefasst. Kandidaten haben dieselbe
Sorte und Chargennummer und gehören noch keinem anderen Bestand. Bei
mehreren Kandidaten gewinnt der zeitlich nächste innerhalb von fünf Sekunden:
Wareneingang und Charge entstanden im selben Request.
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


def _utc(timestamp: datetime) -> datetime:
    return timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)


def verknuepfe_saatgutbestaende(db: Session) -> dict:
    ergebnis = {"verknuepft": 0, "mehrdeutig_per_zeit": 0, "ohne_charge": 0, "zu_weit_auseinander": 0}

    vergeben = set(db.execute(
        select(SeedInventory.seed_batch_id).where(SeedInventory.seed_batch_id.is_not(None))
    ).scalars())

    offen = db.execute(
        select(SeedInventory).where(SeedInventory.seed_batch_id.is_(None)).order_by(SeedInventory.created_at)
    ).scalars().all()

    for bestand in offen:
        kandidaten = [
            charge for charge in db.execute(
                select(SeedBatch).where(
                    SeedBatch.seed_id == bestand.seed_id,
                    SeedBatch.charge_nummer == bestand.batch_number,
                )
            ).scalars()
            if charge.id not in vergeben
        ]
        if not kandidaten:
            ergebnis["ohne_charge"] += 1
            continue

        naechste = min(kandidaten, key=lambda charge: abs(_utc(charge.created_at) - _utc(bestand.created_at)))
        if abs(_utc(naechste.created_at) - _utc(bestand.created_at)) > MAX_ABSTAND:
            ergebnis["zu_weit_auseinander"] += 1
            logger.warning(
                "[saatgut] Bestand %s (Charge %s) nicht verknüpft: keine zeitnahe Charge",
                bestand.id, bestand.batch_number,
            )
            continue

        if len(kandidaten) > 1:
            ergebnis["mehrdeutig_per_zeit"] += 1
        bestand.seed_batch_id = naechste.id
        vergeben.add(naechste.id)
        ergebnis["verknuepft"] += 1

    db.flush()
    if any(ergebnis.values()):
        logger.info("[saatgut] Rückfüllung: %s", ergebnis)
    return ergebnis
