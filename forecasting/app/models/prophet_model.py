"""
Prophet Forecasting Model
Zeitreihenanalyse mit Saisonalität und deutschen Feiertagen
"""
import logging
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import numpy as np
from prophet import Prophet
import holidays

logger = logging.getLogger(__name__)


class ProphetForecaster:
    """
    Prophet-basierter Forecaster für Microgreens-Absatz.

    Features:
    - Wochentags-Saisonalität (Restaurants bestellen Di-Fr mehr)
    - Deutsche Feiertage
    - Jahres-Saisonalität
    """

    def __init__(self):
        self.model: Optional[Prophet] = None
        self.german_holidays = self._get_german_holidays()

    def _get_german_holidays(self, years: list[int] = None) -> pd.DataFrame:
        """Deutsche Feiertage für Prophet vorbereiten"""
        if years is None:
            current_year = date.today().year
            years = [current_year - 1, current_year, current_year + 1]

        de_holidays = holidays.Germany(years=years)

        holiday_df = pd.DataFrame([
            {"ds": pd.Timestamp(date_), "holiday": name, "lower_window": -1, "upper_window": 1}
            for date_, name in de_holidays.items()
        ])

        return holiday_df

    def prepare_data(self, historical_data: list[dict]) -> pd.DataFrame:
        """
        Daten für Prophet vorbereiten.

        Input:
            [{"date": "2025-01-15", "quantity": 2500}, ...]

        Output:
            DataFrame mit Spalten: ds, y
        """
        df = pd.DataFrame(historical_data)
        df.columns = ["ds", "y"]
        df["ds"] = pd.to_datetime(df["ds"])

        # Fehlende Tage auffüllen
        date_range = pd.date_range(start=df["ds"].min(), end=df["ds"].max(), freq="D")
        df = df.set_index("ds").reindex(date_range, fill_value=0).reset_index()
        df.columns = ["ds", "y"]

        return df

    def train(self, df: pd.DataFrame, include_holidays: bool = True) -> None:
        """
        Prophet-Model trainieren.

        Args:
            df: DataFrame mit ds, y Spalten
            include_holidays: Deutsche Feiertage einbeziehen
        """
        self.model = Prophet(
            # Wöchentliche Saisonalität (für Gastronomie wichtig)
            weekly_seasonality=True,
            # Jährliche Saisonalität
            yearly_seasonality=True,
            # Tägliche Saisonalität deaktiviert (wir haben Tageswerte)
            daily_seasonality=False,
            # Changepoint-Sensitivität
            changepoint_prior_scale=0.05,
            # Saisonalitäts-Stärke
            seasonality_prior_scale=10,
            # Feiertage
            holidays=self.german_holidays if include_holidays else None,
        )

        # Custom Saisonalität für Wochentage (Di-Fr höher als Mo, Sa, So)
        self.model.add_seasonality(
            name="weekday_pattern",
            period=7,
            fourier_order=3
        )

        self.model.fit(df)
        logger.info(f"Prophet model trained with {len(df)} data points")

    def forecast(
        self,
        horizon_days: int = 14,
        include_history: bool = False
    ) -> pd.DataFrame:
        """
        Prognose erstellen.

        Args:
            horizon_days: Anzahl Tage in die Zukunft
            include_history: Historische Werte mitliefern

        Returns:
            DataFrame mit: ds, yhat, yhat_lower, yhat_upper
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        future = self.model.make_future_dataframe(periods=horizon_days)
        forecast = self.model.predict(future)

        # Nur Zukunft oder mit Historie
        if not include_history:
            forecast = forecast.tail(horizon_days)

        # Negative Werte auf 0 setzen
        forecast["yhat"] = forecast["yhat"].clip(lower=0)
        forecast["yhat_lower"] = forecast["yhat_lower"].clip(lower=0)
        forecast["yhat_upper"] = forecast["yhat_upper"].clip(lower=0)

        return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]

    def get_forecast_dict(self, horizon_days: int = 14) -> list[dict]:
        """
        Prognose als Liste von Dictionaries.

        Returns:
            [
                {
                    "date": "2026-01-24",
                    "predicted_quantity": 2800.5,
                    "lower_bound": 2200.0,
                    "upper_bound": 3400.0
                },
                ...
            ]
        """
        forecast = self.forecast(horizon_days)

        return [
            {
                "date": row["ds"].strftime("%Y-%m-%d"),
                "predicted_quantity": round(row["yhat"], 2),
                "lower_bound": round(row["yhat_lower"], 2),
                "upper_bound": round(row["yhat_upper"], 2)
            }
            for _, row in forecast.iterrows()
        ]


class SimpleForecaster:
    """
    Einfacher Fallback-Forecaster ohne Prophet.
    Verwendet gleitende Durchschnitte und Wochentags-Muster.
    """

    def __init__(self):
        self.weekday_factors: dict[int, float] = {}
        self.base_demand: float = 0

    def train(self, historical_data: list[dict]) -> None:
        """
        Trainiert einfaches Modell basierend auf Wochentags-Durchschnitten.
        """
        df = pd.DataFrame(historical_data)
        df.columns = ["ds", "y"]
        df["ds"] = pd.to_datetime(df["ds"])
        df["weekday"] = df["ds"].dt.weekday

        # Durchschnitt pro Wochentag
        weekday_avg = df.groupby("weekday")["y"].mean()
        overall_avg = df["y"].mean()

        self.base_demand = overall_avg
        self.weekday_factors = (weekday_avg / overall_avg).to_dict()

        # Fehlende Wochentage mit 1.0 auffüllen
        for i in range(7):
            if i not in self.weekday_factors:
                self.weekday_factors[i] = 1.0

    def forecast(self, horizon_days: int = 14) -> list[dict]:
        """
        Einfache Prognose mit Wochentags-Faktoren.
        """
        today = date.today()
        results = []

        for i in range(horizon_days):
            forecast_date = today + timedelta(days=i)
            weekday = forecast_date.weekday()
            factor = self.weekday_factors.get(weekday, 1.0)

            predicted = self.base_demand * factor
            # Konfidenzintervall: ±25%
            margin = predicted * 0.25

            results.append({
                "date": forecast_date.strftime("%Y-%m-%d"),
                "predicted_quantity": round(predicted, 2),
                "lower_bound": round(max(0, predicted - margin), 2),
                "upper_bound": round(predicted + margin, 2)
            })

        return results
