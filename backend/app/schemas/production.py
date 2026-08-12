from typing import Literal, Optional
"""
Pydantic Schemas für Produktion
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, model_validator

from app.models.production import GrowBatchStatus


class GrowBatchBase(BaseModel):
    """Basis-Schema für Wachstumscharge"""
    tray_anzahl: int = Field(..., ge=1, description="Anzahl der Trays")
    aussaat_datum: date = Field(..., description="Datum der Aussaat")
    regal_position: Optional[str] = Field(None, max_length=50, description="Position im Regal")
    notizen: Optional[str] = Field(None, description="Zusätzliche Notizen")


class GrowBatchCreate(GrowBatchBase):
    """Schema zum Erstellen einer Wachstumscharge"""
    seed_batch_id: UUID = Field(..., description="ID der Saatgut-Charge")
    # Chargen-Abweichung (Tage): wird an der Saatgut-Charge persistiert und
    # verschiebt das Erntefenster (z.B. +1 bei langsamer Keimung)
    zusatz_tage: Optional[int] = Field(None, ge=-7, le=14, description="Erntefenster-Verschiebung der Saatgut-Charge in Tagen")


class GrowBatchUpdate(BaseModel):
    """Schema zum Aktualisieren einer Wachstumscharge"""
    status: Optional[GrowBatchStatus] = None
    regal_position: Optional[str] = None
    notizen: Optional[str] = None


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
    seed_name: Optional[str] = None


class GrowBatchListResponse(BaseModel):
    """Schema für Wachstumscharge-Liste"""
    items: list[GrowBatchResponse]
    total: int


# Harvest Schemas

class HarvestBase(BaseModel):
    """Basis-Schema für Ernte — Erfassung wahlweise in Gramm oder Stück"""
    ernte_datum: date = Field(..., description="Datum der Ernte")
    einheit: Literal["G", "STK"] = Field(default="G", description="Erfassungseinheit: Gramm oder Stück (ganze Schalen)")
    menge_gramm: Optional[Decimal] = Field(None, ge=0, description="Geerntete Menge in Gramm (bei einheit=G)")
    verlust_gramm: Decimal = Field(default=Decimal("0"), ge=0, description="Verlust in Gramm")
    menge_stueck: Optional[int] = Field(None, ge=0, description="Geerntete Menge in Stück (bei einheit=STK)")
    verlust_stueck: Optional[int] = Field(None, ge=0, description="Verlust in Stück")
    stueck_pro_kiste: Optional[int] = Field(None, ge=1, description="Kistenformat: Stück pro Anzuchtkiste (z.B. 15 oder 21)")
    qualitaet_note: Optional[int] = Field(None, ge=1, le=5, description="Qualitätsbewertung 1-5")

    @model_validator(mode="after")
    def _require_menge_for_einheit(self):
        if self.einheit == "STK":
            if not self.menge_stueck or self.menge_stueck <= 0:
                raise ValueError("Bei Erfassung in Stück muss menge_stueck > 0 sein")
            # STK-Ernten tragen keine Gramm-Werte: unconditional auf 0 setzen,
            # sonst würden mitgeschickte Gramm alle g-Aggregationen verschmutzen.
            # (Tenant-DBs führen menge_gramm zudem als NOT NULL — 0 statt NULL.)
            self.menge_gramm = Decimal("0")
            self.verlust_gramm = Decimal("0")
        else:
            if not self.menge_gramm or self.menge_gramm <= 0:
                raise ValueError("Bei Erfassung in Gramm muss menge_gramm > 0 sein")
        return self


class HarvestCreate(HarvestBase):
    """Schema zum Erstellen einer Ernte"""
    grow_batch_id: UUID = Field(..., description="ID der Wachstumscharge")
    # Wird als Harvest.quality_notes gespeichert
    notizen: Optional[str] = Field(None, description="Beobachtungen zur Ernte")


class HarvestResponse(HarvestBase):
    """Schema für Ernte-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    grow_batch_id: UUID
    created_at: datetime
    quality_notes: Optional[str] = None

    # Berechnete Felder
    verlustquote: Decimal



class HarvestListResponse(BaseModel):
    """Schema für Ernte-Liste"""
    items: list[HarvestResponse]
    total: int


class DashboardWoche(BaseModel):
    """Wochenfenster (Mo–So) der Dashboard-Zusammenfassung"""
    start: date
    ende: date


class DashboardSummary(BaseModel):
    """Schema für Dashboard-Zusammenfassung"""
    active_batches: int
    harvest_ready: int
    weekly_harvest_kg: Decimal
    weekly_harvest_stueck: int = 0
    # Vertrag des Dashboard-Frontends (deutsche Feldnamen)
    chargen_nach_status: dict[str, int]
    erntereife_chargen: int
    ernten_diese_woche_gramm: Decimal
    verluste_diese_woche_gramm: Decimal
    ernten_diese_woche_stueck: int = 0
    verluste_diese_woche_stueck: int = 0
    woche: DashboardWoche

