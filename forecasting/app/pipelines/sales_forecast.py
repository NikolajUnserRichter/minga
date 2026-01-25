"""
Sales Forecast Pipeline
Orchestriert die Absatzprognose für Microgreens
"""
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models.prophet_model import ProphetForecaster, SimpleForecaster

logger = logging.getLogger(__name__)
settings = get_settings()


class SalesForecastPipeline:
    """
    Pipeline für Absatzprognosen.

    Schritte:
    1. Historische Verkaufsdaten laden
    2. Abonnements berücksichtigen
    3. Saisonalität und Feiertage einbeziehen
    4. Prognose erstellen
    """

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or settings.database_url
        self.engine = create_engine(self.database_url)
        self.Session = sessionmaker(bind=self.engine)

    def load_historical_sales(
        self,
        seed_id: UUID,
        days_back: int = 90,
        customer_id: Optional[UUID] = None
    ) -> list[dict]:
        """
        Lädt historische Verkaufsdaten.

        Returns:
            [{"date": "2025-01-15", "quantity": 2500.0}, ...]
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)

        # Raw SQL für Flexibilität
        query = """
            SELECT
                o.liefer_datum as date,
                COALESCE(SUM(oi.menge), 0) as quantity
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.id
            WHERE oi.seed_id = :seed_id
                AND o.liefer_datum BETWEEN :start_date AND :end_date
                AND o.status != 'STORNIERT'
        """

        params = {
            "seed_id": str(seed_id),
            "start_date": start_date,
            "end_date": end_date
        }

        if customer_id:
            query += " AND o.kunde_id = :customer_id"
            params["customer_id"] = str(customer_id)

        query += " GROUP BY o.liefer_datum ORDER BY o.liefer_datum"

        with self.engine.connect() as conn:
            result = conn.execute(query, params)
            data = [
                {"date": str(row.date), "quantity": float(row.quantity)}
                for row in result
            ]

        return data

    def load_subscriptions(
        self,
        seed_id: UUID,
        customer_id: Optional[UUID] = None
    ) -> list[dict]:
        """
        Lädt aktive Abonnements für ein Produkt.

        Returns:
            [{
                "customer_id": "...",
                "quantity": 500.0,
                "weekdays": [1, 3, 5],  # Di, Do, Sa
                "interval": "WOECHENTLICH"
            }, ...]
        """
        query = """
            SELECT
                s.kunde_id,
                s.menge as quantity,
                s.liefertage as weekdays,
                s.intervall as interval
            FROM subscriptions s
            WHERE s.seed_id = :seed_id
                AND s.aktiv = true
                AND s.gueltig_von <= CURRENT_DATE
                AND (s.gueltig_bis IS NULL OR s.gueltig_bis >= CURRENT_DATE)
        """

        params = {"seed_id": str(seed_id)}

        if customer_id:
            query += " AND s.kunde_id = :customer_id"
            params["customer_id"] = str(customer_id)

        with self.engine.connect() as conn:
            result = conn.execute(query, params)
            data = [
                {
                    "customer_id": str(row.kunde_id),
                    "quantity": float(row.quantity),
                    "weekdays": row.weekdays or [],
                    "interval": row.interval
                }
                for row in result
            ]

        return data

    def calculate_subscription_demand(
        self,
        subscriptions: list[dict],
        forecast_date: date
    ) -> float:
        """
        Berechnet erwartete Nachfrage aus Abonnements für ein Datum.
        """
        weekday = forecast_date.weekday()
        total = 0.0

        for sub in subscriptions:
            if weekday in sub.get("weekdays", []):
                total += sub["quantity"]

        return total

    def run_forecast(
        self,
        seed_id: UUID,
        horizon_days: int = 14,
        customer_id: Optional[UUID] = None,
        use_prophet: bool = True,
        min_history_days: int = 30
    ) -> list[dict]:
        """
        Führt komplette Forecast-Pipeline aus.

        Args:
            seed_id: Produkt-ID
            horizon_days: Prognosehorizont
            customer_id: Optional - kundenspezifische Prognose
            use_prophet: Prophet verwenden (sonst SimpleForecaster)
            min_history_days: Mindest-Historiedaten für Prophet

        Returns:
            [
                {
                    "date": "2026-01-24",
                    "predicted_quantity": 2800.5,
                    "subscription_quantity": 500.0,
                    "total_quantity": 3300.5,
                    "lower_bound": 2700.0,
                    "upper_bound": 3900.0
                },
                ...
            ]
        """
        # 1. Historische Daten laden
        historical_data = self.load_historical_sales(
            seed_id=seed_id,
            days_back=90,
            customer_id=customer_id
        )

        # 2. Abonnements laden
        subscriptions = self.load_subscriptions(
            seed_id=seed_id,
            customer_id=customer_id
        )

        # 3. Forecaster wählen
        if use_prophet and len(historical_data) >= min_history_days:
            try:
                forecaster = ProphetForecaster()
                df = forecaster.prepare_data(historical_data)
                forecaster.train(df)
                base_forecast = forecaster.get_forecast_dict(horizon_days)
            except Exception as e:
                logger.warning(f"Prophet failed, using SimpleForecaster: {e}")
                forecaster = SimpleForecaster()
                forecaster.train(historical_data)
                base_forecast = forecaster.forecast(horizon_days)
        else:
            # Fallback auf SimpleForecaster
            if historical_data:
                forecaster = SimpleForecaster()
                forecaster.train(historical_data)
                base_forecast = forecaster.forecast(horizon_days)
            else:
                # Keine Daten - nur Abonnements
                today = date.today()
                base_forecast = [
                    {
                        "date": (today + timedelta(days=i)).strftime("%Y-%m-%d"),
                        "predicted_quantity": 0,
                        "lower_bound": 0,
                        "upper_bound": 0
                    }
                    for i in range(horizon_days)
                ]

        # 4. Abonnement-Nachfrage hinzurechnen
        results = []
        for forecast in base_forecast:
            forecast_date = date.fromisoformat(forecast["date"])
            sub_demand = self.calculate_subscription_demand(subscriptions, forecast_date)

            total = forecast["predicted_quantity"] + sub_demand

            results.append({
                "date": forecast["date"],
                "predicted_quantity": forecast["predicted_quantity"],
                "subscription_quantity": sub_demand,
                "total_quantity": round(total, 2),
                "lower_bound": round(forecast["lower_bound"] + sub_demand, 2),
                "upper_bound": round(forecast["upper_bound"] + sub_demand, 2)
            })

        return results


def run_forecast_for_product(
    seed_id: UUID,
    horizon_days: int = 14
) -> list[dict]:
    """
    Convenience-Funktion für Produkt-Forecast.
    """
    pipeline = SalesForecastPipeline()
    return pipeline.run_forecast(seed_id, horizon_days)
