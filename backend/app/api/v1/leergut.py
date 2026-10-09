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
