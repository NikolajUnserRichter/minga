"""
Celery Tasks für Forecasting
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select

from app.celery_app import celery_app
from app.config import get_settings
from app.database import SessionLocal
from app.models.seed import Seed
from app.models.production import GrowBatch, GrowBatchStatus
from app.models.forecast import Forecast, ForecastAccuracy
from app.models.order import Order, OrderLine, OrderStatus

logger = logging.getLogger(__name__)
settings = get_settings()


@celery_app.task(name="app.tasks.forecast_tasks.generate_daily_forecasts")
def generate_daily_forecasts():
    """
    Generiert tägliche Forecasts für alle aktiven Produkte.
    Wird jeden Morgen um 6:00 ausgeführt.
    """
    logger.info("Starte tägliche Forecast-Generierung")

    db = SessionLocal()
    try:
        # Alle aktiven Seeds laden
        seeds = db.execute(
            select(Seed).where(Seed.aktiv == True)
        ).scalars().all()

        if not seeds:
            logger.warning("Keine aktiven Produkte gefunden")
            return {"status": "warning", "message": "Keine aktiven Produkte"}

        # Forecasting Service aufrufen
        forecasts_generated = 0

        for seed in seeds:
            try:
                # Externen Forecasting Service aufrufen
                response = httpx.post(
                    f"{settings.forecasting_service_url}/forecast/sales",
                    json={
                        "seed_id": str(seed.id),
                        "horizon_days": 14,
                        "use_prophet": True
                    },
                    timeout=60.0
                )

                if response.status_code == 200:
                    forecasts_generated += 1
                    logger.info(f"Forecast für {seed.name} generiert")
                else:
                    logger.warning(f"Forecast für {seed.name} fehlgeschlagen: {response.status_code}")

            except Exception as e:
                logger.error(f"Fehler bei Forecast für {seed.name}: {e}")

        logger.info(f"Forecast-Generierung abgeschlossen: {forecasts_generated} Produkte")

        return {
            "status": "success",
            "products_processed": len(seeds),
            "forecasts_generated": forecasts_generated
        }

    finally:
        db.close()


@celery_app.task(name="app.tasks.forecast_tasks.check_batch_status")
def check_batch_status():
    """
    Prüft Chargen-Status und aktualisiert basierend auf Erntefenster.
    Wird stündlich ausgeführt.
    """
    logger.info("Prüfe Chargen-Status")

    db = SessionLocal()
    try:
        today = date.today()

        # Chargen in WACHSTUM, die erntereif sind
        batches_to_update = db.execute(
            select(GrowBatch)
            .where(
                GrowBatch.status == GrowBatchStatus.WACHSTUM,
                GrowBatch.erwartete_ernte_min <= today
            )
        ).scalars().all()

        updated_count = 0
        for batch in batches_to_update:
            batch.status = GrowBatchStatus.ERNTEREIF
            updated_count += 1
            logger.info(f"Charge {batch.id} auf ERNTEREIF gesetzt")

        # Chargen die über max Erntefenster sind
        overdue_batches = db.execute(
            select(GrowBatch)
            .where(
                GrowBatch.status.in_([GrowBatchStatus.WACHSTUM, GrowBatchStatus.ERNTEREIF]),
                GrowBatch.erwartete_ernte_max < today
            )
        ).scalars().all()

        overdue_count = 0
        for batch in overdue_batches:
            # Warnung loggen (nicht automatisch auf Verlust setzen)
            logger.warning(
                f"Charge {batch.id} überschreitet maximales Erntefenster "
                f"(max: {batch.erwartete_ernte_max})"
            )
            overdue_count += 1

        db.commit()

        return {
            "status": "success",
            "updated_to_erntereif": updated_count,
            "overdue_warnings": overdue_count
        }

    finally:
        db.close()


@celery_app.task(name="app.tasks.forecast_tasks.calculate_forecast_accuracy")
def calculate_forecast_accuracy():
    """
    Berechnet Forecast Accuracy für vergangene Forecasts.
    Vergleicht Prognose mit tatsächlichen Verkäufen.
    """
    logger.info("Berechne Forecast Accuracy")

    db = SessionLocal()
    try:
        yesterday = date.today() - timedelta(days=1)

        # Forecasts von gestern ohne Accuracy-Eintrag
        forecasts = db.execute(
            select(Forecast)
            .where(
                Forecast.datum == yesterday,
                ~Forecast.id.in_(
                    select(ForecastAccuracy.forecast_id)
                )
            )
        ).scalars().all()

        accuracy_count = 0

        for forecast in forecasts:
            # Tatsächliche Verkäufe für diesen Tag und Produkt
            actual_sales = db.execute(
                select(func.sum(OrderLine.menge))
                .join(Order)
                .where(
                    OrderLine.seed_id == forecast.seed_id,
                    Order.liefer_datum == yesterday,
                    Order.status != OrderStatus.STORNIERT
                )
            ).scalar() or Decimal("0")

            # Accuracy berechnen
            accuracy = ForecastAccuracy(
                forecast_id=forecast.id,
                ist_menge=actual_sales
            )
            accuracy.berechne_abweichungen()
            db.add(accuracy)
            accuracy_count += 1

        db.commit()

        logger.info(f"Accuracy für {accuracy_count} Forecasts berechnet")

        return {
            "status": "success",
            "accuracies_calculated": accuracy_count
        }

    except Exception as e:
        logger.error(f"Fehler bei Accuracy-Berechnung: {e}")
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(name="app.tasks.forecast_tasks.generate_production_suggestions")
def generate_production_suggestions(seed_id: str = None, horizont_tage: int = 14):
    """
    Generiert Produktionsvorschläge aus Forecasts.
    Kann für einzelnes Produkt oder alle aufgerufen werden.
    """
    logger.info(f"Generiere Produktionsvorschläge (seed_id={seed_id}, horizont={horizont_tage})")

    try:
        # Forecasting Service aufrufen
        params = {"horizont_tage": horizont_tage}

        response = httpx.post(
            f"{settings.forecasting_service_url}/forecast/production-suggestions/generate",
            params=params,
            timeout=120.0
        )

        if response.status_code == 200:
            suggestions = response.json()
            logger.info(f"{len(suggestions)} Produktionsvorschläge generiert")
            return {
                "status": "success",
                "suggestions_count": len(suggestions)
            }
        else:
            logger.error(f"Fehler bei Vorschlags-Generierung: {response.status_code}")
            return {
                "status": "error",
                "message": response.text
            }

    except Exception as e:
        logger.error(f"Fehler bei Produktionsvorschlägen: {e}")
        raise


# Import für func
from sqlalchemy import func


# ==================== ORDER-TRIGGERED TASKS ====================

@celery_app.task(name="app.tasks.forecast_tasks.trigger_forecast_recalculation")
def trigger_forecast_recalculation(
    order_id: str = None,
    seed_ids: list[str] = None,
    product_ids: list[str] = None,
    reason: str = "Order change"
):
    """
    Löst Forecast-Neuberechnung aus wenn sich Bestellungen ändern.

    Diese Task wird automatisch getriggert bei:
    - Neuer Bestellung
    - Bestellungsänderung
    - Bestellungsstornierung

    Args:
        order_id: ID der geänderten Bestellung (optional)
        seed_ids: Liste von Seed-IDs die betroffen sind
        product_ids: Liste von Produkt-IDs die betroffen sind
        reason: Grund für die Neuberechnung
    """
    logger.info(f"Forecast-Neuberechnung getriggert: {reason}")

    db = SessionLocal()
    try:
        from app.models.order import Order as OrderModel, OrderLine
        from app.models.product import Product

        affected_seed_ids = set()

        # Wenn Order-ID angegeben, extrahiere betroffene Seeds/Products
        if order_id:
            order = db.get(OrderModel, order_id)
            if order:
                for line in order.lines:
                    if line.seed_id:
                        affected_seed_ids.add(str(line.seed_id))
                    if line.product_id:
                        product = db.get(Product, line.product_id)
                        if product and product.seed_id:
                            affected_seed_ids.add(str(product.seed_id))

        # Direkt angegebene IDs hinzufügen
        if seed_ids:
            affected_seed_ids.update(seed_ids)

        if product_ids:
            for prod_id in product_ids:
                product = db.get(Product, prod_id)
                if product and product.seed_id:
                    affected_seed_ids.add(str(product.seed_id))

        if not affected_seed_ids:
            logger.info("Keine betroffenen Produkte gefunden")
            return {"status": "no_action", "reason": "No affected products"}

        # Forecast-Service aufrufen
        forecasts_updated = 0

        for seed_id in affected_seed_ids:
            try:
                response = httpx.post(
                    f"{settings.forecasting_service_url}/forecast/sales",
                    json={
                        "seed_id": seed_id,
                        "horizon_days": 14,
                        "use_prophet": True,
                        "trigger_reason": reason
                    },
                    timeout=60.0
                )

                if response.status_code == 200:
                    forecasts_updated += 1
                    logger.info(f"Forecast für Seed {seed_id} aktualisiert")
                else:
                    logger.warning(f"Forecast-Update für Seed {seed_id} fehlgeschlagen")

            except Exception as e:
                logger.error(f"Fehler bei Forecast-Update für {seed_id}: {e}")

        return {
            "status": "success",
            "affected_seeds": len(affected_seed_ids),
            "forecasts_updated": forecasts_updated,
            "reason": reason
        }

    finally:
        db.close()


@celery_app.task(name="app.tasks.forecast_tasks.update_forecast_from_order")
def update_forecast_from_order(order_id: str, action: str):
    """
    Aktualisiert Forecasts basierend auf Bestellungsänderung.

    Args:
        order_id: UUID der Bestellung
        action: Art der Änderung (CREATE, UPDATE, CONFIRM, CANCEL)
    """
    logger.info(f"Order-basierte Forecast-Aktualisierung: Order={order_id}, Action={action}")

    # Je nach Aktion unterschiedliche Behandlung
    if action == "CANCEL":
        reason = "Bestellung storniert"
    elif action == "CREATE":
        reason = "Neue Bestellung angelegt"
    elif action == "CONFIRM":
        reason = "Bestellung bestätigt"
    else:
        reason = f"Bestellung geändert ({action})"

    # Neuberechnung auslösen
    return trigger_forecast_recalculation.delay(
        order_id=order_id,
        reason=reason
    )


# ==================== MANUAL ADJUSTMENT TASKS ====================

@celery_app.task(name="app.tasks.forecast_tasks.apply_manual_adjustment")
def apply_manual_adjustment(forecast_id: str):
    """
    Wendet manuelle Anpassungen auf einen Forecast an und
    aktualisiert die effektive Menge.

    Args:
        forecast_id: UUID des Forecasts
    """
    logger.info(f"Wende manuelle Anpassungen auf Forecast {forecast_id} an")

    db = SessionLocal()
    try:
        forecast = db.get(Forecast, forecast_id)
        if not forecast:
            logger.error(f"Forecast {forecast_id} nicht gefunden")
            return {"status": "error", "message": "Forecast not found"}

        # Anpassungen anwenden
        forecast.apply_manual_adjustments()
        db.commit()

        logger.info(
            f"Forecast {forecast_id}: "
            f"Automatisch={forecast.prognostizierte_menge}, "
            f"Effektiv={forecast.effektive_menge}"
        )

        # Produktionsvorschläge aktualisieren falls vorhanden
        if forecast.suggestions:
            for suggestion in forecast.suggestions:
                suggestion.benoetigte_menge_gramm = forecast.effektive_menge

            db.commit()

        return {
            "status": "success",
            "forecast_id": str(forecast.id),
            "automatic": float(forecast.prognostizierte_menge),
            "effective": float(forecast.effektive_menge),
            "has_adjustments": forecast.hat_manuelle_anpassung
        }

    finally:
        db.close()


@celery_app.task(name="app.tasks.forecast_tasks.recalculate_production_suggestions")
def recalculate_production_suggestions(forecast_id: str):
    """
    Berechnet Produktionsvorschläge nach manueller Forecast-Anpassung neu.

    Args:
        forecast_id: UUID des Forecasts
    """
    logger.info(f"Berechne Produktionsvorschläge für Forecast {forecast_id} neu")

    db = SessionLocal()
    try:
        from app.models.forecast import ProductionSuggestion

        forecast = db.get(Forecast, forecast_id)
        if not forecast:
            return {"status": "error", "message": "Forecast not found"}

        # Existierende Vorschläge für diesen Forecast
        for suggestion in forecast.suggestions:
            if suggestion.status.value == "VORGESCHLAGEN":
                # Nur offene Vorschläge aktualisieren
                seed = suggestion.seed
                if seed:
                    # Neue Tray-Anzahl berechnen
                    required_grams = forecast.effektive_menge
                    yield_per_tray = seed.ertrag_gramm_pro_tray
                    loss_factor = 1 - (seed.verlustquote_prozent / 100)

                    new_trays = int(
                        (required_grams / (yield_per_tray * loss_factor)) + Decimal("0.5")
                    )

                    suggestion.empfohlene_trays = max(1, new_trays)
                    suggestion.benoetigte_menge_gramm = required_grams
                    suggestion.erwartete_menge_gramm = new_trays * yield_per_tray * loss_factor

        db.commit()

        return {
            "status": "success",
            "forecast_id": str(forecast.id),
            "suggestions_updated": len(forecast.suggestions)
        }

    finally:
        db.close()
