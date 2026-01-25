"""
Datenbankverbindung und Session-Management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import get_settings

settings = get_settings()

# Engine erstellen
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
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
