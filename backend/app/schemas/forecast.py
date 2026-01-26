from typing import Optional
"""
Pydantic Schemas für Forecasting
Erweitert um vollständige Manual-Input-Funktionalität.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

from app.models.forecast import ForecastModelType, SuggestionStatus, AdjustmentType


# ==================== MANUAL ADJUSTMENT SCHEMAS ====================

class ManualAdjustmentCreate(BaseModel):
    """Schema zum Erstellen einer manuellen Forecast-Anpassung"""
    adjustment_type: AdjustmentType = Field(..., description="Art der Anpassung")
    adjustment_value: Decimal = Field(..., description="Wert der Anpassung")
    reason: str = Field(..., min_length=10, max_length=1000, description="Begründung (Pflicht)")
    valid_from: Optional[date] = Field(None, description="Gültig ab")
    valid_until: Optional[date] = Field(None, description="Gültig bis")


class ManualAdjustmentRevert(BaseModel):
    """Schema zum Rückgängig-Machen einer Anpassung"""
    reason: str = Field(..., min_length=5, max_length=500, description="Begründung für Rücknahme")


class ManualAdjustmentResponse(BaseModel):
    """Schema für Manual-Adjustment-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    forecast_id: UUID
    adjustment_type: AdjustmentType
    adjustment_value: Decimal
    reason: str
    valid_from: Optional[date]
    valid_until: Optional[date]
    is_active: bool
    reverted_at: Optional[datetime]
    reverted_by: Optional[UUID]
    revert_reason: Optional[str]
    user_id: Optional[UUID]
    user_name: Optional[str]
    created_at: datetime


# ==================== FORECAST SCHEMAS ====================

class ForecastBase(BaseModel):
    """Basis-Schema für Forecast"""
    datum: date = Field(..., description="Prognosedatum")
    horizont_tage: int = Field(..., ge=1, le=90, description="Prognosehorizont in Tagen")


class ForecastGenerateRequest(BaseModel):
    """Request zum Generieren von Forecasts"""
    seed_ids: Optional[list[UUID]] = Field(None, description="Produkt-IDs (None = alle)")
    product_ids: Optional[list[UUID]] = Field(None, description="Produkt-IDs")
    kunde_id: Optional[UUID] = Field(None, description="Kunden-ID für kundenspezifischen Forecast")
    horizont_tage: int = Field(default=14, ge=1, le=90, description="Prognosehorizont")
    modell_typ: ForecastModelType = Field(default=ForecastModelType.PROPHET, description="Modelltyp")
    include_subscriptions: bool = Field(default=True, description="Abonnements einbeziehen")
    include_seasonality: bool = Field(default=True, description="Saisonalität einbeziehen")
    include_weekday_patterns: bool = Field(default=True, description="Wochentagsmuster einbeziehen")


class ForecastOverride(BaseModel):
    """Legacy Schema für einfachen Override - für Rückwärtskompatibilität"""
    override_menge: Decimal = Field(..., ge=0, description="Überschriebene Menge")
    override_grund: str = Field(..., min_length=1, max_length=500, description="Begründung")


class ForecastBreakdown(BaseModel):
    """Aufschlüsselung eines Forecasts"""
    automatic_forecast: float
    confidence_lower: Optional[float]
    confidence_upper: Optional[float]
    model_type: str
    manual_adjustments: list[dict]
    effective_forecast: float
    has_manual_adjustment: bool


class ForecastResponse(ForecastBase):
    """Schema für Forecast-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seed_id: UUID
    product_id: Optional[UUID]
    customer_id: Optional[UUID]

    # Automatische Prognose
    prognostizierte_menge: Decimal
    konfidenz_untergrenze: Optional[Decimal]
    konfidenz_obergrenze: Optional[Decimal]
    modell_typ: ForecastModelType

    # Effektive Werte
    effektive_menge: Decimal
    hat_manuelle_anpassung: bool

    # Datenquellen
    basiert_auf_historisch: bool
    basiert_auf_abonnements: bool
    basiert_auf_saisonalitaet: bool
    basiert_auf_wochentag: bool
    historische_datenpunkte: Optional[int]

    # Legacy Override (für Kompatibilität)
    override_menge: Optional[Decimal]
    override_grund: Optional[str]
    override_user_id: Optional[UUID]
    override_timestamp: Optional[datetime]

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Expandierte Felder
    seed_name: Optional[str] = None
    product_name: Optional[str] = None
    customer_name: Optional[str] = None

    # Manuelle Anpassungen
    manual_adjustments: list[ManualAdjustmentResponse] = []


class ForecastDetailResponse(ForecastResponse):
    """Erweiterte Forecast-Antwort mit Breakdown"""
    breakdown: Optional[ForecastBreakdown] = None
    suggestions: list["ProductionSuggestionResponse"] = []
    accuracy: Optional["ForecastAccuracyResponse"] = None


class ForecastListResponse(BaseModel):
    """Schema für Forecast-Liste"""
    items: list[ForecastResponse]
    total: int


# ==================== FORECAST ACCURACY SCHEMAS ====================

class ForecastAccuracyResponse(BaseModel):
    """Schema für Forecast-Genauigkeit"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    forecast_id: UUID
    ist_menge: Decimal
    abweichung_absolut: Optional[Decimal]
    abweichung_prozent: Optional[Decimal]
    mape: Optional[Decimal]

    # Zusätzliche Felder für Vergleich
    hatte_manuelle_anpassung: bool
    urspruengliche_prognose: Optional[Decimal]
    abweichung_ohne_anpassung: Optional[Decimal]

    ausgewertet_am: datetime


class ForecastAccuracySummary(BaseModel):
    """Zusammenfassung der Forecast-Genauigkeit"""
    zeitraum_von: date
    zeitraum_bis: date
    anzahl_forecasts: int
    durchschnitt_mape: Decimal
    median_mape: Decimal
    beste_genauigkeit: Decimal
    schlechteste_genauigkeit: Decimal
    nach_produkt: dict[str, Decimal] = {}

    # Vergleich mit/ohne manuelle Anpassungen
    durchschnitt_mape_mit_anpassung: Optional[Decimal] = None
    durchschnitt_mape_ohne_anpassung: Optional[Decimal] = None
    anzahl_mit_anpassung: int = 0
    anzahl_ohne_anpassung: int = 0


class ForecastAccuracyComparison(BaseModel):
    """Vergleich Accuracy mit vs. ohne manuelle Anpassungen"""
    forecast_id: UUID
    datum: date
    product_name: Optional[str]

    # Mit manueller Anpassung
    effektive_prognose: Decimal
    ist_menge: Decimal
    abweichung_mit_anpassung: Optional[Decimal]

    # Ohne manuelle Anpassung (nur automatisch)
    automatische_prognose: Decimal
    abweichung_ohne_anpassung: Optional[Decimal]

    # War manuelle Anpassung hilfreich?
    anpassung_hilfreich: Optional[bool]


# ==================== PRODUCTION SUGGESTION SCHEMAS ====================

class ProductionSuggestionResponse(BaseModel):
    """Schema für Produktionsvorschlag"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    forecast_id: UUID
    seed_id: UUID
    product_id: Optional[UUID]
    empfohlene_trays: int
    aussaat_datum: date
    erwartete_ernte_datum: date

    # Mengen
    erwartete_menge_gramm: Optional[Decimal]
    benoetigte_menge_gramm: Optional[Decimal]

    status: SuggestionStatus
    warnungen: Optional[list[dict]]
    ablehnungsgrund: Optional[str]

    created_at: datetime
    genehmigt_am: Optional[datetime]
    genehmigt_von: Optional[UUID]
    genehmigt_von_name: Optional[str]

    # Expandierte Felder
    seed_name: Optional[str] = None
    product_name: Optional[str] = None


class ProductionSuggestionApprove(BaseModel):
    """Schema zum Genehmigen eines Vorschlags"""
    angepasste_trays: Optional[int] = Field(None, ge=1, description="Angepasste Tray-Anzahl")


class ProductionSuggestionReject(BaseModel):
    """Schema zum Ablehnen eines Vorschlags"""
    grund: str = Field(..., min_length=5, max_length=500, description="Ablehnungsgrund")


class ProductionSuggestionListResponse(BaseModel):
    """Schema für Produktionsvorschlags-Liste"""
    items: list[ProductionSuggestionResponse]
    total: int
    warnungen_gesamt: int


# ==================== SUMMARY SCHEMAS ====================

class WeeklyForecastSummary(BaseModel):
    """Wöchentliche Forecast-Zusammenfassung"""
    kalenderwoche: int
    jahr: int
    start_datum: date
    end_datum: date
    forecasts: list[ForecastResponse]
    produktionsvorschlaege: list[ProductionSuggestionResponse]
    warnungen: list[dict]

    # Aggregate
    gesamt_prognostiziert: Decimal
    gesamt_mit_anpassungen: Decimal
    anzahl_anpassungen: int


class ForecastDashboard(BaseModel):
    """Dashboard-Daten für Forecasting"""
    # Aktuelle Forecasts
    forecasts_heute: int
    forecasts_diese_woche: int
    forecasts_mit_anpassung: int

    # Produktionsvorschläge
    offene_vorschlaege: int
    genehmigte_vorschlaege: int
    warnungen: int

    # Accuracy
    durchschnitt_mape_7_tage: Optional[Decimal]
    durchschnitt_mape_30_tage: Optional[Decimal]

    # Trend
    forecast_trend: list[dict]  # [{datum, prognostiziert, ist}]


# Forward reference updates
ForecastDetailResponse.model_rebuild()
