"""Pydantic-Schemas für Lieferanten (Saatgut, Substrat, Verpackung, …)."""
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SupplierBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    telefon: Optional[str] = Field(None, max_length=50)
    adresse: Optional[str] = None
    ust_id: Optional[str] = Field(None, max_length=20)
    notizen: Optional[str] = None
    # SAATGUT | SUBSTRAT | VERPACKUNG | ARBEITSMATERIAL | SONSTIGES
    product_group: Optional[str] = Field(None, max_length=30, description="Produktgruppe")
    is_organic: bool = Field(default=False, description="BIO-zertifiziert?")
    bio_certificate_url: Optional[str] = Field(None, max_length=500, description="URL zum BIO-Zertifikat")
    bio_certificate_valid_until: Optional[date] = Field(None, description="Zertifikat gültig bis")
    bio_kontrollstelle: Optional[str] = Field(None, max_length=100, description="Kontrollstelle (z.B. DE-ÖKO-006)")


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    telefon: Optional[str] = None
    adresse: Optional[str] = None
    ust_id: Optional[str] = None
    notizen: Optional[str] = None
    product_group: Optional[str] = Field(None, max_length=30)
    is_organic: Optional[bool] = None
    bio_certificate_url: Optional[str] = Field(None, max_length=500)
    bio_certificate_valid_until: Optional[date] = None
    bio_kontrollstelle: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class SupplierResponse(SupplierBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseModel):
    items: list[SupplierResponse]
    total: int
