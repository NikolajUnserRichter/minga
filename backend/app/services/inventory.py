"""
Inventar-Service - Lagerverwaltung für Saatgut und Verpackung
"""
from decimal import Decimal
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.seed import Seed, SeedBatch


class InventoryService:
    """Service für Inventar-Operationen"""

    def __init__(self, db: Session):
        self.db = db

    def get_seed_stock(self, seed_id: UUID) -> dict:
        """
        Gibt aktuellen Saatgut-Bestand zurück.
        """
        batches = self.db.execute(
            select(SeedBatch)
            .where(SeedBatch.seed_id == seed_id, SeedBatch.verbleibend_gramm > 0)
            .order_by(SeedBatch.mhd)  # FIFO nach MHD
        ).scalars().all()

        return {
            "seed_id": str(seed_id),
            "gesamt_gramm": sum(float(b.verbleibend_gramm) for b in batches),
            "chargen": [
                {
                    "id": str(b.id),
                    "charge_nummer": b.charge_nummer,
                    "verbleibend_gramm": float(b.verbleibend_gramm),
                    "mhd": b.mhd.isoformat() if b.mhd else None,
                }
                for b in batches
            ]
        }

    def consume_seed(self, seed_id: UUID, menge_gramm: Decimal) -> list[dict]:
        """
        Verbraucht Saatgut nach FIFO-Prinzip.
        Gibt Liste der verwendeten Chargen zurück.
        """
        batches = self.db.execute(
            select(SeedBatch)
            .where(SeedBatch.seed_id == seed_id, SeedBatch.verbleibend_gramm > 0)
            .order_by(SeedBatch.mhd)
        ).scalars().all()

        verbraucht = []
        verbleibend = menge_gramm

        for batch in batches:
            if verbleibend <= 0:
                break

            entnahme = min(batch.verbleibend_gramm, verbleibend)
            batch.verbleibend_gramm -= entnahme
            verbleibend -= entnahme

            verbraucht.append({
                "batch_id": str(batch.id),
                "charge_nummer": batch.charge_nummer,
                "entnommen_gramm": float(entnahme),
            })

        if verbleibend > 0:
            raise ValueError(
                f"Nicht genug Saatgut verfügbar. "
                f"Benötigt: {menge_gramm}g, Fehlend: {verbleibend}g"
            )

        return verbraucht

    def add_seed_batch(
        self,
        seed_id: UUID,
        charge_nummer: str,
        menge_gramm: Decimal,
        mhd=None,
        lieferdatum=None
    ) -> SeedBatch:
        """
        Fügt neue Saatgut-Charge hinzu (Wareneingang).
        """
        seed = self.db.get(Seed, seed_id)
        if not seed:
            raise ValueError("Saatgut-Sorte nicht gefunden")

        batch = SeedBatch(
            seed_id=seed_id,
            charge_nummer=charge_nummer,
            menge_gramm=menge_gramm,
            verbleibend_gramm=menge_gramm,
            mhd=mhd,
            lieferdatum=lieferdatum,
        )

        self.db.add(batch)
        return batch

    def get_low_stock_alerts(self, threshold_gramm: Decimal = Decimal("1000")) -> list[dict]:
        """
        Gibt Produkte mit niedrigem Bestand zurück.
        """
        from sqlalchemy import func

        stock_levels = self.db.execute(
            select(
                Seed.id,
                Seed.name,
                func.coalesce(func.sum(SeedBatch.verbleibend_gramm), 0).label("bestand")
            )
            .outerjoin(SeedBatch)
            .where(Seed.aktiv == True)
            .group_by(Seed.id, Seed.name)
            .having(func.coalesce(func.sum(SeedBatch.verbleibend_gramm), 0) < threshold_gramm)
        ).all()

        return [
            {
                "seed_id": str(row.id),
                "name": row.name,
                "bestand_gramm": float(row.bestand),
                "schwellwert_gramm": float(threshold_gramm),
            }
            for row in stock_levels
        ]
