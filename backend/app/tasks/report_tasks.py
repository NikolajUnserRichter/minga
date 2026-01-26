"""
Celery Tasks für Reports
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, func

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.seed import Seed
from app.models.production import GrowBatch, Harvest
from app.models.order import Order, OrderLine
from app.models.forecast import Forecast, ForecastAccuracy

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.report_tasks.generate_weekly_accuracy_report")
def generate_weekly_accuracy_report():
    """
    Generiert wöchentlichen Forecast-Accuracy Report.
    Wird jeden Montag um 7:00 ausgeführt.
    """
    logger.info("Generiere wöchentlichen Accuracy Report")

    db = SessionLocal()
    try:
        # Letzte Woche
        today = date.today()
        week_start = today - timedelta(days=today.weekday() + 7)
        week_end = week_start + timedelta(days=6)

        # Accuracy-Daten der letzten Woche
        accuracies = db.execute(
            select(ForecastAccuracy)
            .join(Forecast)
            .where(Forecast.datum.between(week_start, week_end))
        ).scalars().all()

        if not accuracies:
            logger.info("Keine Accuracy-Daten für letzte Woche")
            return {"status": "no_data"}

        # Statistiken berechnen
        mapes = [a.mape for a in accuracies if a.mape is not None]

        report = {
            "zeitraum": {
                "von": week_start.isoformat(),
                "bis": week_end.isoformat()
            },
            "anzahl_forecasts": len(accuracies),
            "durchschnitt_mape": float(sum(mapes) / len(mapes)) if mapes else 0,
            "median_mape": float(sorted(mapes)[len(mapes) // 2]) if mapes else 0,
            "beste_genauigkeit": float(min(mapes)) if mapes else 0,
            "schlechteste_genauigkeit": float(max(mapes)) if mapes else 0,
        }

        logger.info(f"Accuracy Report: Ø MAPE = {report['durchschnitt_mape']:.1f}%")

        # TODO: Report per E-Mail versenden oder speichern

        return {
            "status": "success",
            "report": report
        }

    finally:
        db.close()


@celery_app.task(name="app.tasks.report_tasks.generate_production_summary")
def generate_production_summary(von_datum: str = None, bis_datum: str = None):
    """
    Generiert Produktions-Zusammenfassung.
    """
    logger.info("Generiere Produktions-Zusammenfassung")

    db = SessionLocal()
    try:
        if not von_datum:
            von = date.today() - timedelta(days=7)
        else:
            von = date.fromisoformat(von_datum)

        if not bis_datum:
            bis = date.today()
        else:
            bis = date.fromisoformat(bis_datum)

        # Ernten im Zeitraum
        ernten = db.execute(
            select(
                Seed.name,
                func.sum(Harvest.menge_gramm).label("gesamt_gramm"),
                func.sum(Harvest.verlust_gramm).label("gesamt_verlust"),
                func.count(Harvest.id).label("anzahl_ernten")
            )
            .join(GrowBatch, Harvest.grow_batch_id == GrowBatch.id)
            .join(Seed, GrowBatch.seed_batch.has(seed_id=Seed.id))
            .where(Harvest.ernte_datum.between(von, bis))
            .group_by(Seed.name)
        ).all()

        summary = {
            "zeitraum": {
                "von": von.isoformat(),
                "bis": bis.isoformat()
            },
            "produkte": [
                {
                    "name": row.name,
                    "gesamt_gramm": float(row.gesamt_gramm or 0),
                    "gesamt_verlust": float(row.gesamt_verlust or 0),
                    "anzahl_ernten": row.anzahl_ernten,
                    "verlustquote": float(
                        (row.gesamt_verlust / (row.gesamt_gramm + row.gesamt_verlust)) * 100
                    ) if row.gesamt_gramm else 0
                }
                for row in ernten
            ],
            "gesamt": {
                "gramm": sum(float(r.gesamt_gramm or 0) for r in ernten),
                "verlust": sum(float(r.gesamt_verlust or 0) for r in ernten)
            }
        }

        logger.info(f"Produktions-Summary: {summary['gesamt']['gramm']:.0f}g Ernte")

        return {
            "status": "success",
            "summary": summary
        }

    finally:
        db.close()


@celery_app.task(name="app.tasks.report_tasks.generate_sales_summary")
def generate_sales_summary(von_datum: str = None, bis_datum: str = None):
    """
    Generiert Vertriebs-Zusammenfassung.
    """
    logger.info("Generiere Vertriebs-Zusammenfassung")

    db = SessionLocal()
    try:
        if not von_datum:
            von = date.today() - timedelta(days=7)
        else:
            von = date.fromisoformat(von_datum)

        if not bis_datum:
            bis = date.today()
        else:
            bis = date.fromisoformat(bis_datum)

        # Bestellungen im Zeitraum
        orders = db.execute(
            select(
                func.count(Order.id).label("anzahl_bestellungen"),
                func.sum(OrderLine.menge * OrderLine.preis_pro_einheit).label("umsatz")
            )
            .join(OrderLine)
            .where(Order.liefer_datum.between(von, bis))
        ).first()

        # Top Produkte
        top_produkte = db.execute(
            select(
                Seed.name,
                func.sum(OrderLine.menge).label("gesamt_menge")
            )
            .join(Seed, OrderLine.seed_id == Seed.id)
            .join(Order)
            .where(Order.liefer_datum.between(von, bis))
            .group_by(Seed.name)
            .order_by(func.sum(OrderLine.menge).desc())
            .limit(5)
        ).all()

        summary = {
            "zeitraum": {
                "von": von.isoformat(),
                "bis": bis.isoformat()
            },
            "bestellungen": orders.anzahl_bestellungen or 0,
            "umsatz": float(orders.umsatz or 0),
            "top_produkte": [
                {"name": row.name, "menge": float(row.gesamt_menge)}
                for row in top_produkte
            ]
        }

        logger.info(f"Sales Summary: {summary['bestellungen']} Bestellungen, {summary['umsatz']:.2f}€")

        return {
            "status": "success",
            "summary": summary
        }

    finally:
        db.close()
