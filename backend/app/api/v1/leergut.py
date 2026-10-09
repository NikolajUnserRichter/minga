"""Leergutkonto (Paket 3, Q6): Pfandkisten je Kunde.

Der Router hängt an der Belegkette (_deps_belege in main.py): auch die Halle
(production_staff) liest die Pfandartikel und das Konto und erfasst
Rücknahmen. Korrekturen und Anfangsbestand nur Verwaltung, Vertrieb und
Buchhaltung. Abgerechnet wird im Rechnungsrouter (/invoices/leergut-run).
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, require_role
from app.models.customer import Customer, PfandAbrechnung
from app.models.enums import TaxRate
from app.models.leergut import LeergutArt, LeergutBewegung
from app.models.product import Product
from app.services import leergut_service as leergut

router = APIRouter(prefix="/leergut", tags=["Leergut"])

#: Korrekturen und Anfangsbestand ändern, was abgerechnet wird
_VERWALTUNG = ["admin", "sales", "accounting"]


class LeergutArtikel(BaseModel):
    id: UUID
    sku: str
    name: str
    einzelwert: Decimal
    tax_rate: TaxRate


class LeergutKundeKurz(BaseModel):
    customer_id: UUID
    name: str
    pfand_abrechnung: PfandAbrechnung
    stueck_beim_kunden: int


class LeergutSaldo(BaseModel):
    product_id: UUID
    artikel: str
    stueck: int
    wert: Decimal
    offen_stueck: int
    offen_wert: Decimal


class LeergutBewegungResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    artikel: str
    art: LeergutArt
    menge: int
    einzelwert: Decimal
    leistungsdatum: date
    order_line_id: Optional[UUID]
    delivery_note_id: Optional[UUID]
    invoice_id: Optional[UUID]
    bereits_berechnet: bool
    erfasst_von: Optional[str]
    erfasst_am: datetime
    notiz: Optional[str]


class LeergutKonto(BaseModel):
    customer_id: UUID
    customer_name: str
    pfand_abrechnung: PfandAbrechnung
    pfand_monatlich_ab: Optional[date]
    salden: list[LeergutSaldo]
    bewegungen: list[LeergutBewegungResponse]


def _kunde(db, customer_id: UUID) -> Customer:
    kunde = db.get(Customer, customer_id)
    if kunde is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")
    return kunde


@router.get("/artikel", response_model=list[LeergutArtikel])
def list_pfandartikel(db: DBSession):
    """Aktive Pfandartikel für die Auswahl „Kistenart" — eigener Lese-Endpunkt,
    damit die Halle nicht den ganzen Produktkatalog braucht."""
    produkte = db.execute(
        select(Product)
        .where(Product.is_deposit.is_(True), Product.is_active.is_(True))
        .order_by(Product.name)
    ).scalars().all()
    return [LeergutArtikel(id=p.id, sku=p.sku, name=p.name,
                           einzelwert=leergut.pfandwert(p), tax_rate=p.tax_rate) for p in produkte]


@router.get("/kunden", response_model=list[LeergutKundeKurz])
def list_kunden_mit_konto(db: DBSession):
    return leergut.kunden_mit_konto(db)


@router.get("/kunden/{customer_id}", response_model=LeergutKonto)
def get_konto(customer_id: UUID, db: DBSession):
    return leergut.konto(db, _kunde(db, customer_id))


class LeergutMenge(BaseModel):
    product_id: UUID
    menge: int = Field(..., gt=0, le=10000)


class RuecknahmeCreate(BaseModel):
    leistungsdatum: Optional[date] = Field(None, description="Rückgabetag, leer = heute")
    positionen: list[LeergutMenge] = Field(..., min_length=1)
    delivery_note_id: Optional[UUID] = None
    notiz: Optional[str] = Field(None, max_length=500)


class KorrekturCreate(BaseModel):
    art: Literal["KORREKTUR_PLUS", "KORREKTUR_MINUS", "ANFANGSBESTAND"]
    product_id: UUID
    menge: int = Field(..., gt=0, le=10000)
    leistungsdatum: Optional[date] = None
    notiz: str = Field(..., min_length=3, max_length=500, description="Begründung, Pflicht")
    bereits_berechnet: bool = Field(
        True, description="Nur ANFANGSBESTAND: Kisten wurden schon berechnet (Altsystem, Rechnung)")


def _wer(user: dict) -> Optional[str]:
    return (user or {}).get("username") or (user or {}).get("email")


@router.post("/kunden/{customer_id}/ruecknahmen", response_model=list[LeergutBewegungResponse],
             status_code=status.HTTP_201_CREATED)
def create_ruecknahme(customer_id: UUID, data: RuecknahmeCreate, db: DBSession, user: CurrentUser):
    """Rückgabe als Stückzahl je Kistenart — auch von der Halle."""
    try:
        neu = leergut.erfasse(
            db, _kunde(db, customer_id), LeergutArt.RUECKNAHME,
            [(p.product_id, p.menge) for p in data.positionen],
            tag=data.leistungsdatum, erfasst_von=_wer(user), notiz=data.notiz,
            delivery_note_id=data.delivery_note_id,
        )
    except leergut.LeergutFehler as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return neu


@router.post("/kunden/{customer_id}/korrekturen", response_model=list[LeergutBewegungResponse],
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_role(_VERWALTUNG))])
def create_korrektur(customer_id: UUID, data: KorrekturCreate, db: DBSession, user: CurrentUser):
    """Gegenbuchung (abgerechnete Bewegungen sind unveränderlich) oder
    Anfangsbestand vor dem Stichtag."""
    try:
        neu = leergut.erfasse(
            db, _kunde(db, customer_id), LeergutArt(data.art), [(data.product_id, data.menge)],
            tag=data.leistungsdatum, erfasst_von=_wer(user), notiz=data.notiz,
            bereits_berechnet=data.bereits_berechnet,
        )
    except leergut.LeergutFehler as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return neu


@router.delete("/bewegungen/{bewegung_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bewegung(bewegung_id: UUID, db: DBSession, user: CurrentUser):
    """Nur offene Rücknahmen (alle) bzw. offene Korrekturen und Anfangsbestände
    (Verwaltung). Ausgaben entstehen aus Lieferungen und werden per Gegenbuchung
    berichtigt; abgerechnete Bewegungen sind unveränderlich."""
    bewegung = db.get(LeergutBewegung, bewegung_id)
    if bewegung is None:
        raise HTTPException(status_code=404, detail="Bewegung nicht gefunden")
    if bewegung.invoice_id is not None:
        raise HTTPException(status_code=400, detail="Abgerechnete Bewegungen lassen sich nur per Korrektur berichtigen")
    if bewegung.art == LeergutArt.AUSGABE:
        raise HTTPException(status_code=400, detail="Ausgaben entstehen aus Lieferungen — Korrektur über eine Gegenbuchung")
    if bewegung.art != LeergutArt.RUECKNAHME and not set((user or {}).get("roles", [])) & set(_VERWALTUNG):
        raise HTTPException(status_code=403, detail="Keine Berechtigung für diese Aktion")
    db.delete(bewegung)
    db.commit()
