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
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Sicherheit
    secret_key: str = "your-secret-key-change-in-production"
    access_token_expire_minutes: int = 60 * 24  # 24 Stunden
    auth_disabled: bool = False
    basic_auth_enabled: bool = False
    basic_auth_user_1: str = ""
    basic_auth_password_1: str = ""
    basic_auth_user_2: str = ""
    basic_auth_password_2: str = ""

    # Keycloak
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "minga-greens"
    keycloak_client_id: str = "minga-backend"

    # E-Mail (SMTP)
    smtp_host: str = "localhost"
    smtp_port: int = 1025 # Mailpit default
    smtp_user: str = ""
    smtp_password: str = ""
    emails_from_email: str = "info@minga-greens.de"
    emails_from_name: str = "Minga Greens"

    # Dunning / Mahnwesen
    dunning_level1_days: int = 3      # Tage nach Fälligkeit → 1. Mahnung
    dunning_level2_days: int = 14     # Tage nach Fälligkeit → 2. Mahnung
    dunning_level3_days: int = 28     # Tage nach Fälligkeit → 3. Mahnung (letzte)
    dunning_fee_level2: float = 5.0   # Mahngebühr 2. Stufe (EUR)
    dunning_fee_level3: float = 10.0  # Mahngebühr 3. Stufe (EUR)

    # Quality Control / Qualitätskontrolle
    quality_min_note: int = 2              # Mindest-Qualitätsnote (1–5) für Freigabe
    quality_max_loss_percent: float = 20.0 # Maximale Verlustquote (%) für Auto-Freigabe

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3002",
        "http://localhost:5173",
    ]

    class Config:
        env_file = ".env"
        extra = "ignore"

    def validate_production(self) -> list[str]:
        """Prüft ob Produktions-Einstellungen gesetzt sind."""
        warnings = []
        if self.secret_key.startswith("your-secret-key"):
            warnings.append("SECRET_KEY ist noch der Standardwert — bitte ändern!")
        if "minga_secret" in self.database_url and not self.debug:
            warnings.append("DATABASE_URL verwendet Standard-Passwort")
        return warnings


@lru_cache
def get_settings() -> Settings:
    """Cached Settings-Instanz"""
    return Settings()
