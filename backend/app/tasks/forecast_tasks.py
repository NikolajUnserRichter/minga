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
from app.models.order import Order, OrderItem, OrderStatus

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
                select(func.sum(OrderItem.menge))
                .join(Order)
                .where(
                    OrderItem.seed_id == forecast.seed_id,
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
