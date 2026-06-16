"""
Datenbankverbindung und Session-Management
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import get_settings

settings = get_settings()

# Engine erstellen
if settings.database_url.startswith("sqlite"):
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )

    # SQLites eingebautes lower() faltet nur ASCII -> Umlaute (Ö/Ä/Ü) bleiben
    # unverändert, wodurch .ilike()-Suchen (kompiliert zu lower(x) LIKE lower(y))
    # z.B. "ökoring" nicht auf "Ökoring" matchen. Wir ersetzen lower() durch
    # Pythons Unicode-fähige Variante. Prod läuft auf SQLite, daher essenziell.
    @event.listens_for(engine, "connect")
    def _register_unicode_lower(dbapi_conn, _connection_record):
        dbapi_conn.create_function(
            "lower", 1,
            lambda s: s.lower() if isinstance(s, str) else s,
            deterministic=True,
        )
else:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_recycle=3600,
    )

# Session Factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Basis-Klasse für alle SQLAlchemy Models"""
    pass


def get_db():
    """
    Dependency für FastAPI - liefert eine DB-Session.
    Wird automatisch nach dem Request geschlossen.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
