"""
Datenbankverbindung und Session-Management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import get_settings

settings = get_settings()

# Engine erstellen
if settings.database_url.startswith("sqlite"):
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
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
