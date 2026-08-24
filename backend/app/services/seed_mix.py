"""
Mischsorten ('Brotzeitmix'): aus dem Bestand mehrerer Sorten wird bei der
Aussaat eine Mischcharge angesetzt.

Der Mix hat keinen Wareneingang — er entsteht erst beim Aussäen. Damit die
Rückverfolgbarkeit erhalten bleibt, bekommt jede Mischung eine eigene
Chargennummer und merkt sich, welche Ausgangschargen darin stecken.
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inventory import SeedInventory
from app.models.seed import Seed, SeedBatch, SeedBatchComponent

GRAMM_PRO_KG = Decimal("1000")


class NichtGenugSaatgut(ValueError):
    """Der Bestand einer Ausgangssorte reicht für die Mischung nicht."""


def naechste_mix_chargennummer(db: Session, tag: date) -> str:
    """MIX-JJJJMMTT-N — pro Tag durchnummeriert."""
    prefix = f"MIX-{tag.strftime('%Y%m%d')}-"
    vorhanden = db.execute(
        select(func.count()).select_from(SeedBatch)
        .where(SeedBatch.charge_nummer.like(f"{prefix}%"))
    ).scalar() or 0
    return f"{prefix}{vorhanden + 1}"


def _bestaende(db: Session, seed_id) -> list[SeedInventory]:
    """Verfügbare Chargen einer Sorte, FIFO nach MHD (ohne MHD zuletzt)."""
    bestaende = db.execute(
        select(SeedInventory).where(
            SeedInventory.seed_id == seed_id,
            SeedInventory.current_quantity_kg > 0,
            SeedInventory.is_active.is_(True),
            SeedInventory.is_blocked.is_(False),
        )
    ).scalars().all()
    return sorted(
        bestaende,
        key=lambda b: (b.best_before_date is None, b.best_before_date or date.max, b.received_date),
    )


def mische_charge(
    db: Session,
    mix_seed: Seed,
    tray_anzahl: int,
    aussaat_datum: date,
    created_by: Optional[str] = None,
) -> SeedBatch:
    """Setzt eine Mischcharge an und zieht das Saatgut von den Ausgangssorten ab.

    Wirft NichtGenugSaatgut, *bevor* irgendetwas abgebucht wird — eine halb
    abgezogene Mischung wäre schlimmer als eine abgelehnte.
    """
    from app.services.inventory_service import InventoryService

    komponenten = list(mix_seed.mix_components)
    if not komponenten:
        raise NichtGenugSaatgut(
            f"'{mix_seed.name}' ist als Mischsorte angelegt, hat aber keine Komponente. "
            "Bitte im Saatgut-Stammsatz die Ausgangssorten mit Menge je Kiste hinterlegen."
        )

    # Erst rechnen, dann buchen: Bedarf und Deckung je Komponente prüfen.
    bedarf: list[tuple] = []
    for komponente in komponenten:
        menge_g = Decimal(str(komponente.gramm_pro_tray)) * tray_anzahl
        bestaende = _bestaende(db, komponente.component_seed_id)
        verfuegbar_g = sum((b.current_quantity_kg for b in bestaende), Decimal("0")) * GRAMM_PRO_KG
        if verfuegbar_g < menge_g:
            name = komponente.component_seed.name if komponente.component_seed else "Unbekannte Sorte"
            raise NichtGenugSaatgut(
                f"Nicht genug Saatgut für '{name}': benötigt {menge_g:.0f} g, "
                f"verfügbar {verfuegbar_g:.0f} g."
            )
        bedarf.append((komponente, menge_g, bestaende))

    mix_batch = SeedBatch(
        seed_id=mix_seed.id,
        charge_nummer=naechste_mix_chargennummer(db, aussaat_datum),
        menge_gramm=sum((menge for _, menge, _ in bedarf), Decimal("0")),
        # Die Mischung geht direkt in die Kiste — sie liegt nie im Lager.
        verbleibend_gramm=Decimal("0"),
        lieferdatum=aussaat_datum,
        in_production_at=aussaat_datum,
    )
    db.add(mix_batch)
    db.flush()

    service = InventoryService(db)
    for komponente, menge_g, bestaende in bedarf:
        offen = menge_g
        for bestand in bestaende:
            if offen <= 0:
                break
            entnahme_g = min(bestand.current_quantity_kg * GRAMM_PRO_KG, offen)
            entnahme_kg = entnahme_g / GRAMM_PRO_KG
            offen -= entnahme_g

            service.consume_seed_for_sowing(
                seed_inventory_id=bestand.id,
                quantity_kg=entnahme_kg,
                reason=f"Mischung {mix_seed.name}",
                reference_number=mix_batch.charge_nummer,
                created_by=created_by,
            )
            _spiegel_seed_batch(db, komponente.component_seed_id, bestand.batch_number, entnahme_g)
            db.add(SeedBatchComponent(
                mix_batch_id=mix_batch.id,
                component_seed_id=komponente.component_seed_id,
                charge_nummer=bestand.batch_number,
                menge_gramm=entnahme_g,
            ))

    db.flush()
    return mix_batch


def _spiegel_seed_batch(db: Session, seed_id, charge_nummer: str, entnahme_g: Decimal) -> None:
    """Zieht die Entnahme auch an der Traceability-Charge ab.

    SeedInventory und SeedBatch führen denselben Bestand doppelt (kg bzw. g).
    Ohne den Spiegel stünde die Charge in der Rückverfolgung noch als voll da.
    """
    batch = db.execute(
        select(SeedBatch).where(
            SeedBatch.seed_id == seed_id,
            SeedBatch.charge_nummer == charge_nummer,
        )
    ).scalars().first()
    if batch is None:
        return
    batch.verbleibend_gramm = max(Decimal(str(batch.verbleibend_gramm)) - entnahme_g, Decimal("0"))
