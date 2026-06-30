"""
NovaERP - FastAPI Backend
Hauptanwendung und Router-Konfiguration
"""
import logging
import os
import time
import uuid
import base64
import binascii
import secrets
from typing import Optional
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import engine, Base
from app.tenancy import (
    init_all_existing_tenants, provision_tenant, registry as tenant_registry,
    resolve_slug_from_host, set_request_tenant, DEFAULT_TENANT_SLUG,
)
from app.api.v1 import seeds, production, sales, forecasting, products, invoices, inventory, analytics, capacity, suppliers, units, imports, documents, attachments, admin, document_templates, platform
from app.api.deps import get_current_user
from app.core.security import verify_token

logger = logging.getLogger(__name__)
settings = get_settings()

# Rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

# All API routes require authentication
_auth_deps = [Depends(get_current_user)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup und Shutdown Events"""
    # Validate production settings
    warnings = settings.validate_production()
    for w in warnings:
        logger.warning(f"[CONFIG] {w}")

    # Multi-Tenant Init: alle existierenden Tenant-DBs entdecken + Tabellen
    # erstellen + auto-migrate. Pro Tenant eine SQLite-Datei in TENANTS_DIR.
    existing = init_all_existing_tenants()
    logger.info(f"[startup] {len(existing)} existing tenants initialized: {existing}")

    # Default-Tenants beim ersten Start auto-provisionieren — komma-separierte Slugs in env.
    import os as _os
    default_tenants = [s.strip() for s in _os.environ.get("DEFAULT_TENANTS", "").split(",") if s.strip()]
    if default_tenants:
        for slug in default_tenants:
            if not tenant_registry.exists(slug):
                try:
                    provision_tenant(slug, seed_defaults=True)
                    logger.warning(f"[startup] auto-provisioned default tenant '{slug}'")
                except Exception as e:
                    logger.error(f"[startup] could not provision '{slug}': {e}")

    # Idempotenter Backfill für Kundennummern (pro Tenant).
    try:
        from sqlalchemy import text
        from app.database import get_tenant_session
        for slug in tenant_registry.known_slugs():
            with get_tenant_session(slug) as _db:
                conn = _db.connection()
                existing_nums = conn.execute(
                    text("SELECT customer_number FROM customers WHERE customer_number LIKE 'KD-%'")
                ).fetchall()
                max_num = 10000
                for (cn,) in existing_nums:
                    try:
                        n = int(str(cn).split("-")[-1])
                    except (ValueError, IndexError):
                        continue
                    max_num = max(max_num, n)

                missing = conn.execute(
                    text(
                        "SELECT id FROM customers "
                        "WHERE customer_number IS NULL OR customer_number = '' "
                        "ORDER BY created_at, name, id"
                    )
                ).fetchall()

                next_num = max_num + 1
                for (cid,) in missing:
                    conn.execute(
                        text("UPDATE customers SET customer_number = :cn WHERE id = :id"),
                        {"cn": f"KD-{next_num:05d}", "id": cid},
                    )
                    next_num += 1
                if missing:
                    _db.commit()
                    logger.warning(f"[customer-backfill][{slug}] {len(missing)} Kundennummern vergeben")
    except Exception as e:
        logger.error(f"[customer-backfill] failed: {e}")

    # In-Process-Scheduler starten (Celery-Ersatz im Demo-Deploy)
    try:
        from app.services.scheduler_service import start_scheduler
        start_scheduler()
    except Exception as e:
        logger.error(f"[scheduler] start failed: {e}")

    yield

    # Shutdown: Scheduler sauber stoppen
    try:
        from app.services.scheduler_service import shutdown_scheduler
        shutdown_scheduler()
    except Exception as e:
        logger.warning(f"[scheduler] shutdown failed: {e}")


# Serialize Decimals as JSON numbers (not strings) so the frontend can call
# .toFixed directly without wrapping every value in Number(...).
import json as _json
from decimal import Decimal as _Decimal
from fastapi.responses import JSONResponse as _JSONResponse


class _DecimalJSONResponse(_JSONResponse):
    def render(self, content) -> bytes:
        def default(o):
            if isinstance(o, _Decimal):
                return float(o)
            raise TypeError
        return _json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            default=default,
        ).encode("utf-8")


app = FastAPI(
    default_response_class=_DecimalJSONResponse,
    title=settings.app_name,
    version=settings.app_version,
    description="""
    ## NovaERP API

    Open-Source ERP-System für Microgreens-Produktion.

    ### Features
    - **Produktion**: Saatgut, Wachstumschargen, Ernten
    - **Vertrieb**: Kunden, Bestellungen, Abonnements
    - **Forecasting**: KI-gestützte Absatzprognosen
    - **Planung**: Automatische Produktionsvorschläge

    ### Authentifizierung
    Bearer Token via Keycloak
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

frontend_dist = Path("/app/static")
if frontend_dist.exists():
    assets_path = frontend_dist / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

# Marketing-Seite (apex novaerp.de) — separate Static-Dir, kein Auth nötig.
marketing_dist = Path("/app/static_marketing")
if not marketing_dist.exists():
    marketing_dist = Path(__file__).parent.parent / "static_marketing"

# Platform-Admin-UI (admin.novaerp.de) — eigener Static-Dir.
admin_dist = Path("/app/static_admin")
if not admin_dist.exists():
    admin_dist = Path(__file__).parent.parent / "static_admin"


def _root_domain() -> str:
    return os.environ.get("SPROUDDESK_ROOT_DOMAIN", "novaerp.de").lower()


def _is_apex_request(request: Request) -> bool:
    """Apex = novaerp.de ohne Subdomain (oder ROOT_DOMAIN-env-Vorgabe)."""
    host = (request.headers.get("host") or "").split(":")[0].lower()
    return host == _root_domain()


def _is_admin_request(request: Request) -> bool:
    """admin.novaerp.de → Platform-Admin-UI. Die UI selbst ist statisch;
    alle Aktionen sind durch den X-Platform-Admin-Key geschützt."""
    host = (request.headers.get("host") or "").split(":")[0].lower()
    return host == f"admin.{_root_domain()}"

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Correlation-ID"],
)


# === Tenant-Routing-Middleware ===========================================
# Liest den Host-Header, leitet Slug ab und legt ihn in request.state ab.
# Muss VOR dem basic_auth_middleware sitzen (= später hinzugefügt), damit
# alle nachfolgenden Middlewares + Dependencies ihn auslesen können.
@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    host = request.headers.get("host") or request.url.hostname
    slug = resolve_slug_from_host(host)

    # Plattform-Pfade die kein Tenant brauchen: /health, /api/v1/platform/*, /docs
    # + apex-Routes (Marketing-Seite serviert SPA-Files ohne Tenant)
    path = request.url.path
    _root = os.getenv("SPROUDDESK_ROOT_DOMAIN", "novaerp.de").lower()
    _host_only = host.split(":")[0].lower() if host else ""
    is_apex = _host_only == _root
    is_admin_host = _host_only == f"admin.{_root}"
    is_platform_path = (
        is_apex
        or is_admin_host
        or path.startswith("/health")
        or path.startswith("/api/v1/platform")
        or path.startswith("/docs")
        or path.startswith("/redoc")
        or path == "/openapi.json"
    )

    if slug is None and not is_platform_path:
        # Unbekannte Subdomain → 404, sofern nicht statische Frontend-Datei
        if path.startswith("/api/"):
            return JSONResponse(
                status_code=404,
                content={"detail": f"Tenant nicht gefunden für Host '{host}'"},
            )
        # SPA-Routes bekommen den Default-Tenant — sonst kann der User die
        # Marketing-Seite des apex-Hosts nicht laden.
        slug = DEFAULT_TENANT_SLUG

    if slug is not None:
        # Wenn die Slug-DB noch nicht existiert (Tenant nicht provisioniert),
        # 404 statt SQLite-Fehler.
        if not tenant_registry.exists(slug) and slug != DEFAULT_TENANT_SLUG and not is_platform_path:
            return JSONResponse(
                status_code=404,
                content={"detail": f"Tenant '{slug}' ist nicht bereitgestellt"},
            )
        set_request_tenant(request, slug)

    return await call_next(request)


def _identify_basic_auth_user(request: Request) -> Optional[dict]:
    """Decodet den Authorization-Header, prüft gegen alle Account-Slots
    und gibt {username, role} zurück. role ∈ {"FULL", "READONLY"}.
    None = nicht authentifiziert."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        return None

    token = auth_header[6:].strip()
    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None

    if ":" not in decoded:
        return None

    username, password = decoded.split(":", 1)
    # FULL-Access Accounts
    full_pairs = [
        (settings.basic_auth_user_1, settings.basic_auth_password_1),
        (settings.basic_auth_user_2, settings.basic_auth_password_2),
    ]
    for allowed_user, allowed_password in full_pairs:
        if not allowed_user or not allowed_password:
            continue
        if secrets.compare_digest(username, allowed_user) and secrets.compare_digest(password, allowed_password):
            return {"username": username, "role": "FULL"}

    # READONLY Demo-Account
    if (
        settings.basic_auth_user_readonly
        and settings.basic_auth_password_readonly
        and secrets.compare_digest(username, settings.basic_auth_user_readonly)
        and secrets.compare_digest(password, settings.basic_auth_password_readonly)
    ):
        return {"username": username, "role": "READONLY"}

    return None


# READ-only Methoden + Whitelist für Pfade die ein READONLY-User trotzdem
# triggern darf (z.B. PDF-Download via POST in seltenen Fällen — hier keiner)
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_READONLY_PATH_ALLOWLIST = {
    # nichts — alle Schreib-Routen sind für Demo-User gesperrt
}


def _jwt_readonly_blocked(request: Request) -> Optional[JSONResponse]:
    """Prüft Keycloak-Bearer-Token auf 'readonly'-Rolle und blockt Schreibmethoden.

    Läuft UNABHÄNGIG von basic_auth_enabled, damit die Demo-Read-Only-Sperre auch
    im reinen Keycloak-Betrieb greift. Gibt eine 403-Response zurück wenn geblockt,
    sonst None.
    """
    if settings.auth_disabled:
        return None
    auth_hdr = request.headers.get("Authorization", "")
    if not auth_hdr.startswith("Bearer "):
        return None
    if request.method not in _WRITE_METHODS or request.url.path in _READONLY_PATH_ALLOWLIST:
        return None
    token = auth_hdr.split(" ", 1)[1].strip()
    try:
        payload = verify_token(token)
    except Exception:
        return None  # ungültiges Token → andere Schichten lehnen ab (401)
    roles = payload.get("realm_access", {}).get("roles", [])
    write_roles = {"admin", "sales", "production_planner", "production_staff", "accounting"}
    if "readonly" in roles and not (write_roles & set(roles)):
        return JSONResponse(
            status_code=403,
            content={"detail": "Demo-Account hat nur Leserechte. Bitte als Vollnutzer einloggen, um Änderungen zu speichern."},
        )
    return None


@app.middleware("http")
async def basic_auth_middleware(request: Request, call_next):
    # READONLY-Enforcement für Keycloak-Tokens läuft IMMER (auch wenn Basic-Auth
    # aus ist — reiner Keycloak-Betrieb).
    if not _is_apex_request(request) and not _is_admin_request(request) and not request.url.path.startswith("/health"):
        ro = _jwt_readonly_blocked(request)
        if ro is not None:
            return ro

    if not settings.basic_auth_enabled:
        return await call_next(request)

    if request.url.path.startswith("/health"):
        return await call_next(request)

    # Apex (novaerp.de) = öffentliche Marketing-Seite. admin.novaerp.de =
    # Platform-Admin-UI (statisch; Aktionen sind durch X-Platform-Admin-Key
    # geschützt). Beide ohne Basic-Auth-Gate.
    if _is_apex_request(request) or _is_admin_request(request):
        return await call_next(request)

    # Bearer-Token (Keycloak-JWT) darf das Basic-Auth-Gate NUR überspringen,
    # wenn das Token kryptographisch gültig ist (readonly schon oben geprüft).
    auth_hdr = request.headers.get("Authorization", "")
    if not settings.auth_disabled and auth_hdr.startswith("Bearer "):
        token = auth_hdr.split(" ", 1)[1].strip()
        try:
            verify_token(token)
            return await call_next(request)
        except Exception:
            pass  # ungültiges Token → unten auf Basic-Auth zurückfallen (401)

    user = _identify_basic_auth_user(request)
    if user is None:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
            headers={"WWW-Authenticate": 'Basic realm="NovaERP"'},
        )

    # User-Identity in der Request-State ablegen — Endpoints + /whoami können sie auslesen
    request.state.basic_auth_user = user

    # READONLY-Demo: alle Schreib-Methoden blocken
    if (
        user["role"] == "READONLY"
        and request.method in _WRITE_METHODS
        and request.url.path not in _READONLY_PATH_ALLOWLIST
    ):
        return JSONResponse(
            status_code=403,
            content={"detail": "Demo-Account hat nur Leserechte. Bitte als Vollnutzer einloggen, um Änderungen zu speichern."},
        )

    return await call_next(request)


# Request logging & correlation ID middleware
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    response.headers["X-Correlation-ID"] = correlation_id
    logger.info(
        f"[{correlation_id[:8]}] {request.method} {request.url.path} "
        f"→ {response.status_code} ({duration:.3f}s)"
    )
    return response


# Health Check
@app.get("/health", tags=["System"])
async def health_check():
    """
    Systemstatus prüfen.
    Wird von Docker für Health Checks verwendet.
    """
    return {"status": "healthy", "version": settings.app_version}


@app.get("/api/v1/auth/whoami", tags=["System"])
async def whoami(request: Request):
    """Liefert username + role (FULL/READONLY) für UI-Banner und
    Frontend-Write-Gating. Wenn Basic-Auth aus ist → FULL."""
    user = getattr(request.state, "basic_auth_user", None)
    if user is None:
        return {"username": None, "role": "FULL"}
    return user


@app.get("/health/detailed", tags=["System"])
async def health_check_detailed():
    """
    Detaillierter Health Check — prüft DB, Redis und Keycloak.
    """
    import redis as redis_lib
    from sqlalchemy import text
    from app.database import SessionLocal

    checks: dict = {"version": settings.app_version}

    # --- PostgreSQL ---
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        checks["database"] = {"status": "healthy"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}

    # --- Redis ---
    try:
        r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=3)
        r.ping()
        checks["redis"] = {"status": "healthy"}
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)}

    # --- Keycloak ---
    try:
        import httpx
        resp = httpx.get(
            f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/.well-known/openid-configuration",
            timeout=5,
        )
        if resp.status_code == 200:
            checks["keycloak"] = {"status": "healthy"}
        else:
            checks["keycloak"] = {"status": "degraded", "http_status": resp.status_code}
    except Exception as e:
        checks["keycloak"] = {"status": "unhealthy", "error": str(e)}

    overall = "healthy" if all(
        c.get("status") == "healthy"
        for c in checks.values()
        if isinstance(c, dict)
    ) else "degraded"
    checks["status"] = overall

    status_code = 200 if overall == "healthy" else 503
    return JSONResponse(content=checks, status_code=status_code)


@app.get("/", tags=["System"])
async def root(request: Request):
    """Root-Handler — apex=Marketing, admin=Admin-UI, Subdomains=App."""
    if _is_admin_request(request):
        if (admin_dist / "index.html").exists():
            return FileResponse(admin_dist / "index.html")
    if _is_apex_request(request):
        if (marketing_dist / "index.html").exists():
            return FileResponse(marketing_dist / "index.html")
    if (frontend_dist / "index.html").exists():
        return FileResponse(frontend_dist / "index.html")
    return {
        "message": "Willkommen bei NovaERP",
        "version": settings.app_version,
        "docs": "/docs",
    }


# API Router einbinden
app.include_router(
    seeds.router,
    prefix="/api/v1/seeds",
    tags=["Saatgut"],
    dependencies=_auth_deps,
)

app.include_router(
    production.router,
    prefix="/api/v1/production",
    tags=["Produktion"],
    dependencies=_auth_deps,
)

app.include_router(
    sales.router,
    prefix="/api/v1/sales",
    tags=["Vertrieb"],
    dependencies=_auth_deps,
)

app.include_router(
    forecasting.router,
    prefix="/api/v1/forecasting",
    tags=["Forecasting"],
    dependencies=_auth_deps,
)

# ERP Module
app.include_router(
    products.router,
    prefix="/api/v1",
    dependencies=_auth_deps,
)

app.include_router(
    products.groups_router,
    prefix="/api/v1",
    dependencies=_auth_deps,
)

app.include_router(
    products.grow_plans_router,
    prefix="/api/v1",
    dependencies=_auth_deps,
)

app.include_router(
    products.price_lists_router,
    prefix="/api/v1",
    dependencies=_auth_deps,
)

app.include_router(
    invoices.router,
    prefix="/api/v1",
    dependencies=_auth_deps,
)

app.include_router(
    inventory.router,
    prefix="/api/v1",
    dependencies=_auth_deps,
)

app.include_router(
    capacity.router,
    prefix="/api/v1",
    dependencies=_auth_deps,
)

app.include_router(
    suppliers.router,
    prefix="/api/v1",
    dependencies=_auth_deps,
)

app.include_router(
    units.router,
    prefix="/api/v1",
    dependencies=_auth_deps,
)

app.include_router(
    imports.router,
    prefix="/api/v1",
    dependencies=_auth_deps,
)

app.include_router(
    documents.router,
    prefix="/api/v1/sales",
    tags=["Belegkette"],
    dependencies=_auth_deps,
)

app.include_router(
    attachments.router,
    prefix="/api/v1",
    dependencies=_auth_deps,
)

app.include_router(
    admin.router,
    prefix="/api/v1",
    dependencies=_auth_deps,
)

app.include_router(
    analytics.router,
    prefix="/api/v1/analytics",
    tags=["Analytics"],
    dependencies=_auth_deps,
)

app.include_router(
    document_templates.router,
    prefix="/api/v1",
    dependencies=_auth_deps,
)

# Platform-Admin: KEINE _auth_deps — eigener X-Platform-Admin-Key
app.include_router(
    platform.router,
    prefix="/api/v1",
)


def _safe_static_file(base: Path, rel_path: str) -> Optional[Path]:
    """Löst rel_path innerhalb von base auf und schützt vor Path-Traversal.

    Gibt den Pfad nur zurück, wenn er eine existierende Datei IST und garantiert
    innerhalb von `base` liegt (kein ../, keine Symlink-Flucht, kein absoluter Pfad).
    Sonst None.
    """
    if not rel_path:
        return None
    # Frühe Ablehnung offensichtlicher Traversal-Versuche
    if ".." in rel_path.split("/") or "\\" in rel_path or rel_path.startswith("/"):
        return None
    try:
        base_resolved = base.resolve()
        candidate = (base / rel_path).resolve(strict=True)
    except (FileNotFoundError, RuntimeError, OSError):
        return None
    # Containment-Check: candidate muss unterhalb von base liegen
    if base_resolved != candidate and base_resolved not in candidate.parents:
        return None
    if not candidate.is_file():
        return None
    return candidate


# === Kontakt-Formular (Marketing-Seite, apex, ohne Auth) =================
import re as _re
import html as _htmllib
from pydantic import BaseModel as _BaseModel
from app.core.email import email_service as _email_service

_CONTACT_EMAIL_RE = _re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class _ContactIn(_BaseModel):
    name: str = ""
    betrieb: str = ""
    email: str = ""
    message: str = ""
    website: str = ""  # Honeypot — von Bots ausgefüllt, von Menschen nicht


@app.post("/api/contact", tags=["System"])
@limiter.limit("5/hour")
async def contact_submit(request: Request, payload: _ContactIn):
    """Nimmt Anfragen vom Marketing-Kontaktformular entgegen und mailt sie an
    CONTACT_EMAIL. Kein Auth (apex). Spam-Schutz: Honeypot + Rate-Limit."""
    # Honeypot: Bots füllen das versteckte Feld → still "ok", nichts weiter tun.
    if payload.website.strip():
        return {"ok": True}

    name = payload.name.strip()[:120]
    email = payload.email.strip()[:160]
    betrieb = payload.betrieb.strip()[:160]
    message = payload.message.strip()[:2000]

    if not name or not _CONTACT_EMAIL_RE.match(email):
        return JSONResponse(
            status_code=422,
            content={"ok": False, "detail": "Bitte Namen und eine gültige E-Mail angeben."},
        )

    # Lead IMMER loggen — so geht keine Anfrage verloren, auch wenn SMTP fehlt.
    logger.warning("[contact] name=%r betrieb=%r email=%r message=%r", name, betrieb, email, message)

    def _esc(s: str) -> str:
        return _htmllib.escape(s, quote=False)

    recipient = os.environ.get("CONTACT_EMAIL", "info@novaerp.de")
    subject_name = _re.sub(r"[\r\n]+", " ", name)[:80]
    html_body = (
        "<h3>Neue Anfrage über novaerp.de</h3>"
        "<p><b>Name:</b> {{ name }}<br>"
        "<b>Betrieb:</b> {{ betrieb }}<br>"
        "<b>E-Mail:</b> {{ email }}</p>"
        "<p><b>Nachricht:</b><br>{{ message }}</p>"
    )
    try:
        _email_service.send_email(
            email_to=recipient,
            subject=f"Neue Anfrage von {subject_name}",
            template_str=html_body,
            template_data={
                "name": _esc(name),
                "betrieb": _esc(betrieb) or "—",
                "email": _esc(email),
                "message": _esc(message).replace("\n", "<br>") or "—",
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.error("[contact] E-Mail-Versand fehlgeschlagen: %s", e)

    return {"ok": True}


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str, request: Request):
    """Serve SPA/marketing index — apex zeigt Marketing-Seite, Subdomains die App."""
    if full_path.startswith(("api/", "docs", "redoc", "openapi.json", "health")):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    # admin.novaerp.de → Platform-Admin-UI
    if _is_admin_request(request) and admin_dist.exists():
        safe = _safe_static_file(admin_dist, full_path)
        if safe:
            return FileResponse(safe)
        if (admin_dist / "index.html").exists():
            return FileResponse(admin_dist / "index.html")

    # Apex (novaerp.de) → Marketing-Seite
    if _is_apex_request(request) and marketing_dist.exists():
        # Direkte Dateianforderung (z.B. /assets/foo.png) prüfen
        safe = _safe_static_file(marketing_dist, full_path)
        if safe:
            return FileResponse(safe)
        # Saubere URLs ohne .html mappen: /impressum → impressum.html
        safe_html = _safe_static_file(marketing_dist, f"{full_path}.html")
        if safe_html:
            return FileResponse(safe_html)
        # Sonst: Marketing-Index ausliefern
        if (marketing_dist / "index.html").exists():
            return FileResponse(marketing_dist / "index.html")

    # Subdomains → React-SPA
    if (frontend_dist / "index.html").exists():
        safe = _safe_static_file(frontend_dist, full_path)
        if safe:
            return FileResponse(safe)
        return FileResponse(frontend_dist / "index.html")

    return JSONResponse(status_code=404, content={"detail": "Not Found"})


# Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Globaler Exception Handler - never leaks internals to clients"""
    import logging
    logger = logging.getLogger(__name__)
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Ein interner Fehler ist aufgetreten.",
        }
    )
