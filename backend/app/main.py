"""
Minga-Greens ERP - FastAPI Backend
Hauptanwendung und Router-Konfiguration
"""
import logging
import time
import uuid
import base64
import binascii
import secrets
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
from app.api.v1 import seeds, production, sales, forecasting, products, invoices, inventory, analytics, capacity
from app.api.deps import get_current_user

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

    # Startup: Tabellen erstellen (für Entwicklung)
    # In Produktion: Alembic Migrations verwenden
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown: Cleanup falls nötig


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    ## Minga-Greens ERP API

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


def _is_basic_auth_valid(request: Request) -> bool:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        return False

    token = auth_header[6:].strip()
    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False

    if ":" not in decoded:
        return False

    username, password = decoded.split(":", 1)
    allowed_pairs = [
        (settings.basic_auth_user_1, settings.basic_auth_password_1),
        (settings.basic_auth_user_2, settings.basic_auth_password_2),
    ]

    for allowed_user, allowed_password in allowed_pairs:
        if not allowed_user or not allowed_password:
            continue
        if secrets.compare_digest(username, allowed_user) and secrets.compare_digest(password, allowed_password):
            return True

    return False


@app.middleware("http")
async def basic_auth_middleware(request: Request, call_next):
    if not settings.basic_auth_enabled:
        return await call_next(request)

    if request.url.path.startswith("/health"):
        return await call_next(request)

    if not _is_basic_auth_valid(request):
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
            headers={"WWW-Authenticate": 'Basic realm="Minga Greens Demo"'},
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
async def root():
    """API Root - Zeigt Willkommensnachricht"""
    if (frontend_dist / "index.html").exists():
        return FileResponse(frontend_dist / "index.html")

    return {
        "message": "Willkommen bei Minga-Greens ERP",
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
    analytics.router,
    prefix="/api/v1/analytics",
    tags=["Analytics"],
    dependencies=_auth_deps,
)


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """Serve SPA index for non-API routes in single-container deployment."""
    if full_path.startswith(("api/", "docs", "redoc", "openapi.json", "health")):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    if (frontend_dist / "index.html").exists():
        requested = frontend_dist / full_path
        if requested.exists() and requested.is_file():
            return FileResponse(requested)
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
