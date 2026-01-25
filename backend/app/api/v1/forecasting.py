"""
API Endpoints für Forecasting und Produktionsplanung
"""
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID
import math
from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from app.api.deps import DBSession, Pagination, CurrentUser
from app.models.seed import Seed
from app.models.customer import Subscription
from app.models.order import Order, OrderItem, OrderStatus
from app.models.forecast import (
    Forecast, ForecastModelType, ForecastAccuracy,
    ProductionSuggestion, SuggestionStatus, WarningType
)
from app.models.capacity import Capacity, ResourceType
from app.schemas.forecast import (
    ForecastGenerateRequest, ForecastResponse, ForecastOverride,
    ForecastListResponse, ForecastAccuracyResponse, ForecastAccuracySummary,
    ProductionSuggestionResponse, ProductionSuggestionApprove,
    ProductionSuggestionListResponse, WeeklyForecastSummary
)

router = APIRouter()


# ============== Forecast Endpoints ==============

@router.get("/forecasts", response_model=ForecastListResponse)
async def list_forecasts(
    db: DBSession,
    pagination: Pagination,
    seed_id: UUID | None = None,
    von_datum: date | None = None,
    bis_datum: date | None = None
):
    """
    Forecasts abrufen.

    Filter:
    - **seed_id**: Forecasts für ein bestimmtes Produkt
    - **von_datum** / **bis_datum**: Prognosezeitraum
    """
    query = select(Forecast).options(
        joinedload(Forecast.seed),
        joinedload(Forecast.kunde)
    )

    if seed_id:
        query = query.where(Forecast.seed_id == seed_id)
    if von_datum:
        query = query.where(Forecast.datum >= von_datum)
    if bis_datum:
        query = query.where(Forecast.datum <= bis_datum)

    # Total Count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Paginated Results
    query = query.order_by(Forecast.datum.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    forecasts = db.execute(query).scalars().unique().all()

    items = []
    for fc in forecasts:
        response = ForecastResponse.model_validate(fc)
        response.seed_name = fc.seed.name if fc.seed else None
        response.kunde_name = fc.kunde.name if fc.kunde else None
        items.append(response)

    return ForecastListResponse(items=items, total=total)


@router.post("/forecasts/generate", response_model=list[ForecastResponse])
async def generate_forecasts(request: ForecastGenerateRequest, db: DBSession):
    """
    Forecasts generieren.

    Berechnet Absatzprognosen basierend auf:
    - Historischen Bestellungen
    - Aktiven Abonnements
    - Saisonalen Mustern

    Hinweis: Für komplexe Forecasts wird der externe Forecasting-Service
    verwendet. Diese Endpoint bietet eine Basis-Implementierung.
    """
    # Seeds laden
    if request.seed_ids:
        seeds = db.execute(
            select(Seed).where(Seed.id.in_(request.seed_ids), Seed.aktiv == True)
        ).scalars().all()
    else:
        seeds = db.execute(select(Seed).where(Seed.aktiv == True)).scalars().all()

    if not seeds:
        raise HTTPException(status_code=404, detail="Keine aktiven Produkte gefunden")

    today = date.today()
    forecasts = []

    for seed in seeds:
        for day_offset in range(request.horizont_tage):
            forecast_date = today + timedelta(days=day_offset)

            # Basis-Forecast aus historischen Daten
            base_demand = await _calculate_base_demand(db, seed.id, forecast_date)

            # Abonnement-Beiträge
            subscription_demand = await _calculate_subscription_demand(
                db, seed.id, forecast_date, request.kunde_id
            )

            total_demand = base_demand + subscription_demand

            # Konfidenzintervall (einfache Schätzung: ±20%)
            confidence_margin = total_demand * Decimal("0.2")

            forecast = Forecast(
                seed_id=seed.id,
                kunde_id=request.kunde_id,
                datum=forecast_date,
                horizont_tage=request.horizont_tage,
                prognostizierte_menge=total_demand,
                konfidenz_untergrenze=max(Decimal("0"), total_demand - confidence_margin),
                konfidenz_obergrenze=total_demand + confidence_margin,
                modell_typ=request.modell_typ
            )
            db.add(forecast)
            forecasts.append(forecast)

    db.commit()

    # Responses erstellen
    results = []
    for fc in forecasts:
        db.refresh(fc)
        response = ForecastResponse.model_validate(fc)
        response.seed_name = next(s.name for s in seeds if s.id == fc.seed_id)
        results.append(response)

    return results


@router.get("/forecasts/{forecast_id}", response_model=ForecastResponse)
async def get_forecast(forecast_id: UUID, db: DBSession):
    """Einzelnen Forecast abrufen."""
    forecast = db.execute(
        select(Forecast)
        .options(joinedload(Forecast.seed), joinedload(Forecast.kunde))
        .where(Forecast.id == forecast_id)
    ).scalar_one_or_none()

    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast nicht gefunden")

    response = ForecastResponse.model_validate(forecast)
    response.seed_name = forecast.seed.name if forecast.seed else None
    response.kunde_name = forecast.kunde.name if forecast.kunde else None
    return response


@router.patch("/forecasts/{forecast_id}/override", response_model=ForecastResponse)
async def override_forecast(
    forecast_id: UUID,
    override_data: ForecastOverride,
    db: DBSession,
    user: CurrentUser
):
    """
    Manueller Override für Forecast.

    Nur für Production Planner erlaubt.
    Speichert Begründung für Nachvollziehbarkeit.
    """
    forecast = db.execute(
        select(Forecast)
        .options(joinedload(Forecast.seed), joinedload(Forecast.kunde))
        .where(Forecast.id == forecast_id)
    ).scalar_one_or_none()

    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast nicht gefunden")

    forecast.override_menge = override_data.override_menge
    forecast.override_grund = override_data.override_grund
    forecast.override_user_id = UUID(user["id"])

    db.commit()
    db.refresh(forecast)

    response = ForecastResponse.model_validate(forecast)
    response.seed_name = forecast.seed.name if forecast.seed else None
    response.kunde_name = forecast.kunde.name if forecast.kunde else None
    return response


# ============== Forecast Accuracy ==============

@router.get("/forecasts/accuracy/summary", response_model=ForecastAccuracySummary)
async def get_forecast_accuracy_summary(
    db: DBSession,
    von_datum: date | None = None,
    bis_datum: date | None = None
):
    """
    Zusammenfassung der Forecast-Genauigkeit.

    Berechnet MAPE (Mean Absolute Percentage Error) über alle Forecasts.
    """
    if not von_datum:
        von_datum = date.today() - timedelta(days=30)
    if not bis_datum:
        bis_datum = date.today()

    accuracies = db.execute(
        select(ForecastAccuracy)
        .join(Forecast)
        .options(joinedload(ForecastAccuracy.forecast).joinedload(Forecast.seed))
        .where(Forecast.datum.between(von_datum, bis_datum))
    ).scalars().all()

    if not accuracies:
        return ForecastAccuracySummary(
            zeitraum_von=von_datum,
            zeitraum_bis=bis_datum,
            anzahl_forecasts=0,
            durchschnitt_mape=Decimal("0"),
            median_mape=Decimal("0"),
            beste_genauigkeit=Decimal("0"),
            schlechteste_genauigkeit=Decimal("0")
        )

    mapes = [a.mape for a in accuracies if a.mape is not None]
    sorted_mapes = sorted(mapes)

    # Nach Produkt gruppieren
    by_product = {}
    for acc in accuracies:
        if acc.mape and acc.forecast.seed:
            name = acc.forecast.seed.name
            if name not in by_product:
                by_product[name] = []
            by_product[name].append(acc.mape)

    nach_produkt = {
        name: sum(values) / len(values)
        for name, values in by_product.items()
    }

    return ForecastAccuracySummary(
        zeitraum_von=von_datum,
        zeitraum_bis=bis_datum,
        anzahl_forecasts=len(accuracies),
        durchschnitt_mape=sum(mapes) / len(mapes) if mapes else Decimal("0"),
        median_mape=sorted_mapes[len(sorted_mapes) // 2] if sorted_mapes else Decimal("0"),
        beste_genauigkeit=min(mapes) if mapes else Decimal("0"),
        schlechteste_genauigkeit=max(mapes) if mapes else Decimal("0"),
        nach_produkt=nach_produkt
    )


# ============== Production Suggestions ==============

@router.get("/production-suggestions", response_model=ProductionSuggestionListResponse)
async def list_production_suggestions(
    db: DBSession,
    pagination: Pagination,
    status_filter: SuggestionStatus | None = Query(None, alias="status"),
    seed_id: UUID | None = None
):
    """
    Produktionsvorschläge abrufen.

    Filter:
    - **status**: VORGESCHLAGEN, GENEHMIGT, ABGELEHNT, UMGESETZT
    - **seed_id**: Vorschläge für ein Produkt
    """
    query = select(ProductionSuggestion).options(
        joinedload(ProductionSuggestion.seed),
        joinedload(ProductionSuggestion.forecast)
    )

    if status_filter:
        query = query.where(ProductionSuggestion.status == status_filter)
    if seed_id:
        query = query.where(ProductionSuggestion.seed_id == seed_id)

    # Total Count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Warnungen zählen
    warning_count = db.execute(
        select(func.count())
        .where(
            ProductionSuggestion.warnungen != None,
            ProductionSuggestion.status == SuggestionStatus.VORGESCHLAGEN
        )
    ).scalar() or 0

    # Paginated Results
    query = query.order_by(ProductionSuggestion.aussaat_datum)
    query = query.offset(pagination.offset).limit(pagination.page_size)
    suggestions = db.execute(query).scalars().unique().all()

    items = []
    for sug in suggestions:
        response = ProductionSuggestionResponse.model_validate(sug)
        response.seed_name = sug.seed.name if sug.seed else None
        items.append(response)

    return ProductionSuggestionListResponse(
        items=items,
        total=total,
        warnungen_gesamt=warning_count
    )


@router.post("/production-suggestions/generate", response_model=list[ProductionSuggestionResponse])
async def generate_production_suggestions(
    db: DBSession,
    horizont_tage: int = Query(default=14, ge=1, le=30)
):
    """
    Produktionsvorschläge aus Forecasts generieren.

    Berechnet:
    - Benötigte Trays basierend auf Forecast
    - Aussaat-Datum (rückgerechnet von Erntedatum)
    - Warnungen bei Kapazitätsengpässen
    """
    today = date.today()
    end_date = today + timedelta(days=horizont_tage)

    # Aktuelle Forecasts laden
    forecasts = db.execute(
        select(Forecast)
        .options(joinedload(Forecast.seed))
        .where(
            Forecast.datum.between(today, end_date),
            Forecast.kunde_id == None  # Nur Gesamtprognosen
        )
    ).scalars().unique().all()

    if not forecasts:
        return []

    # Kapazitäten laden
    regal_capacity = db.execute(
        select(Capacity).where(Capacity.ressource_typ == ResourceType.REGAL)
    ).scalar_one_or_none()

    max_regal = regal_capacity.max_kapazitaet if regal_capacity else 100
    current_regal = regal_capacity.aktuell_belegt if regal_capacity else 0

    suggestions = []

    for forecast in forecasts:
        seed = forecast.seed
        if not seed:
            continue

        # Benötigte Menge
        benoetigte_menge = forecast.effektive_menge
        if benoetigte_menge <= 0:
            continue

        # Trays berechnen
        ertrag_pro_tray = float(seed.ertrag_gramm_pro_tray)
        verlust_faktor = 1 - float(seed.verlustquote_prozent) / 100
        effektiver_ertrag = ertrag_pro_tray * verlust_faktor

        trays = math.ceil(float(benoetigte_menge) / effektiver_ertrag)

        # Aussaat-Datum berechnen
        wachstumstage = seed.keimdauer_tage + seed.wachstumsdauer_tage
        aussaat_datum = forecast.datum - timedelta(days=wachstumstage)

        # Warnungen prüfen
        warnungen = []

        # Kapazitätswarnung
        if current_regal + trays > max_regal:
            warnungen.append({
                "typ": WarningType.KAPAZITAET.value,
                "nachricht": f"Kapazität überschritten: {current_regal + trays}/{max_regal} Regalplätze"
            })

        # Aussaat in Vergangenheit?
        if aussaat_datum < today:
            warnungen.append({
                "typ": WarningType.UNTERDECKUNG.value,
                "nachricht": f"Aussaat-Datum liegt in der Vergangenheit ({aussaat_datum})"
            })

        suggestion = ProductionSuggestion(
            forecast_id=forecast.id,
            seed_id=seed.id,
            empfohlene_trays=trays,
            aussaat_datum=max(aussaat_datum, today),
            erwartete_ernte_datum=forecast.datum,
            warnungen=warnungen if warnungen else None
        )
        db.add(suggestion)
        suggestions.append(suggestion)

        # Kapazität vormerken
        current_regal += trays

    db.commit()

    results = []
    for sug in suggestions:
        db.refresh(sug)
        response = ProductionSuggestionResponse.model_validate(sug)
        response.seed_name = sug.seed.name if sug.seed else None
        results.append(response)

    return results


@router.post("/production-suggestions/{suggestion_id}/approve", response_model=ProductionSuggestionResponse)
async def approve_production_suggestion(
    suggestion_id: UUID,
    approval: ProductionSuggestionApprove,
    db: DBSession,
    user: CurrentUser
):
    """
    Produktionsvorschlag genehmigen.

    Optional: Angepasste Tray-Anzahl übergeben.
    """
    from datetime import datetime

    suggestion = db.execute(
        select(ProductionSuggestion)
        .options(joinedload(ProductionSuggestion.seed))
        .where(ProductionSuggestion.id == suggestion_id)
    ).scalar_one_or_none()

    if not suggestion:
        raise HTTPException(status_code=404, detail="Vorschlag nicht gefunden")

    if suggestion.status != SuggestionStatus.VORGESCHLAGEN:
        raise HTTPException(
            status_code=400,
            detail=f"Vorschlag hat Status {suggestion.status.value}, kann nicht genehmigt werden"
        )

    if approval.angepasste_trays:
        suggestion.empfohlene_trays = approval.angepasste_trays

    suggestion.status = SuggestionStatus.GENEHMIGT
    suggestion.genehmigt_am = datetime.utcnow()
    suggestion.genehmigt_von = UUID(user["id"])

    db.commit()
    db.refresh(suggestion)

    response = ProductionSuggestionResponse.model_validate(suggestion)
    response.seed_name = suggestion.seed.name if suggestion.seed else None
    return response


@router.post("/production-suggestions/{suggestion_id}/reject")
async def reject_production_suggestion(suggestion_id: UUID, db: DBSession):
    """Produktionsvorschlag ablehnen."""
    suggestion = db.get(ProductionSuggestion, suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Vorschlag nicht gefunden")

    suggestion.status = SuggestionStatus.ABGELEHNT
    db.commit()

    return {"message": "Vorschlag abgelehnt"}


# ============== Weekly Summary ==============

@router.get("/weekly-summary", response_model=WeeklyForecastSummary)
async def get_weekly_forecast_summary(
    db: DBSession,
    kalenderwoche: int | None = None,
    jahr: int | None = None
):
    """
    Wöchentliche Forecast-Zusammenfassung.

    Ideal für Produktionsplanung auf Wochenbasis.
    """
    today = date.today()

    if not kalenderwoche or not jahr:
        kalenderwoche = today.isocalendar()[1]
        jahr = today.year

    # Wochenstart/-ende berechnen
    jan_first = date(jahr, 1, 1)
    week_start = jan_first + timedelta(weeks=kalenderwoche - 1, days=-jan_first.weekday())
    week_end = week_start + timedelta(days=6)

    # Forecasts der Woche
    forecasts = db.execute(
        select(Forecast)
        .options(joinedload(Forecast.seed))
        .where(Forecast.datum.between(week_start, week_end))
    ).scalars().unique().all()

    # Produktionsvorschläge der Woche
    suggestions = db.execute(
        select(ProductionSuggestion)
        .options(joinedload(ProductionSuggestion.seed))
        .where(ProductionSuggestion.aussaat_datum.between(week_start, week_end))
    ).scalars().unique().all()

    # Warnungen sammeln
    warnungen = []
    for sug in suggestions:
        if sug.warnungen:
            for w in sug.warnungen:
                w["produkt"] = sug.seed.name if sug.seed else "Unbekannt"
                warnungen.append(w)

    forecast_responses = []
    for fc in forecasts:
        response = ForecastResponse.model_validate(fc)
        response.seed_name = fc.seed.name if fc.seed else None
        forecast_responses.append(response)

    suggestion_responses = []
    for sug in suggestions:
        response = ProductionSuggestionResponse.model_validate(sug)
        response.seed_name = sug.seed.name if sug.seed else None
        suggestion_responses.append(response)

    return WeeklyForecastSummary(
        kalenderwoche=kalenderwoche,
        jahr=jahr,
        start_datum=week_start,
        end_datum=week_end,
        forecasts=forecast_responses,
        produktionsvorschlaege=suggestion_responses,
        warnungen=warnungen
    )


# ============== Helper Functions ==============

async def _calculate_base_demand(db, seed_id: UUID, forecast_date: date) -> Decimal:
    """
    Berechnet Basis-Nachfrage aus historischen Bestellungen.

    Analysiert gleiche Wochentage der letzten 8 Wochen.
    """
    weekday = forecast_date.weekday()

    # Historische Bestellungen für gleichen Wochentag
    eight_weeks_ago = forecast_date - timedelta(weeks=8)

    historical_orders = db.execute(
        select(func.sum(OrderItem.menge))
        .join(Order)
        .where(
            OrderItem.seed_id == seed_id,
            Order.liefer_datum >= eight_weeks_ago,
            Order.liefer_datum < forecast_date,
            func.extract('dow', Order.liefer_datum) == weekday,
            Order.status != OrderStatus.STORNIERT
        )
    ).scalar() or Decimal("0")

    # Anzahl Wochen mit Daten
    weeks_with_data = db.execute(
        select(func.count(func.distinct(Order.liefer_datum)))
        .join(OrderItem)
        .where(
            OrderItem.seed_id == seed_id,
            Order.liefer_datum >= eight_weeks_ago,
            Order.liefer_datum < forecast_date,
            func.extract('dow', Order.liefer_datum) == weekday
        )
    ).scalar() or 1

    # Durchschnitt berechnen
    return historical_orders / max(1, weeks_with_data)


async def _calculate_subscription_demand(
    db, seed_id: UUID, forecast_date: date, kunde_id: UUID | None
) -> Decimal:
    """
    Berechnet erwartete Nachfrage aus aktiven Abonnements.
    """
    weekday = forecast_date.weekday()

    query = select(func.sum(Subscription.menge)).where(
        Subscription.seed_id == seed_id,
        Subscription.aktiv == True,
        Subscription.gueltig_von <= forecast_date,
        (Subscription.gueltig_bis == None) | (Subscription.gueltig_bis >= forecast_date),
        Subscription.liefertage.contains([weekday])
    )

    if kunde_id:
        query = query.where(Subscription.kunde_id == kunde_id)

    return db.execute(query).scalar() or Decimal("0")
