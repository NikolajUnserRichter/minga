from typing import Optional
"""
Produktions-Service - Business Logic für Produktion
"""
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.seed import Seed, SeedBatch
from app.models.production import GrowBatch, GrowBatchStatus, Harvest
from app.models.capacity import Capacity, ResourceType


class ProductionService:
    """Service für Produktions-Operationen"""

    def __init__(self, db: Session):
        self.db = db

    def create_grow_batch(
        self,
        seed_batch_id: UUID,
        tray_anzahl: int,
        aussaat_datum: date,
        regal_position: Optional[str] = None,
        notizen: Optional[str] = None
    ) -> GrowBatch:
        """
        Erstellt eine neue Wachstumscharge und berechnet Erntedaten.
        """
        # Seed Batch mit Seed laden
        seed_batch = self.db.execute(
            select(SeedBatch)
            .join(Seed)
            .where(SeedBatch.id == seed_batch_id)
        ).scalar_one_or_none()

        if not seed_batch:
            raise ValueError("Saatgut-Charge nicht gefunden")

        seed = seed_batch.seed

        # Erntedaten berechnen
        keim_ende = aussaat_datum + timedelta(days=seed.keimdauer_tage)
        wachstum_ende = keim_ende + timedelta(days=seed.wachstumsdauer_tage - seed.keimdauer_tage)

        ernte_min = aussaat_datum + timedelta(days=seed.erntefenster_min_tage)
        ernte_optimal = aussaat_datum + timedelta(days=seed.erntefenster_optimal_tage)
        ernte_max = aussaat_datum + timedelta(days=seed.erntefenster_max_tage)

        grow_batch = GrowBatch(
            seed_batch_id=seed_batch_id,
            tray_anzahl=tray_anzahl,
            aussaat_datum=aussaat_datum,
            erwartete_ernte_min=ernte_min,
            erwartete_ernte_optimal=ernte_optimal,
            erwartete_ernte_max=ernte_max,
            status=GrowBatchStatus.KEIMUNG,
            regal_position=regal_position,
            notizen=notizen,
        )

        self.db.add(grow_batch)

        # Kapazität aktualisieren
        self._update_capacity(ResourceType.REGAL, tray_anzahl)

        return grow_batch

    def record_harvest(
        self,
        grow_batch_id: UUID,
        ernte_datum: date,
        menge_gramm: Decimal,
        verlust_gramm: Decimal = Decimal("0"),
        qualitaet_note: Optional[int] = None
    ) -> Harvest:
        """
        Erfasst eine Ernte und aktualisiert den Chargen-Status.
        """
        grow_batch = self.db.get(GrowBatch, grow_batch_id)
        if not grow_batch:
            raise ValueError("Wachstumscharge nicht gefunden")

        harvest = Harvest(
            grow_batch_id=grow_batch_id,
            ernte_datum=ernte_datum,
            menge_gramm=menge_gramm,
            verlust_gramm=verlust_gramm,
            qualitaet_note=qualitaet_note,
        )

        self.db.add(harvest)

        # Status aktualisieren
        grow_batch.status = GrowBatchStatus.ERNTEREIF

        # Kapazität freigeben
        self._update_capacity(ResourceType.REGAL, -grow_batch.tray_anzahl)

        return harvest

    def get_erntereife_chargen(self) -> list[GrowBatch]:
        """
        Gibt alle erntereife Chargen zurück.
        """
        today = date.today()
        return self.db.execute(
            select(GrowBatch)
            .where(
                GrowBatch.erwartete_ernte_min <= today,
                GrowBatch.erwartete_ernte_max >= today,
                GrowBatch.status.in_([GrowBatchStatus.WACHSTUM, GrowBatchStatus.ERNTEREIF])
            )
        ).scalars().all()

    def get_production_summary(self, von: date, bis: date) -> dict:
        """
        Gibt Produktionszusammenfassung für Zeitraum zurück.
        """
        harvests = self.db.execute(
            select(
                func.sum(Harvest.menge_gramm).label("gesamt"),
                func.sum(Harvest.verlust_gramm).label("verluste"),
                func.count(Harvest.id).label("anzahl")
            )
            .where(Harvest.ernte_datum.between(von, bis))
        ).first()

        return {
            "gesamt_gramm": float(harvests.gesamt or 0),
            "verluste_gramm": float(harvests.verluste or 0),
            "anzahl_ernten": harvests.anzahl or 0,
            "verlustquote": (
                float(harvests.verluste / (harvests.gesamt + harvests.verluste) * 100)
                if harvests.gesamt else 0
            )
        }

    def _update_capacity(self, ressource_typ: ResourceType, delta: int):
        """
        Aktualisiert Kapazitätsauslastung.
        """
        capacity = self.db.execute(
            select(Capacity).where(Capacity.ressource_typ == ressource_typ)
        ).scalar_one_or_none()

        if capacity:
            capacity.aktuell_belegt = max(0, capacity.aktuell_belegt + delta)
