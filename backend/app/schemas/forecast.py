"""
Pydantic Schemas für Forecasting
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

from app.models.forecast import ForecastModelType, SuggestionStatus


class ForecastBase(BaseModel):
    """Basis-Schema für Forecast"""
    datum: date = Field(..., description="Prognosedatum")
    horizont_tage: int = Field(..., ge=1, le=90, description="Prognosehorizont in Tagen")


class ForecastGenerateRequest(BaseModel):
    """Request zum Generieren von Forecasts"""
    seed_ids: list[UUID] | None = Field(None, description="Produkt-IDs (None = alle)")
    kunde_id: UUID | None = Field(None, description="Kunden-ID für kundenspezifischen Forecast")
    horizont_tage: int = Field(default=14, ge=1, le=90, description="Prognosehorizont")
    modell_typ: ForecastModelType = Field(default=ForecastModelType.PROPHET, description="Modelltyp")


class ForecastOverride(BaseModel):
    """Schema für manuellen Override"""
    override_menge: Decimal = Field(..., ge=0, description="Überschriebene Menge")
    override_grund: str = Field(..., min_length=1, max_length=500, description="Begründung")


class ForecastResponse(ForecastBase):
    """Schema für Forecast-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seed_id: UUID
    kunde_id: UUID | None
    prognostizierte_menge: Decimal
    konfidenz_untergrenze: Decimal | None
    konfidenz_obergrenze: Decimal | None
    modell_typ: ForecastModelType
    override_menge: Decimal | None
    override_grund: str | None
    override_user_id: UUID | None
    created_at: datetime

    # Berechnete Felder
    effektive_menge: Decimal

    # Expandierte Felder
    seed_name: str | None = None
    kunde_name: str | None = None


class ForecastListResponse(BaseModel):
    """Schema für Forecast-Liste"""
    items: list[ForecastResponse]
    total: int


class ForecastAccuracyResponse(BaseModel):
    """Schema für Forecast-Genauigkeit"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    forecast_id: UUID
    ist_menge: Decimal
    abweichung_absolut: Decimal | None
    abweichung_prozent: Decimal | None
    mape: Decimal | None
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


# Production Suggestion Schemas

class ProductionSuggestionResponse(BaseModel):
    """Schema für Produktionsvorschlag"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    forecast_id: UUID
    seed_id: UUID
    empfohlene_trays: int
    aussaat_datum: date
    erwartete_ernte_datum: date
    status: SuggestionStatus
    warnungen: list[dict] | None
    created_at: datetime
    genehmigt_am: datetime | None
    genehmigt_von: UUID | None

    # Expandierte Felder
    seed_name: str | None = None


class ProductionSuggestionApprove(BaseModel):
    """Schema zum Genehmigen eines Vorschlags"""
    angepasste_trays: int | None = Field(None, ge=1, description="Angepasste Tray-Anzahl")


class ProductionSuggestionListResponse(BaseModel):
    """Schema für Produktionsvorschlags-Liste"""
    items: list[ProductionSuggestionResponse]
    total: int
    warnungen_gesamt: int


class WeeklyForecastSummary(BaseModel):
    """Wöchentliche Forecast-Zusammenfassung"""
    kalenderwoche: int
    jahr: int
    start_datum: date
    end_datum: date
    forecasts: list[ForecastResponse]
    produktionsvorschlaege: list[ProductionSuggestionResponse]
    warnungen: list[dict]
