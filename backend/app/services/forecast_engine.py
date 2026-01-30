import logging
from datetime import date, timedelta, datetime
from typing import List, Tuple, Optional
from decimal import Decimal

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder

from app.models.order import Order, OrderLine, OrderStatus
from app.models.seed import Seed

logger = logging.getLogger(__name__)

class ForecastEngine:
    def __init__(self, db: Session):
        self.db = db
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        
    def _fetch_historical_data(self, seed_id: str) -> pd.DataFrame:
        """
        Loads historical sales data for a specific seed.
        Aggregates daily sums.
        """
        query = (
            select(
                Order.requested_delivery_date.label("ds"),
                func.sum(OrderLine.quantity).label("y")
            )
            .join(Order.lines)
            .where(
                OrderLine.seed_id == seed_id,
                Order.status != OrderStatus.STORNIERT,
                Order.requested_delivery_date <= date.today()
            )
            .group_by(Order.requested_delivery_date)
            .order_by(Order.requested_delivery_date)
        )
        
        results = self.db.execute(query).all()
        
        if not results:
            return pd.DataFrame(columns=["ds", "y"])
            
        data = [{"ds": row.ds, "y": float(row.y)} for row in results]
        df = pd.DataFrame(data)
        df["ds"] = pd.to_datetime(df["ds"])
        return df

    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Feature Engineering:
        - Day of week
        - Month
        - Day of year
        - Rolling averages (if possible)
        """
        if df.empty:
            return df
            
        df = df.sort_values("ds")
        
        # Date features
        df["day_of_week"] = df["ds"].dt.dayofweek
        df["month"] = df["ds"].dt.month
        df["day_of_year"] = df["ds"].dt.dayofyear
        df["year"] = df["ds"].dt.year
        
        # Days since start (trend)
        min_date = df["ds"].min()
        df["days_since_start"] = (df["ds"] - min_date).dt.days
        
        return df

    def train_and_predict(self, seed_id: str, horizon_days: int = 14) -> List[Tuple[date, Decimal]]:
        """
        Trains the model on historical data and predicts for the next `horizon_days`.
        Returns a list of (date, predicted_amount).
        """
        logger.info(f"Generating forecast for seed {seed_id} (horizon={horizon_days})")
        
        # 1. Load Data
        df = self._fetch_historical_data(seed_id)
        
        # Fallback if insufficient data (< 5 data points)
        if len(df) < 5:
            logger.warning(f"Insufficient data for seed {seed_id} ({len(df)} points). Using simple average.")
            return self._predict_simple_average(df, horizon_days)
            
        # 2. Prepare Features
        # Fill missing dates with 0 for better training (sales gaps usually mean 0 sales)
        full_range = pd.date_range(start=df["ds"].min(), end=df["ds"].max(), freq="D")
        df = df.set_index("ds").reindex(full_range, fill_value=0).reset_index().rename(columns={"index": "ds"})
        
        df = self._prepare_features(df)
        
        # Features & Target
        # Simple set of features for now
        features = ["day_of_week", "month", "day_of_year", "days_since_start"]
        X = df[features]
        y = df["y"]
        
        # 3. Train Model
        try:
            self.model.fit(X, y)
        except Exception as e:
            logger.error(f"Model training failed for seed {seed_id}: {e}")
            return self._predict_simple_average(df, horizon_days)
            
        # 4. Predict Future
        future_dates = [date.today() + timedelta(days=i) for i in range(horizon_days)]
        future_df = pd.DataFrame({"ds": pd.to_datetime(future_dates)})
        
        # Add same features to future df
        min_date = df["ds"].min()
        future_df["year"] = future_df["ds"].dt.year # needed implicitly? no, but good for completeness
        future_df["day_of_week"] = future_df["ds"].dt.dayofweek
        future_df["month"] = future_df["ds"].dt.month
        future_df["day_of_year"] = future_df["ds"].dt.dayofyear
        future_df["days_since_start"] = (future_df["ds"] - min_date).dt.days
        
        X_future = future_df[features]
        predictions = self.model.predict(X_future)
        
        # 5. Format Results
        results = []
        for dt, pred in zip(future_dates, predictions):
            # Ensure non-negative and round to 2 decimals
            amount = Decimal(str(max(0.0, round(float(pred), 2))))
            results.append((dt, amount))
            
        return results

    def _predict_simple_average(self, df: pd.DataFrame, horizon_days: int) -> List[Tuple[date, Decimal]]:
        """
        Fallback: Calculates simple average of past sales.
        If empty, returns 0.
        """
        if df.empty:
            avg = 0.0
        else:
            # Only consider non-zero days? Or all days? 
            # If we reindexed with 0s, mean includes 0s. 
            # If we pass raw df, it only has sales days.
            # Let's use simple mean of existing sales records to be optimistic, 
            # or maybe last 30 days average?
            avg = df["y"].mean()
            
        amount = Decimal(str(max(0.0, round(float(avg), 2))))
        
        results = []
        for i in range(horizon_days):
            dt = date.today() + timedelta(days=i)
            results.append((dt, amount))
            
        return results
