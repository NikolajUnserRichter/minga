"""Datenbank-Verbindung — Multi-Tenant via app/tenancy.py.

Behält die alte API (``Base``, ``get_db``, ``SessionLocal``) für Backwards-
Compat, leitet ``get_db()`` jedoch an die tenant-spezifische Engine durch.

Wichtig:
    * Modelle nutzen weiterhin ``from app.database import Base`` — keine Code-Änderung
      nötig in den 30+ Model-Dateien.
    * Endpoints nutzen weiterhin ``DBSession`` aus ``app.api.deps`` —
      die Session wird automatisch pro Request an die richtige Tenant-DB gebunden.
    * Hintergrund-Tasks (Scheduler, manuelle Skripte) müssen ``get_tenant_session(slug)``
      direkt nutzen, da kein Request-Context vorhanden ist.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy.orm import DeclarativeBase, Session

from app.tenancy import registry, get_request_tenant, get_current_tenant, DEFAULT_TENANT_SLUG

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Basis-Klasse für alle SQLAlchemy Models. Geteilt über alle Tenants."""
    pass


def get_db(request=None) -> Generator[Session, None, None]:
    """FastAPI-Dependency: liefert eine Session gebunden an den Tenant des Requests.

    Wird ohne Request aufgerufen (z.B. aus Hintergrund-Tasks), fällt sie auf den
    Default-Tenant zurück und loggt eine Warnung — das sollte in Prod nicht passieren.
    """
    slug: Optional[str] = None
    if request is not None:
        slug = get_request_tenant(request)
    if not slug:
        logger.warning("[db] get_db() ohne Tenant-Kontext — fallback auf Default")
        slug = DEFAULT_TENANT_SLUG

    SessionFactory = registry.get_sessionmaker(slug)
    db = SessionFactory()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_tenant_session(slug: str) -> Generator[Session, None, None]:
    """Kontext-Manager für Hintergrund-Tasks ohne Request.

    Beispiel:
        with get_tenant_session("minga") as db:
            db.execute(...)
    """
    SessionFactory = registry.get_sessionmaker(slug)
    db = SessionFactory()
    try:
        yield db
    finally:
        db.close()


# --- Legacy-Bridge -------------------------------------------------------
# Einige bestehende Module importieren ``engine`` oder ``SessionLocal`` direkt.
# Wir bieten beides als Default-Tenant-Bridge an — sollte mittelfristig migriert
# werden, blockiert aber den Roll-out nicht.

def _active_slug() -> str:
    """Legacy-Auflösung: ContextVar > Default-Tenant."""
    return get_current_tenant() or DEFAULT_TENANT_SLUG


def _default_engine():
    return registry.get_engine(_active_slug())


def _default_sessionmaker():
    return registry.get_sessionmaker(_active_slug())


class _LazyEngine:
    """Proxy: lädt den Default-Tenant-Engine bei erstem Zugriff."""
    def __getattr__(self, name):
        return getattr(_default_engine(), name)


class _LazySessionLocal:
    """Proxy: bei Aufruf wird der Default-Tenant-Sessionmaker erzeugt."""
    def __call__(self, *args, **kwargs):
        return _default_sessionmaker()(*args, **kwargs)


engine = _LazyEngine()
SessionLocal = _LazySessionLocal()
