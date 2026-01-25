"""
Pydantic Schemas für Produktion
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

from app.models.production import GrowBatchStatus


class GrowBatchBase(BaseModel):
    """Basis-Schema für Wachstumscharge"""
    tray_anzahl: int = Field(..., ge=1, description="Anzahl der Trays")
    aussaat_datum: date = Field(..., description="Datum der Aussaat")
    regal_position: str | None = Field(None, max_length=50, description="Position im Regal")
    notizen: str | None = Field(None, description="Zusätzliche Notizen")


class GrowBatchCreate(GrowBatchBase):
    """Schema zum Erstellen einer Wachstumscharge"""
    seed_batch_id: UUID = Field(..., description="ID der Saatgut-Charge")


class GrowBatchUpdate(BaseModel):
    """Schema zum Aktualisieren einer Wachstumscharge"""
    status: GrowBatchStatus | None = None
    regal_position: str | None = None
    notizen: str | None = None


class GrowBatchResponse(GrowBatchBase):
    """Schema für Wachstumscharge-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seed_batch_id: UUID
    erwartete_ernte_min: date
    erwartete_ernte_optimal: date
    erwartete_ernte_max: date
    status: GrowBatchStatus
    created_at: datetime
    updated_at: datetime

    # Berechnete Felder
    tage_seit_aussaat: int
    ist_erntereif: bool

    # Seed-Info (optional expandiert)
    seed_name: str | None = None


class GrowBatchListResponse(BaseModel):
    """Schema für Wachstumscharge-Liste"""
    items: list[GrowBatchResponse]
    total: int


# Harvest Schemas

class HarvestBase(BaseModel):
    """Basis-Schema für Ernte"""
    ernte_datum: date = Field(..., description="Datum der Ernte")
    menge_gramm: Decimal = Field(..., gt=0, description="Geerntete Menge in Gramm")
    verlust_gramm: Decimal = Field(default=Decimal("0"), ge=0, description="Verlust in Gramm")
    qualitaet_note: int | None = Field(None, ge=1, le=5, description="Qualitätsbewertung 1-5")


class HarvestCreate(HarvestBase):
    """Schema zum Erstellen einer Ernte"""
    grow_batch_id: UUID = Field(..., description="ID der Wachstumscharge")


class HarvestResponse(HarvestBase):
    """Schema für Ernte-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    grow_batch_id: UUID
    created_at: datetime

    # Berechnete Felder
    verlustquote: Decimal


class HarvestListResponse(BaseModel):
    """Schema für Ernte-Liste"""
    items: list[HarvestResponse]
    total: int
