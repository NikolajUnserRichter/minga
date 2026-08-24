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
    lieferant: Optional[str] = Field(None, max_length=200, description="Lieferant (Legacy free-text)")
    cooling_days: Optional[int] = Field(None, ge=0, description="Tage in Kühlung nach Ernte")
    cooling_shelf_life_days: Optional[int] = Field(None, ge=0, description="Haltbarkeit in Kühlung (Tage)")
    process_type: str = Field(default="STANDARD", description="Prozessvariante: STANDARD | PLATTE | PLATTE_STEINE")
    saatgut_pro_einheit_gramm: Optional[Decimal] = Field(None, ge=0, description="Saatgut-Dichte pro Anzucht-Einheit (Kiste) in g")
    keimdauer_tage: int = Field(..., ge=1, le=30, description="Keimdauer in Tagen")
    wachstumsdauer_tage: int = Field(..., ge=1, le=60, description="Wachstumsdauer in Tagen")
    erntefenster_min_tage: int = Field(..., ge=1, description="Frühester Erntezeitpunkt")
    erntefenster_optimal_tage: int = Field(..., ge=1, description="Optimaler Erntezeitpunkt")
    erntefenster_max_tage: int = Field(..., ge=1, description="Spätester Erntezeitpunkt")
    ertrag_gramm_pro_tray: Decimal = Field(..., gt=0, description="Erwarteter Ertrag pro Tray in Gramm")
    verlustquote_prozent: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Erwartete Verlustquote")
    substrat: Optional[str] = Field(None, max_length=100, description="Substrattyp für die Aussaat (z.B. Hanfmatte, Erde)")
    winter_extra_tage: int = Field(default=0, ge=0, le=14, description="Legacy-Pauschale Winter (nur ohne Winter-Satz)")
    # Eigenständiger Winter-Satz: leer = Winter wie Sommer
    winter_keimdauer_tage: Optional[int] = Field(None, ge=1, le=30, description="Keimdauer im Winter")
    winter_wachstumsdauer_tage: Optional[int] = Field(None, ge=1, le=60, description="Wachstumsdauer im Winter")
    winter_erntefenster_min_tage: Optional[int] = Field(None, ge=1, description="Frühester Erntezeitpunkt im Winter")
    winter_erntefenster_optimal_tage: Optional[int] = Field(None, ge=1, description="Optimaler Erntezeitpunkt im Winter")
    winter_erntefenster_max_tage: Optional[int] = Field(None, ge=1, description="Spätester Erntezeitpunkt im Winter")


class SeedMixComponentInput(BaseModel):
    """Eine Komponente im Rezept einer Mischsorte"""
    seed_id: UUID = Field(..., description="Ausgangssorte")
    gramm_pro_tray: Decimal = Field(..., gt=0, description="Saatgutmenge je Kiste in Gramm")


class SeedMixComponentResponse(SeedMixComponentInput):
    """Rezeptzeile inkl. Sortenname für die Anzeige"""
    model_config = ConfigDict(from_attributes=True)

    seed_name: Optional[str] = None


class SeedCreate(SeedBase):
    """Schema zum Erstellen einer Saatgut-Sorte"""
    # Mischsorte: das Rezept ersetzt den Wareneingang — gemischt wird bei der
    # Aussaat aus dem Bestand der Ausgangssorten.
    is_mix: bool = Field(default=False, description="Mischsorte (z.B. Brotzeitmix)")
    mix_components: list[SeedMixComponentInput] = Field(default_factory=list)


class SeedUpdate(BaseModel):
    """Schema zum Aktualisieren einer Saatgut-Sorte"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    sorte: Optional[str] = None
    lieferant: Optional[str] = None
    cooling_days: Optional[int] = None
    cooling_shelf_life_days: Optional[int] = None
    process_type: Optional[str] = None
    saatgut_pro_einheit_gramm: Optional[Decimal] = None
    keimdauer_tage: Optional[int] = Field(None, ge=1, le=30)
    wachstumsdauer_tage: Optional[int] = Field(None, ge=1, le=60)
    erntefenster_min_tage: Optional[int] = Field(None, ge=1)
    erntefenster_optimal_tage: Optional[int] = Field(None, ge=1)
    erntefenster_max_tage: Optional[int] = Field(None, ge=1)
    ertrag_gramm_pro_tray: Optional[Decimal] = Field(None, gt=0)
    verlustquote_prozent: Optional[Decimal] = Field(None, ge=0, le=100)
    substrat: Optional[str] = Field(None, max_length=100)
    winter_extra_tage: Optional[int] = Field(None, ge=0, le=14)
    winter_keimdauer_tage: Optional[int] = Field(None, ge=1, le=30)
    winter_wachstumsdauer_tage: Optional[int] = Field(None, ge=1, le=60)
    winter_erntefenster_min_tage: Optional[int] = Field(None, ge=1)
    winter_erntefenster_optimal_tage: Optional[int] = Field(None, ge=1)
    winter_erntefenster_max_tage: Optional[int] = Field(None, ge=1)
    aktiv: Optional[bool] = None
    is_mix: Optional[bool] = None
    #: None = Rezept unverändert lassen, [] = Rezept leeren
    mix_components: Optional[list[SeedMixComponentInput]] = None


class SeedResponse(SeedBase):
    """Schema für Saatgut-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    aktiv: bool
    created_at: datetime
    updated_at: datetime

    # Berechnete Felder
    gesamte_wachstumsdauer: int

    # Mischsorte + Rezept
    is_mix: bool = False
    mix_components: list[SeedMixComponentResponse] = Field(default_factory=list)


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
    in_production_at: Optional[date] = Field(None, description="Wann in Produktion genommen")
    lieferschein_nr: Optional[str] = Field(None, max_length=50, description="Lieferschein-Nummer")
    bio_zertifiziert: bool = Field(default=False, description="BIO-zertifiziert (Kontrollstelle)")
    kontrollstelle: Optional[str] = Field(None, max_length=100, description="Kontrollstelle (z.B. DE-ÖKO-006)")
    zusatz_tage: int = Field(default=0, ge=-7, le=14, description="Erntefenster-Verschiebung dieser Charge in Tagen (Legacy-Pauschale)")
    # Chargenbedingte Wachstumsparameter — Stammdaten der Charge, nicht des Aussaatzyklus
    keimdauer_tage: Optional[int] = Field(None, ge=1, le=30, description="Keimdauer dieser Charge")
    wachstumsdauer_tage: Optional[int] = Field(None, ge=1, le=60, description="Wachstumsdauer dieser Charge")
    erntefenster_min_tage: Optional[int] = Field(None, ge=1, description="Frühester Erntezeitpunkt dieser Charge")
    erntefenster_optimal_tage: Optional[int] = Field(None, ge=1, description="Optimaler Erntezeitpunkt dieser Charge")
    erntefenster_max_tage: Optional[int] = Field(None, ge=1, description="Spätester Erntezeitpunkt dieser Charge")


class SeedBatchCreate(SeedBatchBase):
    """Schema zum Erstellen einer Saatgut-Charge"""
    seed_id: UUID = Field(..., description="ID der Saatgut-Sorte")


class SeedBatchUpdate(BaseModel):
    """Schema zum Aktualisieren einer Saatgut-Charge"""
    charge_nummer: Optional[str] = Field(None, min_length=1, max_length=50)
    menge_gramm: Optional[Decimal] = Field(None, gt=0)
    mhd: Optional[date] = None
    lieferdatum: Optional[date] = None
    in_production_at: Optional[date] = None
    lieferschein_nr: Optional[str] = Field(None, max_length=50)
    bio_zertifiziert: Optional[bool] = None
    kontrollstelle: Optional[str] = Field(None, max_length=100)
    zusatz_tage: Optional[int] = Field(None, ge=-7, le=14)
    keimdauer_tage: Optional[int] = Field(None, ge=1, le=30)
    wachstumsdauer_tage: Optional[int] = Field(None, ge=1, le=60)
    erntefenster_min_tage: Optional[int] = Field(None, ge=1)
    erntefenster_optimal_tage: Optional[int] = Field(None, ge=1)
    erntefenster_max_tage: Optional[int] = Field(None, ge=1)


class SeedBatchResponse(SeedBatchBase):
    """Schema für Saatgut-Charge-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seed_id: UUID
    verbleibend_gramm: Decimal
    created_at: datetime


class SeedBatchComponentResponse(BaseModel):
    """Ausgangscharge einer Mischcharge (Rückverfolgbarkeit)"""
    model_config = ConfigDict(from_attributes=True)

    component_seed_id: UUID
    seed_name: Optional[str] = None
    charge_nummer: str
    menge_gramm: Decimal


# Seed-Supplier Link (M:N)
class SeedSupplierLink(BaseModel):
    """Verknüpfung zwischen Sorte und Lieferant"""
    supplier_id: UUID
    is_default: bool = False
    notizen: Optional[str] = None


class SeedSupplierResponse(BaseModel):
    """Verknüpfung mit eingebettetem Lieferanten-Detail"""
    model_config = ConfigDict(from_attributes=True)

    supplier_id: UUID
    is_default: bool
    notizen: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_email: Optional[str] = None
