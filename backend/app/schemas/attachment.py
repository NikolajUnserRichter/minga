"""Pydantic-Schemas für Attachments."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: str
    entity_id: UUID
    filename: str
    content_type: Optional[str]
    size_bytes: int
    certificate_type: Optional[str] = None
    bio_kontrollstelle: Optional[str] = None
    valid_until: Optional[date] = None
    notes: Optional[str] = None
    uploaded_at: datetime
    uploaded_by: Optional[UUID] = None


class AttachmentUpdate(BaseModel):
    certificate_type: Optional[str] = Field(None, max_length=40)
    bio_kontrollstelle: Optional[str] = Field(None, max_length=100)
    valid_until: Optional[date] = None
    notes: Optional[str] = None
