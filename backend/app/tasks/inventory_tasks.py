"""
Celery Tasks für Lagerverwaltung
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, func

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.inventory import (
    SeedInventory, FinishedGoodsInventory, PackagingInventory,
    InventoryMovement, InventoryItemType, MovementType
)
from app.models.seed import Seed

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.inventory_tasks.check_low_stock")
def check_low_stock():
    """
    Prüft Lagerbestände und erstellt Warnungen für niedrige Bestände.
    Wird täglich um 7:00 ausgeführt.
    """
    logger.info("Prüfe Lagerbestände")

    db = SessionLocal()
    try:
        alerts = []

        # Saatgut prüfen
        low_seeds = db.execute(
            select(SeedInventory)
            .join(Seed)
            .where(
                SeedInventory.is_active == True,
                SeedInventory.min_quantity != None,
                SeedInventory.current_quantity < SeedInventory.min_quantity
            )
        ).scalars().all()

        for inv in low_seeds:
            alert = {
                "type": "SAATGUT",
                "article_name": inv.seed.name if inv.seed else "Unbekannt",
                "batch_number": inv.batch_number,
                "current_quantity": float(inv.current_quantity),
                "min_quantity": float(inv.min_quantity),
                "unit": inv.unit,
                "deficit": float(inv.min_quantity - inv.current_quantity)
            }
            alerts.append(alert)
            logger.warning(
                f"Niedriger Saatgut-Bestand: {alert['article_name']} "
                f"({alert['current_quantity']}{alert['unit']} / min {alert['min_quantity']}{alert['unit']})"
            )

        # Verpackung prüfen
        low_packaging = db.execute(
            select(PackagingInventory)
            .where(
                PackagingInventory.is_active == True,
                PackagingInventory.min_quantity != None,
                PackagingInventory.current_quantity < PackagingInventory.min_quantity
            )
        ).scalars().all()

        for inv in low_packaging:
            alert = {
                "type": "VERPACKUNG",
                "article_name": inv.name,
                "article_number": inv.article_number,
                "current_quantity": float(inv.current_quantity),
                "min_quantity": float(inv.min_quantity),
                "reorder_quantity": float(inv.reorder_quantity) if inv.reorder_quantity else None,
                "unit": inv.unit,
                "deficit": float(inv.min_quantity - inv.current_quantity)
            }
            alerts.append(alert)
            logger.warning(
                f"Niedriger Verpackungs-Bestand: {alert['article_name']} "
                f"({alert['current_quantity']} / min {alert['min_quantity']})"
            )

        # TODO: Alerts per E-Mail versenden oder in Notification-System speichern

        return {
            "status": "success",
            "alerts_count": len(alerts),
            "alerts": alerts
        }

    finally:
        db.close()


@celery_app.task(name="app.tasks.inventory_tasks.check_expiring_goods")
def check_expiring_goods(days_threshold: int = 3):
    """
    Prüft Fertigware auf ablaufende MHD.
    """
    logger.info(f"Prüfe ablaufende Fertigware (Schwelle: {days_threshold} Tage)")

    db = SessionLocal()
    try:
        threshold_date = date.today() + timedelta(days=days_threshold)

        # Fertigware mit nahem MHD
        expiring = db.execute(
            select(FinishedGoodsInventory)
            .where(
                FinishedGoodsInventory.is_active == True,
                FinishedGoodsInventory.current_quantity > 0,
                FinishedGoodsInventory.mhd <= threshold_date
            )
            .order_by(FinishedGoodsInventory.mhd)
        ).scalars().all()

        alerts = []
        for inv in expiring:
            days_until = (inv.mhd - date.today()).days
            alert = {
                "product_name": inv.product.name if inv.product else "Unbekannt",
                "batch_number": inv.batch_number,
                "mhd": inv.mhd.isoformat(),
                "days_until_expiry": days_until,
                "current_quantity": float(inv.current_quantity),
                "unit": inv.unit,
                "location": inv.location.name if inv.location else None
            }
            alerts.append(alert)

            if days_until <= 0:
                logger.error(f"ABGELAUFEN: {alert['product_name']} ({alert['batch_number']})")
            else:
                logger.warning(
                    f"Läuft ab in {days_until} Tagen: {alert['product_name']} "
                    f"({alert['batch_number']}, MHD: {alert['mhd']})"
                )

        return {
            "status": "success",
            "expiring_count": len(alerts),
            "alerts": alerts
        }

    finally:
        db.close()


@celery_app.task(name="app.tasks.inventory_tasks.generate_inventory_report")
def generate_inventory_report():
    """
    Generiert täglichen Bestandsbericht.
    """
    logger.info("Generiere Bestandsbericht")

    db = SessionLocal()
    try:
        today = date.today()

        # Saatgut-Bestand
        seed_stats = db.execute(
            select(
                func.count(SeedInventory.id).label("batches"),
                func.sum(SeedInventory.current_quantity).label("total_quantity")
            )
            .where(SeedInventory.is_active == True)
        ).first()

        # Fertigware-Bestand
        goods_stats = db.execute(
            select(
                func.count(FinishedGoodsInventory.id).label("batches"),
                func.sum(FinishedGoodsInventory.current_quantity).label("total_quantity"),
                func.sum(FinishedGoodsInventory.available_quantity).label("available_quantity")
            )
            .where(FinishedGoodsInventory.is_active == True)
        ).first()

        # Verpackungs-Bestand
        packaging_stats = db.execute(
            select(
                func.count(PackagingInventory.id).label("articles"),
                func.sum(PackagingInventory.current_quantity).label("total_quantity")
            )
            .where(PackagingInventory.is_active == True)
        ).first()

        # Bewegungen heute
        movements_today = db.execute(
            select(
                InventoryMovement.movement_type,
                func.count(InventoryMovement.id).label("count"),
                func.sum(InventoryMovement.quantity).label("total")
            )
            .where(func.date(InventoryMovement.movement_date) == today)
            .group_by(InventoryMovement.movement_type)
        ).all()

        report = {
            "datum": today.isoformat(),
            "saatgut": {
                "chargen": seed_stats.batches or 0,
                "gesamtmenge_gramm": float(seed_stats.total_quantity or 0)
            },
            "fertigware": {
                "chargen": goods_stats.batches or 0,
                "gesamtmenge": float(goods_stats.total_quantity or 0),
                "verfuegbar": float(goods_stats.available_quantity or 0)
            },
            "verpackung": {
                "artikel": packaging_stats.articles or 0,
                "gesamtmenge": float(packaging_stats.total_quantity or 0)
            },
            "bewegungen_heute": [
                {
                    "typ": row.movement_type.value if hasattr(row.movement_type, 'value') else str(row.movement_type),
                    "anzahl": row.count,
                    "menge": float(row.total or 0)
                }
                for row in movements_today
            ]
        }

        logger.info(
            f"Bestandsbericht: {report['saatgut']['gesamtmenge_gramm']:.0f}g Saatgut, "
            f"{report['fertigware']['gesamtmenge']:.0f}g Fertigware"
        )

        return {
            "status": "success",
            "report": report
        }

    finally:
        db.close()


@celery_app.task(name="app.tasks.inventory_tasks.cleanup_expired_goods")
def cleanup_expired_goods():
    """
    Markiert abgelaufene Fertigware als inaktiv und erstellt Verlust-Buchung.
    Wird täglich ausgeführt.
    """
    logger.info("Bereinige abgelaufene Fertigware")

    db = SessionLocal()
    try:
        today = date.today()

        # Abgelaufene Fertigware
        expired = db.execute(
            select(FinishedGoodsInventory)
            .where(
                FinishedGoodsInventory.is_active == True,
                FinishedGoodsInventory.current_quantity > 0,
                FinishedGoodsInventory.mhd < today
            )
        ).scalars().all()

        processed = 0
        total_loss = Decimal("0")

        for inv in expired:
            # Verlust-Bewegung erstellen
            movement = InventoryMovement(
                item_type=InventoryItemType.FERTIGWARE,
                article_id=inv.id,
                movement_type=MovementType.VERLUST,
                quantity=-inv.current_quantity,
                unit=inv.unit,
                movement_date=today,
                notes=f"MHD abgelaufen am {inv.mhd.isoformat()}"
            )
            db.add(movement)

            total_loss += inv.current_quantity
            inv.current_quantity = Decimal("0")
            inv.available_quantity = Decimal("0")
            inv.is_active = False

            logger.warning(
                f"Abgelaufene Ware bereinigt: {inv.product.name if inv.product else 'Unbekannt'} "
                f"({inv.batch_number}), MHD: {inv.mhd}"
            )
            processed += 1

        db.commit()

        return {
            "status": "success",
            "processed_count": processed,
            "total_loss_quantity": float(total_loss)
        }

    finally:
        db.close()


@celery_app.task(name="app.tasks.inventory_tasks.calculate_fifo_consumption")
def calculate_fifo_consumption(product_id: str, required_quantity: float):
    """
    Berechnet FIFO-basierte Entnahme aus Lagerbeständen.
    Gibt Liste der zu entnehmenden Chargen zurück.
    """
    db = SessionLocal()
    try:
        remaining = Decimal(str(required_quantity))

        # Verfügbare Chargen nach FIFO (ältestes MHD zuerst)
        available = db.execute(
            select(FinishedGoodsInventory)
            .where(
                FinishedGoodsInventory.product_id == product_id,
                FinishedGoodsInventory.is_active == True,
                FinishedGoodsInventory.available_quantity > 0,
                FinishedGoodsInventory.mhd >= date.today()
            )
            .order_by(FinishedGoodsInventory.mhd.asc())
        ).scalars().all()

        consumption_plan = []
        fulfilled = True

        for inv in available:
            if remaining <= 0:
                break

            take_quantity = min(remaining, inv.available_quantity)
            consumption_plan.append({
                "inventory_id": str(inv.id),
                "batch_number": inv.batch_number,
                "mhd": inv.mhd.isoformat(),
                "available": float(inv.available_quantity),
                "take": float(take_quantity)
            })
            remaining -= take_quantity

        if remaining > 0:
            fulfilled = False
            logger.warning(
                f"FIFO-Berechnung: Nur {required_quantity - float(remaining):.2f} "
                f"von {required_quantity:.2f} verfügbar"
            )

        return {
            "status": "success",
            "fulfilled": fulfilled,
            "required": float(required_quantity),
            "available": float(required_quantity - float(remaining)),
            "shortage": float(remaining) if remaining > 0 else 0,
            "consumption_plan": consumption_plan
        }

    finally:
        db.close()
