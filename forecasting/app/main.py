"""
Minga-Greens Forecasting Service
Separater Microservice für KI-gestützte Absatzprognosen
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.forecast_api import router as forecast_router
from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup und Shutdown Events"""
    # Prophet Models können hier vorgeladen werden
    yield


app = FastAPI(
    title="Minga-Greens Forecasting Service",
    version="1.0.0",
    description="""
    ## Forecasting Service

    Separater Microservice für Absatzprognosen.

    ### Modelle
    - **Prophet**: Zeitreihen mit Saisonalität und Feiertagen
    - **ARIMA**: Klassische Zeitreihenanalyse
    - **Ensemble**: Kombinierte Vorhersagen

    ### Endpoints
    - `/forecast/sales`: Absatzprognose
    - `/forecast/production`: Produktionsplanung
    - `/forecast/capacity`: Kapazitätsplanung
    """,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health Check für Docker"""
    return {"status": "healthy", "service": "forecasting"}


app.include_router(forecast_router, prefix="/forecast", tags=["Forecasting"])
