"""Schemas für SEPA-Lastschriftmandate (B10). Nur unter /api/v1/sepa —
also nur für Admin und Buchhaltung. Kein Bankfeld in den Kunden-Schemas."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.models.sepa_mandate import LastschriftStatus, Mandatsart, Zahlungsart
from app.services.sepa_service import (
    bic_pruefen, heute_berlin, iban_maskiert, iban_pruefen, mandatsreferenz_pruefen,
)


class MandatCreate(BaseModel):
    mandatsreferenz: str
    mandatsart: Mandatsart = Mandatsart.CORE
    unterschrieben_am: date
    kontoinhaber: str = Field(..., min_length=1, max_length=70)
    iban: str
    bic: Optional[str] = None
    bank_name: Optional[str] = Field(None, max_length=100)

    @field_validator("mandatsreferenz")
    @classmethod
    def _ref(cls, v):
        return mandatsreferenz_pruefen(v)

    @field_validator("iban")
    @classmethod
    def _iban(cls, v):
        return iban_pruefen(v)

    @field_validator("bic")
    @classmethod
    def _bic(cls, v):
        return bic_pruefen(v)

    @field_validator("unterschrieben_am")
    @classmethod
    def _datum(cls, v):
        if v > heute_berlin():
            raise ValueError("Datum der Unterschrift liegt in der Zukunft")
        return v

    @field_validator("kontoinhaber", "bank_name")
    @classmethod
    def _text(cls, v):
        return v.strip() if isinstance(v, str) else v


class MandatUpdate(BaseModel):
    """Felder weglassen = unverändert. Referenz, Datum und Art nur, solange
    keine Rechnung mit diesem Mandat festgeschrieben ist."""
    mandatsreferenz: Optional[str] = None
    mandatsart: Optional[Mandatsart] = None
    unterschrieben_am: Optional[date] = None
    kontoinhaber: Optional[str] = Field(None, min_length=1, max_length=70)
    iban: Optional[str] = None
    bic: Optional[str] = None
    bank_name: Optional[str] = Field(None, max_length=100)

    @field_validator("mandatsreferenz")
    @classmethod
    def _ref(cls, v):
        return None if v is None else mandatsreferenz_pruefen(v)

    @field_validator("iban")
    @classmethod
    def _iban(cls, v):
        return None if v is None else iban_pruefen(v)

    @field_validator("bic")
    @classmethod
    def _bic(cls, v):
        return bic_pruefen(v)

    @field_validator("unterschrieben_am")
    @classmethod
    def _datum(cls, v):
        if v is not None and v > heute_berlin():
            raise ValueError("Datum der Unterschrift liegt in der Zukunft")
        return v


class MandatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    mandatsreferenz: str
    mandatsart: Mandatsart
    unterschrieben_am: date
    kontoinhaber: str
    iban: str
    bic: Optional[str]
    bank_name: Optional[str]
    aktiv: bool
    widerrufen_am: Optional[date]
    letzter_einzug_am: Optional[date]
    aenderungen: Optional[list] = None
    created_at: datetime
    created_by: Optional[str] = None

    @computed_field
    @property
    def iban_maskiert(self) -> str:
        return iban_maskiert(self.iban)


class MandateUebersicht(BaseModel):
    """Mandate eines Kunden. Die Gläubiger-ID kommt mit, weil die Buchhaltung
    /admin/settings nicht lesen darf."""
    customer_id: UUID
    zahlungsart: Optional[Zahlungsart]
    glaeubiger_id: Optional[str]
    mandate: list[MandatResponse]


class ZahlungsartUpdate(BaseModel):
    zahlungsart: Zahlungsart


class WiderrufRequest(BaseModel):
    """Leer = heute. Nicht in der Zukunft; nicht vor der Unterschrift (prüft der Endpunkt)."""
    widerrufen_am: Optional[date] = None

    @field_validator("widerrufen_am")
    @classmethod
    def _datum(cls, v):
        if v is not None and v > heute_berlin():
            raise ValueError("Datum des Widerrufs liegt in der Zukunft")
        return v


class WiderrufResponse(BaseModel):
    mandat: MandatResponse
    zahlungsart: Optional[Zahlungsart]
    #: Festgeschriebene Rechnungen mit Lastschrifthinweis, deren Einzug noch
    #: aussteht: nicht mehr einziehen; für Überweisung stornieren und neu ausstellen.
    offene_lastschriften: list[str]


class EinzugZeile(BaseModel):
    invoice_id: UUID
    invoice_number: str
    customer_id: UUID
    customer_name: str
    rechnungsdatum: date
    betrag: Decimal
    waehrung: str
    einzugsdatum: date
    ueberfaellig_seit_tagen: int
    #: Erster erfolgreicher Mailversand der Rechnung (= der Vorabankündigung)
    versendet_am: Optional[datetime]
    #: RECHTZEITIG | ZU_SPAET | NICHT_PER_MAIL
    ankuendigung: str
    #: Tag der Einreichung bei der Bank (CSV); eine Rechnung nur einmal
    eingereicht_am: Optional[date]
    mandat_id: UUID
    mandatsreferenz: str
    mandatsart: Mandatsart
    unterschrieben_am: date
    kontoinhaber: str
    iban: str
    bic: Optional[str]
    bank_name: Optional[str]
    mandat_aktiv: bool


class EinreichungRequest(BaseModel):
    invoice_ids: list[UUID] = Field(..., min_length=1)
    #: Für Rechnungen ohne rechtzeitig per Mail versendete Vorabankündigung:
    #: Sie ging nachweislich auf anderem Weg rechtzeitig hinaus (wird an der
    #: Rechnung vermerkt). Ohne Bestätigung: 409.
    ankuendigung_bestaetigt: bool = False


class EinzugBuchenRequest(BaseModel):
    invoice_ids: list[UUID] = Field(..., min_length=1)
    datum: date

    @field_validator("datum")
    @classmethod
    def _nicht_in_der_zukunft(cls, v):
        if v > heute_berlin():
            raise ValueError("Einzugsdatum liegt in der Zukunft — gebucht wird, was auf dem Konto ist")
        return v


class EinzugBuchenResponse(BaseModel):
    gebucht: list[str]
    #: z. B. "eingezogen am …, angekündigt war der …" (früher als angekündigt)
    hinweise: list[str] = []
