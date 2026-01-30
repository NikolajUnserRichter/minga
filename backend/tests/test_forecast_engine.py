import unittest
from unittest.mock import MagicMock, patch
from datetime import date, timedelta
from decimal import Decimal
import pandas as pd
import numpy as np

from app.services.forecast_engine import ForecastEngine

class TestForecastEngine(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.engine = ForecastEngine(self.mock_db)

    def test_fetch_historical_data_empty(self):
        """Test fetching with no data"""
        self.mock_db.execute.return_value.all.return_value = []
        df = self.engine._fetch_historical_data("seed-123")
        self.assertTrue(df.empty)
        self.assertListEqual(list(df.columns), ["ds", "y"])

    def test_fetch_historical_data_success(self):
        """Test fetching valid data"""
        mock_row1 = MagicMock()
        mock_row1.ds = date(2023, 1, 1)
        mock_row1.y = 100
        
        mock_row2 = MagicMock()
        mock_row2.ds = date(2023, 1, 2)
        mock_row2.y = 200
        
        self.mock_db.execute.return_value.all.return_value = [mock_row1, mock_row2]
        
        df = self.engine._fetch_historical_data("seed-123")
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]["y"], 100.0)
        self.assertEqual(df.iloc[1]["y"], 200.0)

    def test_prepare_features(self):
        """Test feature engineering"""
        df = pd.DataFrame({
            "ds": [pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-02")],
            "y": [100.0, 200.0]
        })
        
        df_features = self.engine._prepare_features(df)
        
        self.assertIn("day_of_week", df_features.columns)
        self.assertIn("month", df_features.columns)
        self.assertIn("day_of_year", df_features.columns)
        self.assertIn("days_since_start", df_features.columns)
        
        self.assertEqual(df_features.iloc[0]["day_of_week"], 6) # Sunday
        self.assertEqual(df_features.iloc[0]["days_since_start"], 0)
        self.assertEqual(df_features.iloc[1]["days_since_start"], 1)

    def test_predict_simple_average(self):
        """Test fallback prediction"""
        df = pd.DataFrame({
            "ds": [pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-02")],
            "y": [100.0, 200.0]
        })
        
        results = self.engine._predict_simple_average(df, horizon_days=2)
        
        self.assertEqual(len(results), 2)
        # Avg should be 150
        self.assertEqual(results[0][1], Decimal("150.00"))
        
    def test_train_and_predict_insufficient_data(self):
        """Test that insufficient data triggers fallback"""
        # Mock fetch to return small df
        with patch.object(self.engine, "_fetch_historical_data") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame({
                "ds": [pd.Timestamp("2023-01-01")],
                "y": [100.0]
            })
            
            results = self.engine.train_and_predict("seed-123", horizon_days=5)
            self.assertEqual(len(results), 5)
            self.assertEqual(results[0][1], Decimal("100.00"))

    def test_train_and_predict_full_flow(self):
        """Test full flow with sklearn model"""
        # Create dummy data (enough points > 5)
        dates = pd.date_range(start="2023-01-01", periods=10, freq="D")
        y = [100.0] * 10
        df = pd.DataFrame({"ds": dates, "y": y})
        
        with patch.object(self.engine, "_fetch_historical_data", return_value=df):
            results = self.engine.train_and_predict("seed-123", horizon_days=2)
            
            self.assertEqual(len(results), 2)
            self.assertIsInstance(results[0][0], date)
            self.assertIsInstance(results[0][1], Decimal)
            # Should predict roughly 100 given constant input
            self.assertTrue(90 <= results[0][1] <= 110)

if __name__ == "__main__":
    unittest.main()
