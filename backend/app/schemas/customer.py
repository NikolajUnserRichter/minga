from typing import Optional
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
    email: Optional[EmailStr] = Field(None, description="E-Mail-Adresse")
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

    # DATEV
    datev_account: Optional[str] = Field(None, max_length=10, description="DATEV-Kontonummer")

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

    # DATEV
    datev_account: Optional[str] = None

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
    datev_account: Optional[str]
    notizen: Optional[str]
    aktiv: bool
    created_at: datetime
    updated_at: datetime

    # Expandierte Felder
    price_list_name: Optional[str] = None

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


class SubscriptionCreate(SubscriptionBase):
    """Schema zum Erstellen eines Abonnements"""
    kunde_id: UUID = Field(..., description="Kunden-ID")
    seed_id: UUID = Field(..., description="Produkt-ID")


class SubscriptionUpdate(BaseModel):
    """Schema zum Aktualisieren eines Abonnements"""
    menge: Optional[Decimal] = Field(None, gt=0)
    einheit: Optional[str] = None
    intervall: Optional[SubscriptionInterval] = None
    liefertage: Optional[list[int]] = None
    gueltig_bis: Optional[date] = None
    aktiv: Optional[bool] = None


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
    kunde_name: Optional[str] = None
    seed_name: Optional[str] = None


class SubscriptionListResponse(BaseModel):
    """Schema für Abonnement-Liste"""
    items: list[SubscriptionResponse]
    total: int
