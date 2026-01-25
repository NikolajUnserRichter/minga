"""
Konfiguration für Forecasting Service
"""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Forecasting Service Einstellungen"""

    # Datenbank
    database_url: str = "postgresql://minga:minga_secret@localhost:5432/minga_erp"

    # Redis für Caching
    redis_url: str = "redis://localhost:6379/1"

    # Model Cache
    model_cache_dir: str = "/app/models_cache"

    # Forecast Defaults
    default_horizon_days: int = 14
    min_history_days: int = 30

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
