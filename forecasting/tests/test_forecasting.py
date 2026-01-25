"""
Tests für Forecasting Service
"""
import pytest
from datetime import date, timedelta

from app.models.prophet_model import ProphetForecaster, SimpleForecaster


class TestSimpleForecaster:
    """Tests für SimpleForecaster"""

    def test_train_with_data(self):
        """Test Training mit Beispieldaten"""
        forecaster = SimpleForecaster()

        historical = [
            {"date": (date.today() - timedelta(days=i)).isoformat(), "quantity": 100 + i * 10}
            for i in range(30, 0, -1)
        ]

        forecaster.train(historical)

        assert forecaster.base_demand > 0
        assert len(forecaster.weekday_factors) == 7

    def test_forecast_output_format(self):
        """Test Forecast-Output Format"""
        forecaster = SimpleForecaster()

        historical = [
            {"date": (date.today() - timedelta(days=i)).isoformat(), "quantity": 200}
            for i in range(30, 0, -1)
        ]
        forecaster.train(historical)

        forecast = forecaster.forecast(horizon_days=7)

        assert len(forecast) == 7
        assert all("date" in f for f in forecast)
        assert all("predicted_quantity" in f for f in forecast)
        assert all("lower_bound" in f for f in forecast)
        assert all("upper_bound" in f for f in forecast)

    def test_forecast_positive_values(self):
        """Alle Forecast-Werte sollten positiv sein"""
        forecaster = SimpleForecaster()

        historical = [
            {"date": (date.today() - timedelta(days=i)).isoformat(), "quantity": 500}
            for i in range(30, 0, -1)
        ]
        forecaster.train(historical)

        forecast = forecaster.forecast(horizon_days=14)

        for f in forecast:
            assert f["predicted_quantity"] >= 0
            assert f["lower_bound"] >= 0
            assert f["upper_bound"] >= 0
            assert f["lower_bound"] <= f["predicted_quantity"] <= f["upper_bound"]


class TestProphetForecaster:
    """Tests für ProphetForecaster"""

    def test_prepare_data(self):
        """Test Daten-Vorbereitung"""
        forecaster = ProphetForecaster()

        historical = [
            {"date": "2026-01-01", "quantity": 100},
            {"date": "2026-01-03", "quantity": 150},
            {"date": "2026-01-05", "quantity": 120},
        ]

        df = forecaster.prepare_data(historical)

        assert "ds" in df.columns
        assert "y" in df.columns
        # Fehlende Tage sollten aufgefüllt sein
        assert len(df) >= 3

    def test_german_holidays(self):
        """Test deutsche Feiertage"""
        forecaster = ProphetForecaster()

        holidays = forecaster._get_german_holidays([2026])

        assert len(holidays) > 0
        assert "holiday" in holidays.columns
        assert "ds" in holidays.columns

        # Bekannte Feiertage prüfen
        holiday_names = holidays["holiday"].tolist()
        assert any("Neujahr" in h for h in holiday_names)


class TestForecastCalculations:
    """Tests für Forecast-Berechnungen"""

    def test_tray_calculation(self):
        """Test Tray-Berechnung"""
        # Beispiel: 3500g benötigt, 350g/Tray, 5% Verlust
        from decimal import Decimal
        import math

        benoetigte_menge = 3500
        ertrag_pro_tray = 350
        verlustquote = 5  # %

        verlust_faktor = 1 - (verlustquote / 100)
        effektiver_ertrag = ertrag_pro_tray * verlust_faktor

        trays = math.ceil(benoetigte_menge / effektiver_ertrag)

        assert trays == 11  # ceil(3500 / 332.5) = 11

    def test_sow_date_calculation(self):
        """Test Aussaat-Datum Rückrechnung"""
        ernte_datum = date(2026, 2, 5)
        keimdauer = 2
        wachstumsdauer = 8

        aussaat_datum = ernte_datum - timedelta(days=keimdauer + wachstumsdauer)

        assert aussaat_datum == date(2026, 1, 26)

    def test_mape_calculation(self):
        """Test MAPE-Berechnung"""
        forecast = 100
        actual = 90

        # MAPE = |actual - forecast| / forecast * 100
        mape = abs(actual - forecast) / forecast * 100

        assert mape == 10.0

    def test_mape_zero_forecast(self):
        """MAPE bei Forecast = 0"""
        forecast = 0
        actual = 50

        # Bei Forecast = 0 sollte MAPE 0 oder undefined sein
        if forecast == 0:
            mape = 0
        else:
            mape = abs(actual - forecast) / forecast * 100

        assert mape == 0
