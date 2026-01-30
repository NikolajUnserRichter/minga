from typing import Optional
"""
API Endpoints für Forecasting und Produktionsplanung
Erweitert mit Manual Adjustment Capability
"""
from datetime import date, timedelta, datetime
from decimal import Decimal
from uuid import UUID
import math
from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from app.api.deps import DBSession, Pagination, CurrentUser
from app.models.seed import Seed
from app.models.customer import Subscription
from app.models.order import Order, OrderLine, OrderStatus
from app.models.forecast import (
    Forecast, ForecastModelType, ForecastAccuracy,
    ProductionSuggestion, SuggestionStatus, WarningType,
    ForecastManualAdjustment, AdjustmentType
)
from app.models.capacity import Capacity, ResourceType
from app.models.production import GrowBatch, GrowBatchStatus
from app.models.seed import SeedBatch
from app.schemas.forecast import (
    ForecastGenerateRequest, ForecastResponse, ForecastOverride,
    ForecastListResponse, ForecastAccuracyResponse, ForecastAccuracySummary,
    ProductionSuggestionResponse, ProductionSuggestionApprove, ProductionSuggestionReject,
    ProductionSuggestionListResponse, WeeklyForecastSummary,
    ManualAdjustmentCreate, ManualAdjustmentRevert, ManualAdjustmentResponse,
    ForecastBreakdown, ForecastDetailResponse, ForecastDashboard
)
from app.tasks.forecast_tasks import apply_manual_adjustment, recalculate_production_suggestions

router = APIRouter()


# ============== Forecast Endpoints ==============

@router.get("/forecasts", response_model=ForecastListResponse)
async def list_forecasts(
    db: DBSession,
    pagination: Pagination,
    seed_id: Optional[UUID] = None,
    von_datum: Optional[date] = None,
    bis_datum: Optional[date] = None,
    has_adjustments: Optional[bool] = None
):
    """
    Forecasts abrufen.

    Filter:
    - **seed_id**: Forecasts für ein bestimmtes Produkt
    - **von_datum** / **bis_datum**: Prognosezeitraum
    - **has_adjustments**: Nur Forecasts mit manuellen Anpassungen
    """
    query = select(Forecast).options(
        joinedload(Forecast.seed),
        joinedload(Forecast.customer),
        joinedload(Forecast.manual_adjustments)
    )

    if seed_id:
        query = query.where(Forecast.seed_id == seed_id)
    if von_datum:
        query = query.where(Forecast.datum >= von_datum)
    if bis_datum:
        query = query.where(Forecast.datum <= bis_datum)
    if has_adjustments is not None:
        if has_adjustments:
            query = query.where(Forecast.hat_manuelle_anpassung == True)
        else:
            query = query.where(Forecast.hat_manuelle_anpassung == False)

    # Total Count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Paginated Results
    query = query.order_by(Forecast.datum.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    forecasts = db.execute(query).scalars().unique().all()

    items = []
    for fc in forecasts:
        response = _build_forecast_response(fc)
        items.append(response)

    return ForecastListResponse(items=items, total=total)


def _build_forecast_response(fc: Forecast) -> ForecastResponse:
    """Baut ForecastResponse aus Forecast-Objekt."""
    return ForecastResponse(
        id=fc.id,
        seed_id=fc.seed_id,
        seed_name=fc.seed.name if fc.seed else None,
        kunde_id=fc.customer_id,
        kunde_name=fc.customer.name if fc.customer else None,
        datum=fc.datum,
        horizont_tage=fc.horizont_tage,
        prognostizierte_menge=fc.prognostizierte_menge,
        effektive_menge=fc.effektive_menge,
        konfidenz_untergrenze=fc.konfidenz_untergrenze,
        konfidenz_obergrenze=fc.konfidenz_obergrenze,
        modell_typ=fc.modell_typ,
        hat_manuelle_anpassung=fc.hat_manuelle_anpassung,
        override_menge=fc.override_menge,
        override_grund=fc.override_grund,
        basiert_auf_historisch=fc.basiert_auf_historisch,
        basiert_auf_abonnements=fc.basiert_auf_abonnements,
        basiert_auf_saisonalitaet=fc.basiert_auf_saisonalitaet,
        created_at=fc.created_at
    )


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
    # Forecast Engine initialisieren
    from app.services.forecast_engine import ForecastEngine
    engine = ForecastEngine(db)
    
    forecasts = []

    for seed in seeds:
         # Vorhersage generieren (Training + Prediction)
         predictions = engine.train_and_predict(str(seed.id), horizon_days=request.horizont_tage)
         
         # Map preds by date for easy lookup
         pred_map = {d: val for d, val in predictions}
         
         for day_offset in range(request.horizont_tage):
            forecast_date = today + timedelta(days=day_offset)
            
            # Basis-Nachfrage (aus Engine)
            base_demand = pred_map.get(forecast_date, Decimal("0"))
            
            # Abonnement-Beiträge zusätzlich?
            # ForecastEngine trainiert auf historischen Verkäufen.
            # Abonnements sind "Zukunft".
            # Normalerweise: Forecast = Baseline (Sales History) + Additional Known Demand (Subs)
            # ABER: Wenn Subs auch in Vergangenheit waren, dann sind sie in History drin.
            # Wenn wir "Zusatznachfrage" addieren, verdoppeln wir evtl.
            # Der einfache Ansatz war: Base (History) + Subs.
            # Lassen wir es dabei: ForecastEngine ist "History Trend". Subs sind "Fixed Future".
            
            subscription_demand = await _calculate_subscription_demand(
                db, seed.id, forecast_date, request.kunde_id
            )
            
            total_demand = base_demand + subscription_demand
            
            # Konfidenzintervall
            confidence_margin = total_demand * Decimal("0.2")

            forecast = Forecast(
                seed_id=seed.id,
                kunde_id=request.kunde_id,
                datum=forecast_date,
                horizont_tage=request.horizont_tage,
                prognostizierte_menge=total_demand,
                effektive_menge=total_demand,
                konfidenz_untergrenze=max(Decimal("0"), total_demand - confidence_margin),
                konfidenz_obergrenze=total_demand + confidence_margin,
                modell_typ=ForecastModelType.ENSEMBLE, # New internal type
                basiert_auf_historisch=base_demand > 0,
                basiert_auf_abonnements=subscription_demand > 0,
                basiert_auf_saisonalitaet=True
            )
            db.add(forecast)
            forecasts.append(forecast)

    db.commit()

    # Responses erstellen
    results = []
    for fc in forecasts:
        db.refresh(fc)
        response = _build_forecast_response(fc)
        response.seed_name = next(s.name for s in seeds if s.id == fc.seed_id)
        results.append(response)

    return results


@router.get("/forecasts/{forecast_id}", response_model=ForecastDetailResponse)
async def get_forecast(forecast_id: UUID, db: DBSession):
    """
    Einzelnen Forecast mit Details abrufen.

    Inkludiert:
    - Automatische Prognose
    - Alle manuellen Anpassungen
    - Effektive Menge
    - Breakdown der Berechnung
    """
    forecast = db.execute(
        select(Forecast)
        .options(
            joinedload(Forecast.seed),
            joinedload(Forecast.customer),
            joinedload(Forecast.manual_adjustments)
        )
        .where(Forecast.id == forecast_id)
    ).scalar_one_or_none()

    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast nicht gefunden")

    # Breakdown berechnen
    breakdown = forecast.get_forecast_breakdown()

    # Manuelle Anpassungen sammeln
    adjustments = [
        ManualAdjustmentResponse(
            id=adj.id,
            forecast_id=adj.forecast_id,
            adjustment_type=adj.adjustment_type,
            adjustment_value=adj.adjustment_value,
            reason=adj.reason,
            valid_from=adj.valid_from,
            valid_until=adj.valid_until,
            is_active=adj.is_active,
            created_at=adj.created_at,
            created_by=adj.created_by,
            reverted_at=adj.reverted_at,
            reverted_by=adj.reverted_by,
            revert_reason=adj.revert_reason
        )
        for adj in forecast.manual_adjustments
    ]

    return ForecastDetailResponse(
        id=forecast.id,
        seed_id=forecast.seed_id,
        seed_name=forecast.seed.name if forecast.seed else None,
        kunde_id=forecast.customer_id,
        kunde_name=forecast.customer.name if forecast.customer else None,
        datum=forecast.datum,
        horizont_tage=forecast.horizont_tage,
        prognostizierte_menge=forecast.prognostizierte_menge,
        effektive_menge=forecast.effektive_menge,
        konfidenz_untergrenze=forecast.konfidenz_untergrenze,
        konfidenz_obergrenze=forecast.konfidenz_obergrenze,
        modell_typ=forecast.modell_typ,
        hat_manuelle_anpassung=forecast.hat_manuelle_anpassung,
        override_menge=forecast.override_menge,
        override_grund=forecast.override_grund,
        basiert_auf_historisch=forecast.basiert_auf_historisch,
        basiert_auf_abonnements=forecast.basiert_auf_abonnements,
        basiert_auf_saisonalitaet=forecast.basiert_auf_saisonalitaet,
        created_at=forecast.created_at,
        breakdown=ForecastBreakdown(**breakdown),
        manual_adjustments=adjustments
    )


@router.patch("/forecasts/{forecast_id}/override", response_model=ForecastResponse)
async def override_forecast(
    forecast_id: UUID,
    override_data: ForecastOverride,
    db: DBSession,
    user: CurrentUser
):
    """
    Legacy: Manueller Override für Forecast.

    Nutze stattdessen /forecasts/{forecast_id}/adjustments für
    reversible, nachvollziehbare Anpassungen.
    """
    forecast = db.execute(
        select(Forecast)
        .options(joinedload(Forecast.seed), joinedload(Forecast.customer))
        .where(Forecast.id == forecast_id)
    ).scalar_one_or_none()

    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast nicht gefunden")

    forecast.override_menge = override_data.override_menge
    forecast.override_grund = override_data.override_grund
    forecast.override_user_id = UUID(user["id"])
    forecast.effektive_menge = override_data.override_menge
    forecast.hat_manuelle_anpassung = True

    db.commit()
    db.refresh(forecast)

    return _build_forecast_response(forecast)


# ============== Manual Adjustment Endpoints ==============

@router.post("/forecasts/{forecast_id}/adjustments", response_model=ManualAdjustmentResponse, status_code=status.HTTP_201_CREATED)
async def add_manual_adjustment(
    forecast_id: UUID,
    adjustment_data: ManualAdjustmentCreate,
    db: DBSession,
    user: CurrentUser
):
    """
    Manuelle Anpassung zum Forecast hinzufügen.

    Anpassungstypen:
    - **ABSOLUTE**: Setzt die Menge auf einen festen Wert
    - **PERCENTAGE_INCREASE**: Erhöht um X%
    - **PERCENTAGE_DECREASE**: Reduziert um X%
    - **ADDITION**: Addiert festen Wert
    - **SUBTRACTION**: Subtrahiert festen Wert

    Begründung ist Pflicht und muss mindestens 10 Zeichen haben.
    """
    forecast = db.get(Forecast, forecast_id)
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast nicht gefunden")

    # Validierung: Begründung erforderlich
    if not adjustment_data.reason or len(adjustment_data.reason.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Begründung muss mindestens 10 Zeichen haben"
        )

    # Gültigkeitszeitraum validieren
    if adjustment_data.valid_from and adjustment_data.valid_until:
        if adjustment_data.valid_from > adjustment_data.valid_until:
            raise HTTPException(
                status_code=400,
                detail="valid_from muss vor valid_until liegen"
            )

    adjustment = ForecastManualAdjustment(
        forecast_id=forecast_id,
        adjustment_type=adjustment_data.adjustment_type,
        adjustment_value=adjustment_data.adjustment_value,
        reason=adjustment_data.reason.strip(),
        valid_from=adjustment_data.valid_from,
        valid_until=adjustment_data.valid_until,
        created_by=UUID(user["id"]) if user else None
    )
    db.add(adjustment)

    # Forecast aktualisieren
    forecast.apply_manual_adjustments()

    db.commit()
    db.refresh(adjustment)

    # Produktionsvorschläge im Hintergrund neu berechnen
    recalculate_production_suggestions.delay(str(forecast_id))

    return ManualAdjustmentResponse(
        id=adjustment.id,
        forecast_id=adjustment.forecast_id,
        adjustment_type=adjustment.adjustment_type,
        adjustment_value=adjustment.adjustment_value,
        reason=adjustment.reason,
        valid_from=adjustment.valid_from,
        valid_until=adjustment.valid_until,
        is_active=adjustment.is_active,
        created_at=adjustment.created_at,
        created_by=adjustment.created_by,
        reverted_at=None,
        reverted_by=None,
        revert_reason=None
    )


@router.get("/forecasts/{forecast_id}/adjustments", response_model=list[ManualAdjustmentResponse])
async def list_manual_adjustments(
    forecast_id: UUID,
    db: DBSession,
    include_reverted: bool = False
):
    """
    Alle manuellen Anpassungen eines Forecasts abrufen.

    - **include_reverted**: Auch rückgängig gemachte Anpassungen anzeigen
    """
    forecast = db.get(Forecast, forecast_id)
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast nicht gefunden")

    query = select(ForecastManualAdjustment).where(
        ForecastManualAdjustment.forecast_id == forecast_id
    )

    if not include_reverted:
        query = query.where(ForecastManualAdjustment.is_active == True)

    query = query.order_by(ForecastManualAdjustment.created_at.desc())
    adjustments = db.execute(query).scalars().all()

    return [
        ManualAdjustmentResponse(
            id=adj.id,
            forecast_id=adj.forecast_id,
            adjustment_type=adj.adjustment_type,
            adjustment_value=adj.adjustment_value,
            reason=adj.reason,
            valid_from=adj.valid_from,
            valid_until=adj.valid_until,
            is_active=adj.is_active,
            created_at=adj.created_at,
            created_by=adj.created_by,
            reverted_at=adj.reverted_at,
            reverted_by=adj.reverted_by,
            revert_reason=adj.revert_reason
        )
        for adj in adjustments
    ]


@router.post("/forecasts/{forecast_id}/adjustments/{adjustment_id}/revert", response_model=ManualAdjustmentResponse)
async def revert_manual_adjustment(
    forecast_id: UUID,
    adjustment_id: UUID,
    revert_data: ManualAdjustmentRevert,
    db: DBSession,
    user: CurrentUser
):
    """
    Manuelle Anpassung rückgängig machen.

    Die Anpassung wird nicht gelöscht, sondern als "reverted" markiert
    für vollständige Nachvollziehbarkeit.
    """
    forecast = db.get(Forecast, forecast_id)
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast nicht gefunden")

    adjustment = db.execute(
        select(ForecastManualAdjustment).where(
            ForecastManualAdjustment.id == adjustment_id,
            ForecastManualAdjustment.forecast_id == forecast_id
        )
    ).scalar_one_or_none()

    if not adjustment:
        raise HTTPException(status_code=404, detail="Anpassung nicht gefunden")

    if not adjustment.is_active:
        raise HTTPException(
            status_code=400,
            detail="Anpassung wurde bereits rückgängig gemacht"
        )

    # Anpassung als reverted markieren
    adjustment.is_active = False
    adjustment.reverted_at = datetime.utcnow()
    adjustment.reverted_by = UUID(user["id"]) if user else None
    adjustment.revert_reason = revert_data.reason

    # Forecast neu berechnen
    forecast.apply_manual_adjustments()

    db.commit()
    db.refresh(adjustment)

    # Produktionsvorschläge im Hintergrund neu berechnen
    recalculate_production_suggestions.delay(str(forecast_id))

    return ManualAdjustmentResponse(
        id=adjustment.id,
        forecast_id=adjustment.forecast_id,
        adjustment_type=adjustment.adjustment_type,
        adjustment_value=adjustment.adjustment_value,
        reason=adjustment.reason,
        valid_from=adjustment.valid_from,
        valid_until=adjustment.valid_until,
        is_active=adjustment.is_active,
        created_at=adjustment.created_at,
        created_by=adjustment.created_by,
        reverted_at=adjustment.reverted_at,
        reverted_by=adjustment.reverted_by,
        revert_reason=adjustment.revert_reason
    )


# ============== Forecast Dashboard ==============

@router.get("/dashboard", response_model=ForecastDashboard)
async def get_forecast_dashboard(
    db: DBSession,
    tage: int = Query(default=7, ge=1, le=30)
):
    """
    Forecast-Dashboard mit Übersicht.

    Zeigt:
    - Forecasts mit manuellen Anpassungen
    - Aktuelle Produktionsvorschläge
    - Warnungen
    - Genauigkeits-Statistik
    """
    today = date.today()
    end_date = today + timedelta(days=tage)

    # Forecasts der nächsten Tage
    forecasts = db.execute(
        select(Forecast)
        .options(joinedload(Forecast.seed))
        .where(Forecast.datum.between(today, end_date))
        .order_by(Forecast.datum)
    ).scalars().unique().all()

    # Mit Anpassungen
    adjusted_forecasts = [f for f in forecasts if f.hat_manuelle_anpassung]

    # Offene Produktionsvorschläge
    pending_suggestions = db.execute(
        select(ProductionSuggestion)
        .options(joinedload(ProductionSuggestion.seed))
        .where(ProductionSuggestion.status == SuggestionStatus.VORGESCHLAGEN)
        .order_by(ProductionSuggestion.aussaat_datum)
    ).scalars().unique().all()

    # Warnungen sammeln
    warnings = []
    for sug in pending_suggestions:
        if sug.warnungen:
            for w in sug.warnungen:
                warnings.append({
                    "typ": w.get("typ", "UNBEKANNT"),
                    "nachricht": w.get("nachricht", ""),
                    "produkt": sug.seed.name if sug.seed else "Unbekannt",
                    "datum": str(sug.aussaat_datum)
                })

    # Genauigkeits-Statistik (letzte 30 Tage)
    thirty_days_ago = today - timedelta(days=30)
    accuracy_data = db.execute(
        select(func.avg(ForecastAccuracy.mape))
        .join(Forecast)
        .where(Forecast.datum >= thirty_days_ago)
    ).scalar()

    avg_mape = float(accuracy_data) if accuracy_data else 0

    return ForecastDashboard(
        zeitraum_von=today,
        zeitraum_bis=end_date,
        anzahl_forecasts=len(forecasts),
        anzahl_mit_anpassungen=len(adjusted_forecasts),
        offene_vorschlaege=len(pending_suggestions),
        warnungen=warnings,
        durchschnitt_mape=Decimal(str(avg_mape)),
        forecasts=[_build_forecast_response(f) for f in forecasts[:10]],  # Top 10
        vorschlaege=[
            ProductionSuggestionResponse(
                id=s.id,
                forecast_id=s.forecast_id,
                seed_id=s.seed_id,
                seed_name=s.seed.name if s.seed else None,
                empfohlene_trays=s.empfohlene_trays,
                aussaat_datum=s.aussaat_datum,
                erwartete_ernte_datum=s.erwartete_ernte_datum,
                status=s.status,
                warnungen=s.warnungen,
                benoetigte_menge_gramm=s.benoetigte_menge_gramm,
                erwartete_menge_gramm=s.erwartete_menge_gramm
            )
            for s in pending_suggestions[:10]  # Top 10
        ]
    )


# ============== Forecast Accuracy ==============

@router.get("/forecasts/accuracy/summary", response_model=ForecastAccuracySummary)
async def get_forecast_accuracy_summary(
    db: DBSession,
    von_datum: Optional[date] = None,
    bis_datum: Optional[date] = None
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
    status_filter: Optional[SuggestionStatus] = Query(None, alias="status"),
    seed_id: Optional[UUID] = None
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
        response = ProductionSuggestionResponse(
            id=sug.id,
            forecast_id=sug.forecast_id,
            seed_id=sug.seed_id,
            seed_name=sug.seed.name if sug.seed else None,
            empfohlene_trays=sug.empfohlene_trays,
            aussaat_datum=sug.aussaat_datum,
            erwartete_ernte_datum=sug.erwartete_ernte_datum,
            status=sug.status,
            warnungen=sug.warnungen,
            benoetigte_menge_gramm=sug.benoetigte_menge_gramm,
            erwartete_menge_gramm=sug.erwartete_menge_gramm
        )
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
    - Benötigte Trays basierend auf Forecast (nutzt effektive_menge)
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

        # Nutze effektive Menge (inkl. manueller Anpassungen)
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

        # Berechne erwartete Menge
        erwartete_menge = Decimal(str(trays * effektiver_ertrag))

        suggestion = ProductionSuggestion(
            forecast_id=forecast.id,
            seed_id=seed.id,
            empfohlene_trays=trays,
            aussaat_datum=max(aussaat_datum, today),
            erwartete_ernte_datum=forecast.datum,
            warnungen=warnungen if warnungen else None,
            benoetigte_menge_gramm=benoetigte_menge,
            erwartete_menge_gramm=erwartete_menge
        )
        db.add(suggestion)
        suggestions.append(suggestion)

        # Kapazität vormerken
        current_regal += trays

    db.commit()

    results = []
    for sug in suggestions:
        db.refresh(sug)
        response = ProductionSuggestionResponse(
            id=sug.id,
            forecast_id=sug.forecast_id,
            seed_id=sug.seed_id,
            seed_name=sug.seed.name if sug.seed else None,
            empfohlene_trays=sug.empfohlene_trays,
            aussaat_datum=sug.aussaat_datum,
            erwartete_ernte_datum=sug.erwartete_ernte_datum,
            status=sug.status,
            warnungen=sug.warnungen,
            benoetigte_menge_gramm=sug.benoetigte_menge_gramm,
            erwartete_menge_gramm=sug.erwartete_menge_gramm
        )
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

    # Charge suchen (FIFO)
    seed_batch = db.execute(
        select(SeedBatch)
        .where(SeedBatch.seed_id == suggestion.seed_id, SeedBatch.verbleibend_gramm > 0)
        .order_by(SeedBatch.created_at)
    ).scalars().first()

    # Fallback: Wenn keine Charge, suche irgendeine (auch leere) oder erstelle Dummy?
    # Wir nehmen "Neueste" wenn keine mit Bestand da ist, sonst Warnung
    if not seed_batch:
         seed_batch = db.execute(
            select(SeedBatch)
            .where(SeedBatch.seed_id == suggestion.seed_id)
            .order_by(SeedBatch.created_at.desc())
        ).scalars().first()
    
    # Wenn immer noch keine Charge -> Dummy erstellen? 
    # Besser: Fehler werfen, da Produktion ohne Charge im System nicht sauber ist.
    if not seed_batch:
         # Optional: Dummy erstellen
         raise HTTPException(status_code=400, detail="Keine Saatgut-Charge für dieses Produkt gefunden. Bitte erst Warenannahme buchen.")

    # GrowBatch erstellen
    grow_batch = GrowBatch(
        seed_batch_id=seed_batch.id,
        tray_anzahl=suggestion.empfohlene_trays,
        aussaat_datum=suggestion.aussaat_datum,
        erwartete_ernte_min=suggestion.erwartete_ernte_datum - timedelta(days=2), # Einfache Heuristik
        erwartete_ernte_optimal=suggestion.erwartete_ernte_datum,
        erwartete_ernte_max=suggestion.erwartete_ernte_datum + timedelta(days=2),
        status=GrowBatchStatus.KEIMUNG,
        notizen=f"Automatisch erstellt aus Produktionsvorschlag {suggestion.id}"
    )
    db.add(grow_batch)
    db.flush() # ID generieren

    suggestion.status = SuggestionStatus.GENEHMIGT
    suggestion.genehmigt_am = datetime.utcnow()
    suggestion.genehmigt_von = UUID(user["id"])

    db.commit()
    db.refresh(suggestion)
    db.refresh(grow_batch)

    return ProductionSuggestionResponse(
        id=suggestion.id,
        forecast_id=suggestion.forecast_id,
        seed_id=suggestion.seed_id,
        seed_name=suggestion.seed.name if suggestion.seed else None,
        empfohlene_trays=suggestion.empfohlene_trays,
        aussaat_datum=suggestion.aussaat_datum,
        erwartete_ernte_datum=suggestion.erwartete_ernte_datum,
        status=suggestion.status,
        warnungen=suggestion.warnungen,
        benoetigte_menge_gramm=suggestion.benoetigte_menge_gramm,
        erwartete_menge_gramm=suggestion.erwartete_menge_gramm,
        generated_batch_id=grow_batch.id
    )


@router.post("/production-suggestions/{suggestion_id}/reject", response_model=ProductionSuggestionResponse)
async def reject_production_suggestion(
    suggestion_id: UUID,
    rejection: ProductionSuggestionReject,
    db: DBSession,
    user: CurrentUser
):
    """Produktionsvorschlag ablehnen mit Begründung."""
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
            detail=f"Vorschlag hat Status {suggestion.status.value}, kann nicht abgelehnt werden"
        )

    suggestion.status = SuggestionStatus.ABGELEHNT
    suggestion.abgelehnt_am = datetime.utcnow()
    suggestion.abgelehnt_von = UUID(user["id"])
    suggestion.ablehnungsgrund = rejection.reason

    db.commit()
    db.refresh(suggestion)

    return ProductionSuggestionResponse(
        id=suggestion.id,
        forecast_id=suggestion.forecast_id,
        seed_id=suggestion.seed_id,
        seed_name=suggestion.seed.name if suggestion.seed else None,
        empfohlene_trays=suggestion.empfohlene_trays,
        aussaat_datum=suggestion.aussaat_datum,
        erwartete_ernte_datum=suggestion.erwartete_ernte_datum,
        status=suggestion.status,
        warnungen=suggestion.warnungen,
        benoetigte_menge_gramm=suggestion.benoetigte_menge_gramm,
        erwartete_menge_gramm=suggestion.erwartete_menge_gramm
    )


# ============== Weekly Summary ==============

@router.get("/weekly-summary", response_model=WeeklyForecastSummary)
async def get_weekly_forecast_summary(
    db: DBSession,
    kalenderwoche: Optional[int] = None,
    jahr: Optional[int] = None
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

    forecast_responses = [_build_forecast_response(fc) for fc in forecasts]

    suggestion_responses = [
        ProductionSuggestionResponse(
            id=sug.id,
            forecast_id=sug.forecast_id,
            seed_id=sug.seed_id,
            seed_name=sug.seed.name if sug.seed else None,
            empfohlene_trays=sug.empfohlene_trays,
            aussaat_datum=sug.aussaat_datum,
            erwartete_ernte_datum=sug.erwartete_ernte_datum,
            status=sug.status,
            warnungen=sug.warnungen,
            benoetigte_menge_gramm=sug.benoetigte_menge_gramm,
            erwartete_menge_gramm=sug.erwartete_menge_gramm
        )
        for sug in suggestions
    ]

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
        select(func.sum(OrderLine.menge))
        .join(Order)
        .where(
            OrderLine.seed_id == seed_id,
            Order.liefer_datum >= eight_weeks_ago,
            Order.liefer_datum < forecast_date,
            func.extract('dow', Order.liefer_datum) == weekday,
            Order.status != OrderStatus.STORNIERT
        )
    ).scalar() or Decimal("0")

    # Anzahl Wochen mit Daten
    weeks_with_data = db.execute(
        select(func.count(func.distinct(Order.liefer_datum)))
        .join(OrderLine)
        .where(
            OrderLine.seed_id == seed_id,
            Order.liefer_datum >= eight_weeks_ago,
            Order.liefer_datum < forecast_date,
            func.extract('dow', Order.liefer_datum) == weekday
        )
    ).scalar() or 1

    # Durchschnitt berechnen
    return historical_orders / max(1, weeks_with_data)


async def _calculate_subscription_demand(
    db, seed_id: UUID, forecast_date: date, kunde_id: Optional[UUID]
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
