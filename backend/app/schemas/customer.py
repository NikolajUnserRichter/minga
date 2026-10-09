from typing import Optional
"""
Pydantic Schemas für Kunden - ERP-erweitert
Mit Adressen, Payment Terms und Steuer-IDs
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator, model_validator
from pydantic_core import PydanticCustomError

from app.models.customer import CustomerType, SubscriptionInterval, PaymentTerms, AddressType, PfandAbrechnung
from app.models.customer import InvoiceMode
from app.models.sepa_mandate import Zahlungsart


from app.core.email_adressen import pruefe_empfaenger

# Belegversand (Paket 3, Q2): Empfängerlisten je Belegart
_EMPFAENGER_FELDER = ("confirmation_emails", "delivery_note_emails", "invoice_emails")
_EMPFAENGER_TITEL = {
    "confirmation_emails": "Empfänger Auftragsbestätigung",
    "delivery_note_emails": "Empfänger Lieferschein",
    "invoice_emails": "Empfänger Rechnung",
}


def _empfaengerliste(v, info):
    """None/[] = Haupt-E-Mail; sonst geprüft, klein geschrieben, ohne Dubletten."""
    try:
        return pruefe_empfaenger(v, feld=_EMPFAENGER_TITEL[info.field_name])
    except ValueError as error:
        raise PydanticCustomError("empfaengerliste", "{meldung}", {"meldung": str(error)}) from None


# ============================================================
# CUSTOMER ADDRESS SCHEMAS
# ============================================================

class CustomerAddressBase(BaseModel):
    """Basis-Schema für Kundenadresse"""
    address_type: AddressType = Field(default=AddressType.BOTH, description="Adresstyp")
    is_default: bool = Field(default=False, description="Standard-Adresse?")
    name: Optional[str] = Field(None, max_length=200, description="Abweichender Name")
    strasse: str = Field(..., min_length=1, max_length=200, description="Straße")
    hausnummer: Optional[str] = Field(None, max_length=20, description="Hausnummer")
    adresszusatz: Optional[str] = Field(None, max_length=200, description="Adresszusatz (c/o, Etage)")
    plz: str = Field(..., min_length=4, max_length=10, description="Postleitzahl")
    ort: str = Field(..., min_length=1, max_length=100, description="Stadt/Ort")
    land: str = Field(default="DE", min_length=2, max_length=2, description="Land (ISO 3166-1)")
    lieferhinweise: Optional[str] = Field(None, description="Lieferhinweise")


class CustomerAddressCreate(CustomerAddressBase):
    """Schema zum Erstellen einer Adresse"""
    customer_id: UUID = Field(..., description="Kunden-ID")


class CustomerAddressUpdate(BaseModel):
    """Schema zum Aktualisieren einer Adresse"""
    address_type: Optional[AddressType] = None
    is_default: Optional[bool] = None
    name: Optional[str] = None
    strasse: Optional[str] = None
    hausnummer: Optional[str] = None
    adresszusatz: Optional[str] = None
    plz: Optional[str] = None
    ort: Optional[str] = None
    land: Optional[str] = None
    lieferhinweise: Optional[str] = None


class CustomerAddressResponse(CustomerAddressBase):
    """Schema für Adress-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    created_at: datetime
    updated_at: datetime

    # Berechnetes Feld
    full_address: Optional[str] = None


class CustomerAddressListResponse(BaseModel):
    """Schema für Adressen-Liste"""
    items: list[CustomerAddressResponse]
    total: int


# ============================================================
# CUSTOMER SCHEMAS (ERP-erweitert)
# ============================================================

class CustomerBase(BaseModel):
    """Basis-Schema für Kunden"""
    name: str = Field(..., min_length=1, max_length=200, description="Kundenname")
    typ: CustomerType = Field(..., description="Kundentyp")
    email: Optional[EmailStr] = Field(None, description="E-Mail-Adresse (Hauptkontakt)")
    telefon: Optional[str] = Field(None, max_length=50, description="Telefonnummer")
    adresse: Optional[str] = Field(None, description="Adresse (Legacy)")
    liefertage: Optional[list[int]] = Field(None, description="Liefertage (0=Mo, 6=So)")


class CustomerCreate(CustomerBase):
    """Schema zum Erstellen eines Kunden"""
    # Kundennummer
    customer_number: Optional[str] = Field(None, max_length=20, description="Kundennummer")

    # Ansprechpartner
    ansprechpartner_name: Optional[str] = Field(None, max_length=200, description="Ansprechpartner Name")
    ansprechpartner_email: Optional[EmailStr] = Field(None, description="Ansprechpartner E-Mail")
    ansprechpartner_telefon: Optional[str] = Field(None, max_length=50, description="Ansprechpartner Telefon")

    # Steuer-IDs
    ust_id: Optional[str] = Field(None, max_length=20, description="USt-IdNr. (DE123456789)")
    steuernummer: Optional[str] = Field(None, max_length=20, description="Steuernummer")

    # Zahlungsbedingungen
    payment_terms: PaymentTerms = Field(default=PaymentTerms.NET_14, description="Zahlungsbedingungen")
    credit_limit: Optional[Decimal] = Field(None, ge=0, description="Kreditlimit in EUR")

    # Preisgruppe
    price_list_id: Optional[UUID] = Field(None, description="Preislisten-ID")
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Rabatt %")

    # Skonto (Frühzahler-Rabatt)
    skonto_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Skonto %")
    skonto_days: int = Field(default=0, ge=0, le=90, description="Skontofrist in Tagen")

    # Verpackungsgebühr
    packaging_fee_amount: Decimal = Field(default=Decimal("0"), ge=0, description="Verpackungsgebühr (Fixbetrag EUR)")
    packaging_fee_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Verpackungsrabatt %")

    # Preise auf Lieferschein andrucken
    show_prices_on_delivery_note: bool = Field(default=False, description="Preise auf Lieferschein andrucken")

    # Pfandabrechnung: JE_LIEFERUNG (auf jeder Rechnung) oder KEINE (IFCO-Clearing)
    pfand_abrechnung: PfandAbrechnung = Field(
        default=PfandAbrechnung.JE_LIEFERUNG,
        description=(
            "JE_LIEFERUNG: Pfand auf jeder Rechnung; KEINE: über IFCO-Clearing, nicht auf der Rechnung; "
            "MONATLICH: Leergutkonto, einmal im Monat abgerechnet"
        ),
    )

    # Abrechnungsart (B5): EINZELN oder MONATLICH (Monats-Sammelrechnung)
    invoice_mode: InvoiceMode = Field(
        default=InvoiceMode.EINZELN,
        description="EINZELN: Rechnung je Lieferung; MONATLICH: Monats-Sammelrechnung als Entwurf am 1. des Folgemonats",
    )

    # DATEV
    datev_account: Optional[str] = Field(None, max_length=10, description="DATEV-Kontonummer")

    # Belegversand: Empfänger je Belegart (leer = Haupt-E-Mail)
    confirmation_emails: list[str] = Field(default_factory=list, description="Empfänger Auftragsbestätigung")
    delivery_note_emails: list[str] = Field(default_factory=list, description="Empfänger Lieferschein")
    invoice_emails: list[str] = Field(default_factory=list, description="Empfänger Rechnung")

    _empfaenger_pruefen = field_validator(*_EMPFAENGER_FELDER, mode="before")(_empfaengerliste)

    # Notizen
    notizen: Optional[str] = Field(None, description="Interne Notizen")

    # Adressen (optional bei Erstellung)
    addresses: Optional[list[CustomerAddressBase]] = Field(None, description="Adressen")


class CustomerUpdate(BaseModel):
    """Schema zum Aktualisieren eines Kunden"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    typ: Optional[CustomerType] = None
    email: Optional[EmailStr] = None
    telefon: Optional[str] = None
    adresse: Optional[str] = None
    liefertage: Optional[list[int]] = None

    # Kundennummer
    customer_number: Optional[str] = None

    # Ansprechpartner
    ansprechpartner_name: Optional[str] = None
    ansprechpartner_email: Optional[EmailStr] = None
    ansprechpartner_telefon: Optional[str] = None

    # Steuer-IDs
    ust_id: Optional[str] = None
    steuernummer: Optional[str] = None

    # Zahlungsbedingungen
    payment_terms: Optional[PaymentTerms] = None
    credit_limit: Optional[Decimal] = None

    # Preisgruppe
    price_list_id: Optional[UUID] = None
    discount_percent: Optional[Decimal] = None

    # Skonto + Verpackung
    skonto_percent: Optional[Decimal] = None
    skonto_days: Optional[int] = None
    packaging_fee_amount: Optional[Decimal] = None
    packaging_fee_percent: Optional[Decimal] = None

    # Preise auf Lieferschein andrucken
    show_prices_on_delivery_note: Optional[bool] = None

    # Pfandabrechnung (weglassen = unverändert; null wird abgewiesen)
    pfand_abrechnung: Optional[PfandAbrechnung] = None

    @field_validator("pfand_abrechnung")
    @classmethod
    def _pfand_abrechnung_nicht_leer(cls, v):
        # Die Spalte ist NOT NULL. Ein ausdrückliches null ergäbe beim Commit
        # einen Datenbankfehler (500); ein weggelassenes Feld erreicht den
        # Validator nicht.
        if v is None:
            raise ValueError("pfand_abrechnung darf nicht leer sein")
        return v

    # Abrechnungsart (weglassen = unverändert; null wird abgewiesen)
    invoice_mode: Optional[InvoiceMode] = None

    @field_validator("invoice_mode")
    @classmethod
    def _invoice_mode_nicht_leer(cls, v):
        # NOT-NULL-Spalte: ein ausdrückliches null ergäbe beim Commit einen
        # Datenbankfehler (500). Ein weggelassenes Feld erreicht den Validator nicht.
        if v is None:
            raise ValueError("invoice_mode darf nicht leer sein")
        return v

    # DATEV
    datev_account: Optional[str] = None

    # Belegversand: Empfänger je Belegart (null oder [] = Haupt-E-Mail)
    confirmation_emails: Optional[list[str]] = None
    delivery_note_emails: Optional[list[str]] = None
    invoice_emails: Optional[list[str]] = None

    _empfaenger_pruefen = field_validator(*_EMPFAENGER_FELDER, mode="before")(_empfaengerliste)

    # Notizen
    notizen: Optional[str] = None

    # Status
    aktiv: Optional[bool] = None


class CustomerResponse(CustomerBase):
    """Schema für Kunden-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_number: Optional[str]
    ansprechpartner_name: Optional[str]
    ansprechpartner_email: Optional[str]
    ansprechpartner_telefon: Optional[str]
    ust_id: Optional[str]
    steuernummer: Optional[str]
    payment_terms: PaymentTerms
    credit_limit: Optional[Decimal]
    price_list_id: Optional[UUID]
    discount_percent: Decimal
    skonto_percent: Decimal = Decimal("0")
    skonto_days: int = 0
    packaging_fee_amount: Decimal = Decimal("0")
    packaging_fee_percent: Decimal = Decimal("0")
    show_prices_on_delivery_note: bool = False
    pfand_abrechnung: PfandAbrechnung = PfandAbrechnung.JE_LIEFERUNG
    # Stichtag des Leergutkontos (nur bei MONATLICH, vom Server gesetzt)
    pfand_monatlich_ab: Optional[date] = None
    invoice_mode: InvoiceMode = InvoiceMode.EINZELN

    datev_account: Optional[str]
    # Nur lesend (B10): geändert über PUT /sepa/kunden/{id}/zahlungsart.
    # NULL = Überweisung. Bankdaten stehen nie im Kunden-Schema.
    zahlungsart: Optional[Zahlungsart] = None
    notizen: Optional[str]
    aktiv: bool
    created_at: datetime
    updated_at: datetime

    # Expandierte Felder
    price_list_name: Optional[str] = None

    # Belegversand (Paket 3, Q2): Empfänger je Belegart; Bestandskunden NULL → []
    confirmation_emails: list[str] = []
    delivery_note_emails: list[str] = []
    invoice_emails: list[str] = []

    @field_validator(*_EMPFAENGER_FELDER, mode="before")
    @classmethod
    def _empfaenger_leer(cls, v):
        return v or []

    # Berechnete Felder
    payment_days: Optional[int] = None


class CustomerDetailResponse(CustomerResponse):
    """Detailliertes Kunden-Schema mit Adressen"""
    addresses: list[CustomerAddressResponse] = []
    billing_address: Optional[CustomerAddressResponse] = None
    shipping_address: Optional[CustomerAddressResponse] = None


class CustomerListResponse(BaseModel):
    """Schema für Kunden-Liste"""
    items: list[CustomerResponse]
    total: int


# ============================================================
# CONTACT (ANSPRECHPARTNER) SCHEMAS
# ============================================================

class ContactBase(BaseModel):
    """Ansprechpartner pro Kunde"""
    name: str = Field(..., min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    telefon: Optional[str] = Field(None, max_length=50)
    role: str = Field(default="ALLGEMEIN", description="ALLGEMEIN | EINKAUF | VERTRIEB | BUCHHALTUNG | TECHNIK")
    is_primary: bool = Field(default=False)
    notizen: Optional[str] = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    telefon: Optional[str] = None
    role: Optional[str] = None
    is_primary: Optional[bool] = None
    notizen: Optional[str] = None


class ContactResponse(ContactBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    created_at: datetime
    updated_at: datetime


# ============================================================
# SUBSCRIPTION SCHEMAS
# ============================================================

class SubscriptionBase(BaseModel):
    """Basis-Schema für Abonnement"""
    menge: Decimal = Field(..., gt=0, description="Bestellmenge")
    einheit: str = Field(..., description="Einheit (GRAMM, BUND, SCHALE)")
    intervall: SubscriptionInterval = Field(..., description="Lieferintervall")
    liefertage: Optional[list[int]] = Field(None, description="Liefertage")
    gueltig_von: date = Field(..., description="Startdatum")
    gueltig_bis: Optional[date] = Field(None, description="Enddatum")


class SubscriptionPositionIn(BaseModel):
    """Position eines Abos (B6): Produkt bzw. Verpackungsvariante, Menge, Einheit.

    Kein Preisfeld: Der Preis kommt im Abo-Lauf wie in create_order aus
    Sonderpreis, Variante und Basispreis. Paket 3 (Q4) lässt Abos für die
    Halle offen, weil sie keine Preise tragen. extra="forbid": ein
    mitgeschicktes unit_price o. ä. ist ein Fehler (422), kein stilles Weglassen.
    """
    model_config = ConfigDict(extra="forbid")

    product_id: Optional[UUID] = Field(None, description="Produkt-ID")
    product_variant_id: Optional[UUID] = Field(None, description="Verpackungs-Variante")
    seed_id: Optional[UUID] = Field(None, description="Saatgut-ID (Legacy)")
    menge: Decimal = Field(..., gt=0, description="Menge je Lieferung")
    einheit: str = Field(..., min_length=1, max_length=20, description="Einheit (STUECK, SCHALE, KISTE_12 …)")


class SubscriptionPositionResponse(BaseModel):
    """Position eines Abos in der Antwort (B6)"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position: int
    product_id: Optional[UUID] = None
    product_variant_id: Optional[UUID] = None
    seed_id: Optional[UUID] = None
    menge: Decimal
    einheit: str
    # "Produkt — Variante" bzw. Sorte (SubscriptionItem.bezeichnung)
    bezeichnung: Optional[str] = None


class SubscriptionCreate(SubscriptionBase):
    """Schema zum Erstellen eines Abonnements.

    Seit B6 mit `positionen` (ein oder mehrere Produkte je Lieferung). Die
    Einzelfelder product_id/product_variant_id/seed_id mit menge und einheit
    gelten weiter und ergeben genau eine Position; beides zugleich ist ein
    Fehler (422).
    """
    kunde_id: UUID = Field(..., description="Kunden-ID")
    seed_id: Optional[UUID] = Field(None, description="Saatgut-ID (Legacy)")
    product_id: Optional[UUID] = Field(None, description="Produkt-ID")
    product_variant_id: Optional[UUID] = Field(None, description="Verpackungs-Variante")
    menge: Optional[Decimal] = Field(None, gt=0, description="Bestellmenge (ohne positionen)")
    # Grenzen wie SubscriptionPositionIn.einheit: als_positionen() baut daraus
    # eine Position, ein zu langer Wert wäre dort ein 500 statt 422.
    einheit: Optional[str] = Field(None, min_length=1, max_length=20, description="Einheit (ohne positionen)")
    positionen: Optional[list[SubscriptionPositionIn]] = Field(
        None, min_length=1, max_length=50, description="Positionen je Lieferung (B6)"
    )

    @model_validator(mode="after")
    def _positionen_oder_einzelprodukt(self):
        einzelfelder = (self.product_id, self.product_variant_id, self.seed_id, self.menge, self.einheit)
        if self.positionen is not None:
            if any(wert is not None for wert in einzelfelder):
                raise ValueError(
                    "Entweder positionen oder product_id/seed_id mit menge und einheit, nicht beides"
                )
        elif self.menge is None or not self.einheit:
            raise ValueError("Bitte mindestens eine Position angeben (positionen oder menge und einheit)")
        return self

    def als_positionen(self) -> list[SubscriptionPositionIn]:
        """Die Positionen des neuen Abos; die Einzelfelder ergeben genau eine."""
        if self.positionen is not None:
            return self.positionen
        return [SubscriptionPositionIn(
            product_id=self.product_id, product_variant_id=self.product_variant_id,
            seed_id=self.seed_id, menge=self.menge, einheit=self.einheit,
        )]


class SubscriptionUpdate(BaseModel):
    """Schema zum Aktualisieren eines Abonnements.

    `positionen` ersetzt die ganze Liste (B6). menge/einheit wie bisher ändern
    die einzige Position; bei mehreren Positionen antwortet die API mit 400.
    """
    menge: Optional[Decimal] = Field(None, gt=0)
    # Grenzen wie SubscriptionPositionIn.einheit: der Wert landet in der Position
    einheit: Optional[str] = Field(None, min_length=1, max_length=20)
    intervall: Optional[SubscriptionInterval] = None
    liefertage: Optional[list[int]] = None
    gueltig_bis: Optional[date] = None
    aktiv: Optional[bool] = None
    positionen: Optional[list[SubscriptionPositionIn]] = Field(None, min_length=1, max_length=50)

    @model_validator(mode="after")
    def _positionen_oder_menge(self):
        if self.positionen is not None and (self.menge is not None or self.einheit is not None):
            raise ValueError("Entweder positionen oder menge/einheit ändern, nicht beides")
        return self


class SubscriptionResponse(SubscriptionBase):
    """Schema für Abonnement-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kunde_id: UUID
    seed_id: Optional[UUID] = None
    product_id: Optional[UUID] = None
    product_variant_id: Optional[UUID] = None
    aktiv: bool
    created_at: datetime
    updated_at: datetime

    # Berechnete Felder
    ist_aktiv: bool

    # Expandierte Felder
    kunde_name: Optional[str] = None
    seed_name: Optional[str] = None
    product_name: Optional[str] = None

    # B6: alle Positionen; die Kopffelder oben spiegeln Position 1
    positionen: list[SubscriptionPositionResponse] = []


class SubscriptionListResponse(BaseModel):
    """Schema für Abonnement-Liste"""
    items: list[SubscriptionResponse]
    total: int
