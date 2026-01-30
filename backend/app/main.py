"""
Minga-Greens ERP - FastAPI Backend
Hauptanwendung und Router-Konfiguration
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import engine, Base
from app.api.v1 import seeds, production, sales, forecasting, products, invoices, inventory, analytics, capacity

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup und Shutdown Events"""
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

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health Check
@app.get("/health", tags=["System"])
async def health_check():
    """
    Systemstatus prüfen.
    Wird von Docker für Health Checks verwendet.
    """
    return {"status": "healthy", "version": settings.app_version}


@app.get("/", tags=["System"])
async def root():
    """API Root - Zeigt Willkommensnachricht"""
    return {
        "message": "Willkommen bei Minga-Greens ERP",
        "version": settings.app_version,
        "docs": "/docs",
    }


# API Router einbinden
app.include_router(
    seeds.router,
    prefix="/api/v1/seeds",
    tags=["Saatgut"]
)

app.include_router(
    production.router,
    prefix="/api/v1/production",
    tags=["Produktion"]
)

app.include_router(
    sales.router,
    prefix="/api/v1/sales",
    tags=["Vertrieb"]
)

app.include_router(
    forecasting.router,
    prefix="/api/v1/forecasting",
    tags=["Forecasting"]
)

# ERP Module
app.include_router(
    products.router,
    prefix="/api/v1",
)

app.include_router(
    products.groups_router,
    prefix="/api/v1",
)

app.include_router(
    products.grow_plans_router,
    prefix="/api/v1",
)

app.include_router(
    products.price_lists_router,
    prefix="/api/v1",
)

app.include_router(
    invoices.router,
    prefix="/api/v1",
)

app.include_router(
    inventory.router,
    prefix="/api/v1",
)

app.include_router(
    capacity.router,
    prefix="/api/v1",
)

app.include_router(
    analytics.router,
    prefix="/api/v1/analytics",
    tags=["Analytics"]
)


# Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Globaler Exception Handler"""
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Ein interner Fehler ist aufgetreten.",
            "error": str(exc) if settings.debug else None
        }
    )
