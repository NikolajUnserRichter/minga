"""
Konfiguration für Minga-Greens ERP Backend
"""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Anwendungseinstellungen aus Umgebungsvariablen"""

    # Anwendung
    app_name: str = "Minga-Greens ERP"
    app_version: str = "1.0.0"
    debug: bool = False

    # Datenbank
    database_url: str = "postgresql://minga:minga_secret@localhost:5432/minga_erp"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Sicherheit
    secret_key: str = "your-secret-key-change-in-production"
    access_token_expire_minutes: int = 60 * 24  # 24 Stunden

    # Keycloak
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "minga-greens"
    keycloak_client_id: str = "minga-backend"

    # Forecasting Service
    forecasting_service_url: str = "http://localhost:8001"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Cached Settings-Instanz"""
    return Settings()
