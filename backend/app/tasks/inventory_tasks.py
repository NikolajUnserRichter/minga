"""
Celery Tasks für Lagerverwaltung.

Wird durch celery-beat aufgerufen (siehe celery_app.py). Spaltennamen
entsprechen dem aktuellen Inventory-Schema:

  SeedInventory:           current_quantity_kg, best_before_date  (kein unit, kein min_quantity)
  FinishedGoodsInventory:  current_quantity_g,  best_before_date  (kein unit, kein available_quantity)
  PackagingInventory:      current_quantity,    min_quantity, unit, sku
  InventoryMovement:       FK je Typ + quantity_before + quantity_after + reason (Pflichtfeld unit)
"""
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, func

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.inventory import (
    SeedInventory, FinishedGoodsInventory, PackagingInventory,
    InventoryMovement, InventoryItemType, MovementType,
)
from app.models.seed import Seed

logger = logging.getLogger(__name__)


# Konstanten für „Niedriger Saatgut-Bestand" – SeedInventory hat kein min_quantity-Feld.
# Wir warnen, wenn weniger als 0.5 kg übrig sind UND MHD nicht überschritten ist.
SEED_LOW_THRESHOLD_KG = Decimal("0.5")


@celery_app.task(
    name="app.tasks.inventory_tasks.check_low_stock",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=600,
    time_limit=300,
    soft_time_limit=240,
)
def check_low_stock():
    """Prüft Lagerbestände, sammelt Alerts und versendet ggf. eine Sammel-Mail."""
    logger.info("Prüfe Lagerbestände")

    db = SessionLocal()
    try:
        alerts: list[dict] = []

        # Saatgut — feste Schwelle, da Modell kein min_quantity besitzt.
        low_seeds = db.execute(
            select(SeedInventory)
            .join(Seed)
            .where(
                SeedInventory.is_active == True,
                SeedInventory.current_quantity_kg < SEED_LOW_THRESHOLD_KG,
            )
        ).scalars().all()

        for inv in low_seeds:
            alert = {
                "type": "SAATGUT",
                "article_name": inv.seed.name if inv.seed else "Unbekannt",
                "batch_number": inv.batch_number,
                "current_quantity": float(inv.current_quantity_kg),
                "min_quantity": float(SEED_LOW_THRESHOLD_KG),
                "unit": "kg",
                "deficit": float(SEED_LOW_THRESHOLD_KG - inv.current_quantity_kg),
            }
            alerts.append(alert)
            logger.warning(
                f"Niedriger Saatgut-Bestand: {alert['article_name']} "
                f"({alert['current_quantity']}{alert['unit']} / min {alert['min_quantity']}{alert['unit']})"
            )

        # Verpackung — hat min_quantity am Modell.
        low_packaging = db.execute(
            select(PackagingInventory)
            .where(
                PackagingInventory.is_active == True,
                PackagingInventory.min_quantity != None,
                PackagingInventory.current_quantity < PackagingInventory.min_quantity,
            )
        ).scalars().all()

        for inv in low_packaging:
            alert = {
                "type": "VERPACKUNG",
                "article_name": inv.name,
                "article_number": inv.sku,
                "current_quantity": float(inv.current_quantity),
                "min_quantity": float(inv.min_quantity),
                "reorder_quantity": float(inv.reorder_quantity) if inv.reorder_quantity else None,
                "unit": inv.unit,
                "deficit": float(inv.min_quantity - inv.current_quantity),
            }
            alerts.append(alert)
            logger.warning(
                f"Niedriger Verpackungs-Bestand: {alert['article_name']} "
                f"({alert['current_quantity']} / min {alert['min_quantity']})"
            )

        # Alerts per E-Mail versenden (best effort — fehlende Settings dürfen Task nicht killen)
        if alerts:
            try:
                from app.core.email import email_service  # type: ignore
                from app.config import get_settings

                settings = get_settings()

                items_html = ""
                for alert in alerts:
                    items_html += (
                        f"<li><strong>{alert['article_name']}</strong> "
                        f"({alert.get('batch_number', alert.get('article_number', 'N/A'))}): "
                        f"{alert['current_quantity']} {alert['unit']} "
                        f"(Min: {alert['min_quantity']} {alert['unit']})</li>"
                    )

                email_body = f"""
                <h3>Niedriger Lagerbestand erkannt</h3>
                <p>Folgende Artikel haben den Mindestbestand unterschritten:</p>
                <ul>
                    {items_html}
                </ul>
                <p>Bitte Nachbestellung prüfen.</p>
                """

                email_service.send_email(
                    email_to=settings.emails_from_email,
                    subject=f"⚠️ Lagerbestand Warnung ({len(alerts)} Artikel)",
                    template_str=email_body,
                    template_data={},
                )
            except Exception as e:
                logger.warning(f"E-Mail-Versand für Low-Stock-Alerts fehlgeschlagen: {e}")

        return {"status": "success", "alerts_count": len(alerts), "alerts": alerts}
    finally:
        db.close()


@celery_app.task(name="app.tasks.inventory_tasks.check_expiring_goods")
def check_expiring_goods(days_threshold: int = 3):
    """Prüft Fertigware auf nahende MHD."""
    logger.info(f"Prüfe ablaufende Fertigware (Schwelle: {days_threshold} Tage)")

    db = SessionLocal()
    try:
        threshold_date = date.today() + timedelta(days=days_threshold)

        expiring = db.execute(
            select(FinishedGoodsInventory)
            .where(
                FinishedGoodsInventory.is_active == True,
                FinishedGoodsInventory.current_quantity_g > 0,
                FinishedGoodsInventory.best_before_date <= threshold_date,
            )
            .order_by(FinishedGoodsInventory.best_before_date)
        ).scalars().all()

        alerts: list[dict] = []
        for inv in expiring:
            days_until = (inv.best_before_date - date.today()).days
            alert = {
                "product_name": inv.product.name if inv.product else "Unbekannt",
                "batch_number": inv.batch_number,
                "best_before_date": inv.best_before_date.isoformat(),
                "days_until_expiry": days_until,
                "current_quantity_g": float(inv.current_quantity_g),
                "unit": "g",
                "location": inv.location.name if inv.location else None,
            }
            alerts.append(alert)

            if days_until <= 0:
                logger.error(f"ABGELAUFEN: {alert['product_name']} ({alert['batch_number']})")
            else:
                logger.warning(
                    f"Läuft ab in {days_until} Tagen: {alert['product_name']} "
                    f"({alert['batch_number']}, MHD: {alert['best_before_date']})"
                )

        return {"status": "success", "expiring_count": len(alerts), "alerts": alerts}
    finally:
        db.close()


@celery_app.task(name="app.tasks.inventory_tasks.generate_inventory_report")
def generate_inventory_report():
    """Generiert einen täglichen Bestandsbericht."""
    logger.info("Generiere Bestandsbericht")

    db = SessionLocal()
    try:
        today = date.today()

        seed_stats = db.execute(
            select(
                func.count(SeedInventory.id).label("batches"),
                func.sum(SeedInventory.current_quantity_kg).label("total_kg"),
            ).where(SeedInventory.is_active == True)
        ).first()

        goods_stats = db.execute(
            select(
                func.count(FinishedGoodsInventory.id).label("batches"),
                func.sum(FinishedGoodsInventory.current_quantity_g).label("total_g"),
            ).where(FinishedGoodsInventory.is_active == True)
        ).first()

        # Verfügbar = aktiv + MHD nicht überschritten
        available_stats = db.execute(
            select(
                func.sum(FinishedGoodsInventory.current_quantity_g).label("available_g"),
            ).where(
                FinishedGoodsInventory.is_active == True,
                FinishedGoodsInventory.best_before_date >= today,
            )
        ).first()

        packaging_stats = db.execute(
            select(
                func.count(PackagingInventory.id).label("articles"),
                func.sum(PackagingInventory.current_quantity).label("total_quantity"),
            ).where(PackagingInventory.is_active == True)
        ).first()

        # Bewegungen heute
        movements_today = db.execute(
            select(
                InventoryMovement.movement_type,
                func.count(InventoryMovement.id).label("count"),
                func.sum(InventoryMovement.quantity).label("total"),
            )
            .where(func.date(InventoryMovement.movement_date) == today)
            .group_by(InventoryMovement.movement_type)
        ).all()

        report = {
            "datum": today.isoformat(),
            "saatgut": {
                "chargen": seed_stats.batches or 0,
                "gesamtmenge_kg": float(seed_stats.total_kg or 0),
            },
            "fertigware": {
                "chargen": goods_stats.batches or 0,
                "gesamtmenge_g": float(goods_stats.total_g or 0),
                "verfuegbar_g": float(available_stats.available_g or 0),
            },
            "verpackung": {
                "artikel": packaging_stats.articles or 0,
                "gesamtmenge": float(packaging_stats.total_quantity or 0),
            },
            "bewegungen_heute": [
                {
                    "typ": row.movement_type.value if hasattr(row.movement_type, 'value') else str(row.movement_type),
                    "anzahl": row.count,
                    "menge": float(row.total or 0),
                }
                for row in movements_today
            ],
        }

        logger.info(
            f"Bestandsbericht: {report['saatgut']['gesamtmenge_kg']:.2f}kg Saatgut, "
            f"{report['fertigware']['gesamtmenge_g']:.0f}g Fertigware"
        )
        return {"status": "success", "report": report}
    finally:
        db.close()


@celery_app.task(name="app.tasks.inventory_tasks.cleanup_expired_goods")
def cleanup_expired_goods():
    """Markiert abgelaufene Fertigware als inaktiv und protokolliert Verlust."""
    logger.info("Bereinige abgelaufene Fertigware")

    db = SessionLocal()
    try:
        today = date.today()

        expired = db.execute(
            select(FinishedGoodsInventory)
            .where(
                FinishedGoodsInventory.is_active == True,
                FinishedGoodsInventory.current_quantity_g > 0,
                FinishedGoodsInventory.best_before_date < today,
            )
        ).scalars().all()

        processed = 0
        total_loss_g = Decimal("0")

        for inv in expired:
            qty_before = Decimal(str(inv.current_quantity_g))
            movement = InventoryMovement(
                item_type=InventoryItemType.FERTIGWARE,
                finished_goods_id=inv.id,
                movement_type=MovementType.VERLUST,
                quantity=-qty_before,            # negativ = Abgang
                quantity_before=qty_before,
                quantity_after=Decimal("0"),
                unit="g",
                movement_date=datetime.now(timezone.utc),
                reason=f"MHD abgelaufen am {inv.best_before_date.isoformat()}",
            )
            db.add(movement)

            total_loss_g += qty_before
            inv.current_quantity_g = Decimal("0")
            inv.is_active = False
            processed += 1

            logger.warning(
                f"Abgelaufene Ware bereinigt: "
                f"{inv.product.name if inv.product else 'Unbekannt'} "
                f"({inv.batch_number}), MHD: {inv.best_before_date}"
            )

        db.commit()

        return {
            "status": "success",
            "processed_count": processed,
            "total_loss_g": float(total_loss_g),
        }
    finally:
        db.close()


@celery_app.task(name="app.tasks.inventory_tasks.calculate_fifo_consumption")
def calculate_fifo_consumption(product_id: str, required_quantity_g: float):
    """Berechnet FIFO-basierte Entnahme aus Fertigware-Beständen (g)."""
    db = SessionLocal()
    try:
        remaining = Decimal(str(required_quantity_g))

        available = db.execute(
            select(FinishedGoodsInventory)
            .where(
                FinishedGoodsInventory.product_id == product_id,
                FinishedGoodsInventory.is_active == True,
                FinishedGoodsInventory.current_quantity_g > 0,
                FinishedGoodsInventory.best_before_date >= date.today(),
            )
            .order_by(FinishedGoodsInventory.best_before_date.asc())
        ).scalars().all()

        consumption_plan: list[dict] = []
        for inv in available:
            if remaining <= 0:
                break
            take = min(remaining, Decimal(str(inv.current_quantity_g)))
            consumption_plan.append({
                "inventory_id": str(inv.id),
                "batch_number": inv.batch_number,
                "best_before_date": inv.best_before_date.isoformat(),
                "available_g": float(inv.current_quantity_g),
                "take_g": float(take),
            })
            remaining -= take

        fulfilled = remaining <= 0
        if not fulfilled:
            logger.warning(
                f"FIFO-Berechnung: Nur {required_quantity_g - float(remaining):.2f}g "
                f"von {required_quantity_g:.2f}g verfügbar"
            )

        return {
            "status": "success",
            "fulfilled": fulfilled,
            "required_g": float(required_quantity_g),
            "available_g": float(required_quantity_g - float(remaining)),
            "shortage_g": float(remaining) if remaining > 0 else 0,
            "consumption_plan": consumption_plan,
        }
    finally:
        db.close()
