"""Multi-Tenant-Routing: pro Subdomain eine eigene SQLite-Datenbank.

Architektur
-----------
1 FastAPI-Prozess  →  N Tenants  →  je 1 SQLite-Datei unter ``TENANTS_DIR``

Tenant-Resolution:
    minga.sprouddesk.de         →  /data/tenants/minga.db
    demo.sprouddesk.de          →  /data/tenants/demo.db
    kunde1.sprouddesk.de        →  /data/tenants/kunde1.db
    localhost / 127.0.0.1       →  Default-Tenant (DEFAULT_TENANT_SLUG)
    apex sprouddesk.de          →  Marketing-Slot, kein Tenant (HTTP 404 für /api/*)

Vorteile:
    * Daten-Isolation auf File-Ebene (kein Cross-Tenant-Bug möglich)
    * DSGVO-Löschanfrage = rm slug.db
    * Backup pro Kunde trivial
    * Onboarding eines Neukunden = 1 API-Call

Limit:
    SQLite skaliert komfortabel bis ~50 parallele Tenants. Darüber lieber
    Postgres-Schema-per-Tenant oder Row-Level-Multi-Tenancy.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()

# --- Konfiguration -------------------------------------------------------

# Root-Domain (alles davor ist der Tenant-Slug).
# z.B. ROOT_DOMAIN="sprouddesk.de" → minga.sprouddesk.de → slug="minga"
ROOT_DOMAIN: str = os.getenv("SPROUDDESK_ROOT_DOMAIN", "sprouddesk.de").lower().strip()

# Wo die Tenant-SQLite-Dateien liegen.
TENANTS_DIR: Path = Path(os.getenv("TENANTS_DIR", "./data/tenants")).resolve()

# Default-Tenant für Dev (localhost / kein Host-Header / IP-Zugriff).
DEFAULT_TENANT_SLUG: str = os.getenv("DEFAULT_TENANT_SLUG", "dev")

# Gültige Slug-Pattern: a-z, 0-9, dash, 2-32 chars, kein führender/abschließender dash.
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$")

# Reservierte Subdomains, die KEIN Tenant-Routing triggern.
RESERVED_SUBDOMAINS = {"www", "coolify", "api", "admin", "static", "mail", "smtp"}


# --- Engine-Cache --------------------------------------------------------

class _TenantRegistry:
    """Thread-safe Cache von Engine + Session-Factory pro Tenant.

    Engines sind teuer zu erzeugen (Pool-Setup, SQLite-Connect-Hooks),
    deshalb halten wir sie pro Prozess-Lifetime im Speicher.
    """

    def __init__(self) -> None:
        self._engines: dict[str, Engine] = {}
        self._sessions: dict[str, sessionmaker] = {}
        self._lock = threading.RLock()

    def get_engine(self, slug: str) -> Engine:
        with self._lock:
            eng = self._engines.get(slug)
            if eng is not None:
                return eng
            eng = self._build_engine(slug)
            self._engines[slug] = eng
            self._sessions[slug] = sessionmaker(autocommit=False, autoflush=False, bind=eng)
            logger.info(f"[tenancy] engine bereit für tenant='{slug}' → {self.path_for(slug)}")
            return eng

    def get_sessionmaker(self, slug: str) -> sessionmaker:
        with self._lock:
            if slug not in self._sessions:
                self.get_engine(slug)  # legt beides an
            return self._sessions[slug]

    def known_slugs(self) -> list[str]:
        """Slugs aus dem Filesystem ableiten (Quelle der Wahrheit)."""
        TENANTS_DIR.mkdir(parents=True, exist_ok=True)
        return sorted(p.stem for p in TENANTS_DIR.glob("*.db"))

    def path_for(self, slug: str) -> Path:
        return TENANTS_DIR / f"{slug}.db"

    def exists(self, slug: str) -> bool:
        return self.path_for(slug).is_file()

    def _build_engine(self, slug: str) -> Engine:
        TENANTS_DIR.mkdir(parents=True, exist_ok=True)
        db_path = self.path_for(slug)
        url = f"sqlite:///{db_path}"
        eng = create_engine(
            url,
            connect_args={"check_same_thread": False},
            # Per-Tenant kleines Connection-Pool — SQLite verträgt nicht viel Parallelität.
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=False,
            pool_recycle=-1,
        )

        # SQLites eingebautes lower() faltet nur ASCII — Umlaute bleiben.
        # Pythons Unicode-fähige Variante einhängen damit .ilike() korrekt matcht.
        @event.listens_for(eng, "connect")
        def _register_unicode_lower(dbapi_conn, _connection_record):
            dbapi_conn.create_function(
                "lower", 1,
                lambda s: s.lower() if isinstance(s, str) else s,
                deterministic=True,
            )
            # WAL = bessere Concurrency, Lesen blockiert keine Writes.
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        return eng

    def dispose_all(self) -> None:
        """Schließt alle Engines (Shutdown)."""
        with self._lock:
            for slug, eng in self._engines.items():
                try:
                    eng.dispose()
                except Exception as e:
                    logger.warning(f"[tenancy] dispose '{slug}': {e}")
            self._engines.clear()
            self._sessions.clear()


registry = _TenantRegistry()


# --- Tenant-Resolution ---------------------------------------------------

def is_valid_slug(slug: str) -> bool:
    if not slug:
        return False
    if slug in RESERVED_SUBDOMAINS:
        return False
    return bool(_SLUG_RE.match(slug))


def resolve_slug_from_host(host: Optional[str]) -> Optional[str]:
    """Extrahiert den Tenant-Slug aus dem Host-Header.

    Returns:
        slug (str) wenn auflösbar, sonst None (Apex-Domain oder ungültig).
    """
    if not host:
        return None

    # Port abschneiden
    host = host.split(":", 1)[0].lower().strip()

    # localhost / IP → Default-Tenant für Dev
    if host in {"localhost", "127.0.0.1", "::1"} or _looks_like_ip(host):
        return DEFAULT_TENANT_SLUG

    # Muss auf ROOT_DOMAIN enden
    if not host.endswith("." + ROOT_DOMAIN) and host != ROOT_DOMAIN:
        # Unbekannte Domain → behandeln als Apex (kein Tenant)
        return None

    if host == ROOT_DOMAIN:
        # Apex sprouddesk.de — keine Subdomain → kein Tenant
        return None

    subdomain = host[: -(len(ROOT_DOMAIN) + 1)]
    # Bei verschachtelten Subdomains (foo.bar.sprouddesk.de) nur die linke nehmen
    slug = subdomain.split(".")[0]

    if not is_valid_slug(slug):
        return None
    return slug


def _looks_like_ip(host: str) -> bool:
    return bool(re.match(r"^[\d.]+$", host)) or ":" in host


# --- Provisioning --------------------------------------------------------

def provision_tenant(slug: str, *, seed_defaults: bool = True) -> Path:
    """Legt eine neue Tenant-DB an (Tabellen + minimaler Seed) und gibt den Pfad zurück.

    Idempotent: wenn die DB existiert wird create_all() trotzdem ausgeführt
    (kümmert sich nur um fehlende Tabellen).
    """
    if not is_valid_slug(slug):
        raise ValueError(f"Ungültiger Tenant-Slug: '{slug}'")

    # Modelle importieren — alle Models registrieren sich auf Base.metadata.
    from app.database import Base
    import app.models  # noqa: F401  - registriert Mappers

    engine = registry.get_engine(slug)
    Base.metadata.create_all(bind=engine)

    # Auto-Migrate: idempotente ALTER TABLEs für ältere Schemata.
    _auto_migrate(engine)

    if seed_defaults:
        _seed_minimal(registry.get_sessionmaker(slug))

    logger.info(f"[tenancy] tenant '{slug}' provisioned at {registry.path_for(slug)}")
    return registry.path_for(slug)


def init_all_existing_tenants() -> list[str]:
    """Beim Boot: über alle vorhandenen DB-Dateien iterieren und create_all + migrate ausführen.

    Returns:
        Liste der Slugs die initialisiert wurden.
    """
    from app.database import Base
    import app.models  # noqa: F401

    initialized: list[str] = []
    TENANTS_DIR.mkdir(parents=True, exist_ok=True)

    for slug in registry.known_slugs():
        try:
            engine = registry.get_engine(slug)
            Base.metadata.create_all(bind=engine)
            _auto_migrate(engine)
            initialized.append(slug)
        except Exception as e:
            logger.error(f"[tenancy] init failed for '{slug}': {e}")

    logger.info(f"[tenancy] {len(initialized)} tenants initialized: {initialized}")
    return initialized


def _auto_migrate(engine: Engine) -> None:
    """Idempotente Spalten-Migrationen — gleiche Logik wie zuvor in main.py."""
    from sqlalchemy import text, inspect
    inspector = inspect(engine)

    def _add_col_if_missing(table: str, column: str, ddl_type: str, default: str = ""):
        if not inspector.has_table(table):
            return
        cols = {c["name"] for c in inspector.get_columns(table)}
        if column in cols:
            return
        stmt = f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"
        if default:
            stmt += f" DEFAULT {default}"
        with engine.begin() as conn:
            conn.execute(text(stmt))
        logger.info(f"[auto-migrate] {table}.{column} added")

    try:
        _add_col_if_missing("customers", "skonto_percent",        "NUMERIC(5,2)", "0")
        _add_col_if_missing("customers", "skonto_days",           "INTEGER",      "0")
        _add_col_if_missing("customers", "packaging_fee_amount",  "NUMERIC(10,2)", "0")
        _add_col_if_missing("customers", "packaging_fee_percent", "NUMERIC(5,2)", "0")
        _add_col_if_missing("orders", "inventory_deducted_at", "DATETIME")
        # Handelsware-Bestandsbewegung (Tradesk-Einkauf) auf bestehenden Tenant-DBs
        _add_col_if_missing("inventory_movements", "trade_goods_id", "CHAR(32)")
    except Exception as e:
        logger.error(f"[auto-migrate] failed: {e}")


def _seed_minimal(SessionFactory: sessionmaker) -> None:
    """Minimaler Seed für neue Tenants: Einheiten."""
    from sqlalchemy import select, func
    from app.models.unit import UnitOfMeasure, UnitCategory

    with SessionFactory() as db:
        count = db.execute(select(func.count()).select_from(UnitOfMeasure)).scalar() or 0
        if count > 0:
            return
        seeds = [
            ("G", "Gramm", "g", UnitCategory.WEIGHT, 1, True, 10),
            ("KG", "Kilogramm", "kg", UnitCategory.WEIGHT, 1000, False, 20),
            ("STK", "Stück", "Stk", UnitCategory.COUNT, 1, True, 30),
            ("SCHALE", "Schale", "Schale", UnitCategory.CONTAINER, 1, True, 40),
            ("TRAY", "Tray (8 Schalen)", "Tray", UnitCategory.CONTAINER, 8, False, 50),
            ("KISTE_12", "Mehrwegkiste 12 Schalen", "Kiste 12", UnitCategory.CONTAINER, 12, False, 60),
            ("KISTE_6", "Mehrwegkiste 6 Schalen", "Kiste 6", UnitCategory.CONTAINER, 6, False, 70),
            ("KARTON_6", "Karton 6 Schalen", "Karton 6", UnitCategory.CONTAINER, 6, False, 80),
        ]
        for code, name, symbol, cat, factor, is_base, order in seeds:
            db.add(UnitOfMeasure(
                code=code, name=name, symbol=symbol, category=cat,
                conversion_factor=factor, is_base_unit=is_base, is_active=True, sort_order=order,
            ))
        db.commit()
        logger.info(f"[tenancy] seeded units_of_measure")


# --- FastAPI-Integration -------------------------------------------------

_TENANT_STATE_KEY = "tenant_slug"


def get_request_tenant(request) -> Optional[str]:
    """Liest den vom Middleware aufgelösten Tenant aus dem Request-State."""
    return getattr(request.state, _TENANT_STATE_KEY, None)


def set_request_tenant(request, slug: str) -> None:
    setattr(request.state, _TENANT_STATE_KEY, slug)


# --- Context-Var für Hintergrund-Tasks (Scheduler) -----------------------
# Erlaubt dem Legacy-SessionLocal()-Aufruf-Pattern in app/tasks/*.py, ohne
# Refactor weiterhin zu funktionieren: der Scheduler setzt vor jedem Task
# den aktuellen Tenant, und `SessionLocal()` (Legacy-Proxy in database.py)
# liest ihn aus.
_current_tenant: ContextVar[Optional[str]] = ContextVar("current_tenant", default=None)


def set_current_tenant(slug: Optional[str]) -> None:
    _current_tenant.set(slug)


def get_current_tenant() -> Optional[str]:
    return _current_tenant.get()
