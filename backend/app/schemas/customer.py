"""
Pydantic Schemas für Kunden - ERP-erweitert
Mit Adressen, Payment Terms und Steuer-IDs
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, EmailStr

from app.models.customer import CustomerType, SubscriptionInterval, PaymentTerms, AddressType


# ============================================================
# CUSTOMER ADDRESS SCHEMAS
# ============================================================

class CustomerAddressBase(BaseModel):
    """Basis-Schema für Kundenadresse"""
    address_type: AddressType = Field(default=AddressType.BOTH, description="Adresstyp")
    is_default: bool = Field(default=False, description="Standard-Adresse?")
    name: str | None = Field(None, max_length=200, description="Abweichender Name")
    strasse: str = Field(..., min_length=1, max_length=200, description="Straße")
    hausnummer: str | None = Field(None, max_length=20, description="Hausnummer")
    adresszusatz: str | None = Field(None, max_length=200, description="Adresszusatz (c/o, Etage)")
    plz: str = Field(..., min_length=4, max_length=10, description="Postleitzahl")
    ort: str = Field(..., min_length=1, max_length=100, description="Stadt/Ort")
    land: str = Field(default="DE", min_length=2, max_length=2, description="Land (ISO 3166-1)")
    lieferhinweise: str | None = Field(None, description="Lieferhinweise")


class CustomerAddressCreate(CustomerAddressBase):
    """Schema zum Erstellen einer Adresse"""
    customer_id: UUID = Field(..., description="Kunden-ID")


class CustomerAddressUpdate(BaseModel):
    """Schema zum Aktualisieren einer Adresse"""
    address_type: AddressType | None = None
    is_default: bool | None = None
    name: str | None = None
    strasse: str | None = None
    hausnummer: str | None = None
    adresszusatz: str | None = None
    plz: str | None = None
    ort: str | None = None
    land: str | None = None
    lieferhinweise: str | None = None


class CustomerAddressResponse(CustomerAddressBase):
    """Schema für Adress-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    created_at: datetime
    updated_at: datetime

    # Berechnetes Feld
    full_address: str | None = None


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
    email: EmailStr | None = Field(None, description="E-Mail-Adresse")
    telefon: str | None = Field(None, max_length=50, description="Telefonnummer")
    adresse: str | None = Field(None, description="Adresse (Legacy)")
    liefertage: list[int] | None = Field(None, description="Liefertage (0=Mo, 6=So)")


class CustomerCreate(CustomerBase):
    """Schema zum Erstellen eines Kunden"""
    # Kundennummer
    customer_number: str | None = Field(None, max_length=20, description="Kundennummer")

    # Ansprechpartner
    ansprechpartner_name: str | None = Field(None, max_length=200, description="Ansprechpartner Name")
    ansprechpartner_email: EmailStr | None = Field(None, description="Ansprechpartner E-Mail")
    ansprechpartner_telefon: str | None = Field(None, max_length=50, description="Ansprechpartner Telefon")

    # Steuer-IDs
    ust_id: str | None = Field(None, max_length=20, description="USt-IdNr. (DE123456789)")
    steuernummer: str | None = Field(None, max_length=20, description="Steuernummer")

    # Zahlungsbedingungen
    payment_terms: PaymentTerms = Field(default=PaymentTerms.NET_14, description="Zahlungsbedingungen")
    credit_limit: Decimal | None = Field(None, ge=0, description="Kreditlimit in EUR")

    # Preisgruppe
    price_list_id: UUID | None = Field(None, description="Preislisten-ID")
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Rabatt %")

    # DATEV
    datev_account: str | None = Field(None, max_length=10, description="DATEV-Kontonummer")

    # Notizen
    notizen: str | None = Field(None, description="Interne Notizen")

    # Adressen (optional bei Erstellung)
    addresses: list[CustomerAddressBase] | None = Field(None, description="Adressen")


class CustomerUpdate(BaseModel):
    """Schema zum Aktualisieren eines Kunden"""
    name: str | None = Field(None, min_length=1, max_length=200)
    typ: CustomerType | None = None
    email: EmailStr | None = None
    telefon: str | None = None
    adresse: str | None = None
    liefertage: list[int] | None = None

    # Kundennummer
    customer_number: str | None = None

    # Ansprechpartner
    ansprechpartner_name: str | None = None
    ansprechpartner_email: EmailStr | None = None
    ansprechpartner_telefon: str | None = None

    # Steuer-IDs
    ust_id: str | None = None
    steuernummer: str | None = None

    # Zahlungsbedingungen
    payment_terms: PaymentTerms | None = None
    credit_limit: Decimal | None = None

    # Preisgruppe
    price_list_id: UUID | None = None
    discount_percent: Decimal | None = None

    # DATEV
    datev_account: str | None = None

    # Notizen
    notizen: str | None = None

    # Status
    aktiv: bool | None = None


class CustomerResponse(CustomerBase):
    """Schema für Kunden-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_number: str | None
    ansprechpartner_name: str | None
    ansprechpartner_email: str | None
    ansprechpartner_telefon: str | None
    ust_id: str | None
    steuernummer: str | None
    payment_terms: PaymentTerms
    credit_limit: Decimal | None
    price_list_id: UUID | None
    discount_percent: Decimal
    datev_account: str | None
    notizen: str | None
    aktiv: bool
    created_at: datetime
    updated_at: datetime

    # Expandierte Felder
    price_list_name: str | None = None

    # Berechnete Felder
    payment_days: int | None = None


class CustomerDetailResponse(CustomerResponse):
    """Detailliertes Kunden-Schema mit Adressen"""
    addresses: list[CustomerAddressResponse] = []
    billing_address: CustomerAddressResponse | None = None
    shipping_address: CustomerAddressResponse | None = None


class CustomerListResponse(BaseModel):
    """Schema für Kunden-Liste"""
    items: list[CustomerResponse]
    total: int


# ============================================================
# SUBSCRIPTION SCHEMAS
# ============================================================

class SubscriptionBase(BaseModel):
    """Basis-Schema für Abonnement"""
    menge: Decimal = Field(..., gt=0, description="Bestellmenge")
    einheit: str = Field(..., description="Einheit (GRAMM, BUND, SCHALE)")
    intervall: SubscriptionInterval = Field(..., description="Lieferintervall")
    liefertage: list[int] | None = Field(None, description="Liefertage")
    gueltig_von: date = Field(..., description="Startdatum")
    gueltig_bis: date | None = Field(None, description="Enddatum")


class SubscriptionCreate(SubscriptionBase):
    """Schema zum Erstellen eines Abonnements"""
    kunde_id: UUID = Field(..., description="Kunden-ID")
    seed_id: UUID = Field(..., description="Produkt-ID")


class SubscriptionUpdate(BaseModel):
    """Schema zum Aktualisieren eines Abonnements"""
    menge: Decimal | None = Field(None, gt=0)
    einheit: str | None = None
    intervall: SubscriptionInterval | None = None
    liefertage: list[int] | None = None
    gueltig_bis: date | None = None
    aktiv: bool | None = None


class SubscriptionResponse(SubscriptionBase):
    """Schema für Abonnement-Antwort"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kunde_id: UUID
    seed_id: UUID
    aktiv: bool
    created_at: datetime
    updated_at: datetime

    # Berechnete Felder
    ist_aktiv: bool

    # Expandierte Felder
    kunde_name: str | None = None
    seed_name: str | None = None


class SubscriptionListResponse(BaseModel):
    """Schema für Abonnement-Liste"""
    items: list[SubscriptionResponse]
    total: int
