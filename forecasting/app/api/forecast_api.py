"""
Forecasting API Endpoints
"""
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.pipelines.sales_forecast import SalesForecastPipeline
from app.pipelines.production_planning import ProductionPlanningPipeline

router = APIRouter()


# ============== Request/Response Models ==============

class ForecastRequest(BaseModel):
    """Request für Absatzprognose"""
    seed_id: UUID = Field(..., description="Produkt-ID")
    horizon_days: int = Field(default=14, ge=1, le=90, description="Prognosehorizont in Tagen")
    customer_id: Optional[UUID] = Field(None, description="Optional: Kundenspezifische Prognose")
    use_prophet: bool = Field(default=True, description="Prophet-Model verwenden")


class ForecastDataPoint(BaseModel):
    """Einzelner Forecast-Datenpunkt"""
    date: str
    predicted_quantity: float
    subscription_quantity: float
    total_quantity: float
    lower_bound: float
    upper_bound: float


class ForecastResponse(BaseModel):
    """Antwort mit Forecast-Daten"""
    seed_id: UUID
    horizon_days: int
    model_used: str
    forecasts: list[ForecastDataPoint]


class ProductionPlanItem(BaseModel):
    """Einzelner Produktionsplan-Eintrag"""
    harvest_date: str
    sow_date: str
    seed_id: str
    seed_name: str
    forecast_quantity: float
    required_trays: int
    warnings: list[dict]
    confidence: dict


class ProductionPlanResponse(BaseModel):
    """Antwort mit Produktionsplan"""
    seed_id: UUID
    horizon_days: int
    plan: list[ProductionPlanItem]
    total_trays: int
    warning_count: int


class MultiProductRequest(BaseModel):
    """Request für Multi-Produkt-Forecast"""
    seed_ids: list[UUID] = Field(..., description="Liste von Produkt-IDs")
    horizon_days: int = Field(default=14, ge=1, le=90)


# ============== Endpoints ==============

@router.post("/sales", response_model=ForecastResponse)
async def create_sales_forecast(request: ForecastRequest):
    """
    Absatzprognose erstellen.

    Verwendet Prophet oder SimpleForecaster basierend auf verfügbaren Daten.
    Berücksichtigt historische Verkäufe und aktive Abonnements.
    """
    try:
        pipeline = SalesForecastPipeline()
        forecasts = pipeline.run_forecast(
            seed_id=request.seed_id,
            horizon_days=request.horizon_days,
            customer_id=request.customer_id,
            use_prophet=request.use_prophet
        )

        return ForecastResponse(
            seed_id=request.seed_id,
            horizon_days=request.horizon_days,
            model_used="prophet" if request.use_prophet else "simple",
            forecasts=[ForecastDataPoint(**f) for f in forecasts]
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast fehlgeschlagen: {str(e)}")


@router.post("/production", response_model=ProductionPlanResponse)
async def create_production_plan(request: ForecastRequest):
    """
    Produktionsplan erstellen.

    Übersetzt Absatzprognose in konkrete Produktionsvorschläge:
    - Benötigte Trays
    - Aussaat-Termine
    - Kapazitätswarnungen
    """
    try:
        pipeline = ProductionPlanningPipeline()
        plan = pipeline.create_production_plan(
            seed_id=request.seed_id,
            horizon_days=request.horizon_days
        )

        total_trays = sum(p["required_trays"] for p in plan)
        warning_count = sum(len(p["warnings"]) for p in plan)

        return ProductionPlanResponse(
            seed_id=request.seed_id,
            horizon_days=request.horizon_days,
            plan=[ProductionPlanItem(**p) for p in plan],
            total_trays=total_trays,
            warning_count=warning_count
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Planung fehlgeschlagen: {str(e)}")


@router.post("/sales/multi")
async def create_multi_product_forecast(request: MultiProductRequest):
    """
    Absatzprognosen für mehrere Produkte.

    Nützlich für wöchentliche Gesamtplanung.
    """
    pipeline = SalesForecastPipeline()
    results = {}

    for seed_id in request.seed_ids:
        try:
            forecasts = pipeline.run_forecast(
                seed_id=seed_id,
                horizon_days=request.horizon_days
            )
            results[str(seed_id)] = {
                "status": "success",
                "forecasts": forecasts
            }
        except Exception as e:
            results[str(seed_id)] = {
                "status": "error",
                "error": str(e)
            }

    return {
        "horizon_days": request.horizon_days,
        "products": results
    }


@router.get("/weekly-summary")
async def get_weekly_summary(
    week: Optional[int] = Query(None, description="Kalenderwoche (1-52)"),
    year: Optional[int] = Query(None, description="Jahr")
):
    """
    Wöchentliche Zusammenfassung aller Forecasts.

    Aggregiert alle aktiven Produkte für eine Woche.
    """
    from datetime import timedelta

    today = date.today()

    if not week:
        week = today.isocalendar()[1]
    if not year:
        year = today.year

    # Wochenstart berechnen
    jan_first = date(year, 1, 1)
    week_start = jan_first + timedelta(weeks=week - 1, days=-jan_first.weekday())
    week_end = week_start + timedelta(days=6)

    # Alle aktiven Seeds laden
    pipeline = ProductionPlanningPipeline()

    # SQL für aktive Seeds
    from sqlalchemy import text
    with pipeline.engine.connect() as conn:
        result = conn.execute(text("SELECT id, name FROM seeds WHERE aktiv = true"))
        seeds = [(row.id, row.name) for row in result]

    # Forecasts aggregieren
    daily_totals = {}
    production_plans = []

    for seed_id, seed_name in seeds:
        try:
            plan = pipeline.create_production_plan(
                seed_id=seed_id,
                horizon_days=(week_end - today).days + 1 if week_start <= today else 7
            )

            for item in plan:
                if week_start.isoformat() <= item["harvest_date"] <= week_end.isoformat():
                    production_plans.append(item)

                    if item["harvest_date"] not in daily_totals:
                        daily_totals[item["harvest_date"]] = 0
                    daily_totals[item["harvest_date"]] += item["forecast_quantity"]

        except Exception:
            continue

    # Warnungen sammeln
    all_warnings = [
        {"seed": p["seed_name"], **w}
        for p in production_plans
        for w in p["warnings"]
    ]

    return {
        "week": week,
        "year": year,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "daily_totals": daily_totals,
        "total_quantity": sum(daily_totals.values()),
        "total_trays": sum(p["required_trays"] for p in production_plans),
        "warnings": all_warnings,
        "warning_count": len(all_warnings)
    }
