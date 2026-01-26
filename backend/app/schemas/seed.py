from typing import Optional
"""
Pydantic Schemas für Saatgut
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class SeedBase(BaseModel):
    """Basis-Schema für Saatgut"""
    name: str = Field(..., min_length=1, max_length=100, description="Name der Sorte")
    sorte: Optional[str] = Field(None, max_length=100, description="Sortenbezeichnung")
    lieferant: Optional[str] = Field(None, max_length=200, description="Lieferant")
    keimdauer_tage: int = Field(..., ge=1, le=30, description="Keimdauer in Tagen")
    wachstumsdauer_tage: int = Field(..., ge=1, le=60, description="Wachstumsdauer in Tagen")
    erntefenster_min_tage: int = Field(..., ge=1, description="Frühester Erntezeitpunkt")
    erntefenster_optimal_tage: int = Field(..., ge=1, description="Optimaler Erntezeitpunkt")
    erntefenster_max_tage: int = Field(..., ge=1, description="Spätester Erntezeitpunkt")
    ertrag_gramm_pro_tray: Decimal = Field(..., gt=0, description="Erwarteter Ertrag pro Tray in Gramm")
    verlustquote_prozent: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Erwartete Verlustquote")


class SeedCreate(SeedBase):
    """Schema zum Erstellen einer Saatgut-Sorte"""
    pass


class SeedUpdate(BaseModel):
    """Schema zum Aktualisieren einer Saatgut-Sorte"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    sorte: Optional[str] = None
    lieferant: Optional[str] = None
    keimdauer_tage: Optional[int] = Field(None, ge=1, le=30)
    wachstumsdauer_tage: Optional[int] = Field(None, ge=1, le=60)
    erntefenster_min_tage: Optional[int] = Field(None, ge=1)
    erntefenster_optimal_tage: Optional[int] = Field(None, ge=1)
    erntefenster_max_tage: Optional[int] = Field(None, ge=1)
    ertrag_gramm_pro_tray: Optional[Decimal] = Field(None, gt=0)
    verlustquote_prozent: Optional[Decimal] = Field(None, ge=0, le=100)
    aktiv: Optional[bool] = None


class SeedResponse(SeedBase):
    """Schema für Saatgut-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    aktiv: bool
    created_at: datetime
    updated_at: datetime

    # Berechnete Felder
    gesamte_wachstumsdauer: int


class SeedListResponse(BaseModel):
    """Schema für Saatgut-Liste"""
    items: list[SeedResponse]
    total: int
    page: int
    page_size: int


# Seed Batch Schemas

class SeedBatchBase(BaseModel):
    """Basis-Schema für Saatgut-Charge"""
    charge_nummer: str = Field(..., min_length=1, max_length=50, description="Eindeutige Chargennummer")
    menge_gramm: Decimal = Field(..., gt=0, description="Gelieferte Menge in Gramm")
    mhd: Optional[date] = Field(None, description="Mindesthaltbarkeitsdatum")
    lieferdatum: Optional[date] = Field(None, description="Lieferdatum")


class SeedBatchCreate(SeedBatchBase):
    """Schema zum Erstellen einer Saatgut-Charge"""
    seed_id: UUID = Field(..., description="ID der Saatgut-Sorte")


class SeedBatchResponse(SeedBatchBase):
    """Schema für Saatgut-Charge-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seed_id: UUID
    verbleibend_gramm: Decimal
    created_at: datetime
