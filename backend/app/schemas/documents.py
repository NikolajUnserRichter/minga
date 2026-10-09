"""Pydantic-Schemas für die Belegkette."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.email_adressen import MAX_EMPFAENGER, pruefe_empfaenger
from app.models.enums import (
    ConfirmationStatus, DeliveryNoteStatus, DispatchDocType, DispatchStatus,
)


# ==================== VERSANDPROTOKOLL (Paket 3, Q2) ====================

class DocumentDispatchResponse(BaseModel):
    """Eine Zeile des Versandprotokolls."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    doc_type: DispatchDocType
    document_number: str
    status: DispatchStatus
    to_addrs: list[str] = []
    cc_addrs: list[str] = []
    refused: Optional[dict[str, str]] = None
    subject: Optional[str] = None
    attachment_filename: Optional[str] = None
    attachment_sha256: Optional[str] = None
    message_id: Optional[str] = None
    sent_at: datetime
    sent_by_name: Optional[str] = None

    @field_validator("sent_at")
    @classmethod
    def _als_utc(cls, v: datetime) -> datetime:
        # SQLite liefert naive Zeitstempel; gespeichert wird UTC. Mit
        # Zeitzone ausgeben, sonst liest der Browser sie als Ortszeit.
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v


# ==================== AUFTRAGSBESTÄTIGUNG ====================

class OrderConfirmationCreate(BaseModel):
    notes: Optional[str] = None


class BelegVersandRequest(BaseModel):
    """Versand eines Belegs per E-Mail — EINE Mail, alle Adressen im An-Feld.

    - `to`: Empfänger für genau diesen Versand (Abweichung vom Kundenstamm).
    - `use_customer_recipients: true`: die beim Kunden hinterlegte Liste der
      Belegart, ersatzweise die Haupt-E-Mail.
    - Weder noch (leerer Body `{}`): KEINE Mail — AB bzw. Lieferschein werden
      nur als versendet bzw. ausgestellt markiert. Mit dieser Bedeutung schickt
      das bisherige Frontend `{}`; ein leerer Body geht nie an die Kundenliste.
    """
    to: Optional[list[str]] = Field(None, description="Empfänger (An)")
    cc: list[str] = Field(default_factory=list, description="Kopie (Cc), optional")
    use_customer_recipients: bool = Field(
        False, description="Hinterlegte Empfänger der Belegart verwenden"
    )

    @field_validator("to", mode="before")
    @classmethod
    def _to_pruefen(cls, v):
        return pruefe_empfaenger(v, feld="An") if v is not None else None

    @field_validator("cc", mode="before")
    @classmethod
    def _cc_pruefen(cls, v):
        return pruefe_empfaenger(v, feld="Cc")

    @model_validator(mode="after")
    def _zusammen_pruefen(self):
        an = self.to or []
        # Wer im An-Feld steht, bekommt keine zweite Kopie
        self.cc = [a for a in self.cc if a not in an]
        if self.cc and not an and not self.use_customer_recipients:
            raise ValueError("Cc nur zusammen mit Empfängern im An-Feld")
        if len(an) + len(self.cc) > MAX_EMPFAENGER:
            raise ValueError(f"Höchstens {MAX_EMPFAENGER} Adressen je Mail (An und Cc zusammen)")
        return self


class OrderConfirmationSend(BelegVersandRequest):
    """Wie BelegVersandRequest; `sent_to_email` (ein Empfänger) bleibt für
    ältere Aufrufer erhalten und wird wie `to=[…]` behandelt."""
    sent_to_email: Optional[str] = Field(
        None, description="Veraltet: ein Empfänger; neu ist `to`"
    )

    @model_validator(mode="before")
    @classmethod
    def _altes_feld_uebernehmen(cls, daten):
        # Vor der Feldprüfung: sent_to_email wird zu to=[…] und läuft durch
        # dieselbe Adressprüfung.
        if isinstance(daten, dict) and daten.get("sent_to_email") and not daten.get("to"):
            daten = {**daten, "to": [daten["sent_to_email"]]}
        return daten


class OrderConfirmationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    confirmation_number: str
    status: ConfirmationStatus
    issued_at: datetime
    sent_at: Optional[datetime]
    sent_to_email: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    dispatches: list[DocumentDispatchResponse] = []


# ==================== LIEFERSCHEIN ====================

class PackingListItemCreate(BaseModel):
    order_line_id: Optional[UUID] = None
    product_name: str
    quantity: Decimal = Field(..., gt=0)
    unit: str
    batch_number: Optional[str] = None
    harvest_id: Optional[UUID] = None
    is_returnable_container: bool = False
    container_type: Optional[str] = None
    container_count: Optional[int] = Field(None, ge=1)
    sort_order: int = 0


class PackingListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_line_id: Optional[UUID]
    sort_order: int
    product_name: str
    quantity: Decimal
    unit: str
    batch_number: Optional[str]
    harvest_id: Optional[UUID]
    is_returnable_container: bool
    container_type: Optional[str]
    container_count: Optional[int]


class PackingListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    delivery_note_id: UUID
    packing_list_number: str
    total_weight_g: Optional[Decimal]
    total_packages: Optional[int]
    notes: Optional[str]
    items: list[PackingListItemResponse] = []
    created_at: datetime
    updated_at: datetime


class DeliveryNoteCreate(BaseModel):
    """Anlage eines Lieferscheins.

    Falls keine packing_items angegeben werden, werden automatisch aus
    den Order-Lines übernommen (1:1, ohne Pfand-Erweiterungen)."""
    notes: Optional[str] = None
    packing_items: Optional[list[PackingListItemCreate]] = None
    total_weight_g: Optional[Decimal] = None
    total_packages: Optional[int] = None


class DeliveryNoteMarkDelivered(BaseModel):
    signed_by: Optional[str] = None
    actual_delivery_date: Optional[date] = None


class DeliveryNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    delivery_note_number: str
    status: DeliveryNoteStatus
    issued_at: datetime
    delivered_at: Optional[datetime]
    signed_by: Optional[str]
    actual_delivery_date: Optional[date]
    notes: Optional[str]
    packing_list: Optional[PackingListResponse] = None
    created_at: datetime
    updated_at: datetime
    dispatches: list[DocumentDispatchResponse] = []
