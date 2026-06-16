"""Pydantic-Schemas für Document-Templates."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document_template import DocumentType


class DocumentTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_type: DocumentType
    logo_attachment_id: Optional[UUID]
    texts: Optional[dict[str, Any]]
    sections: Optional[list[dict[str, Any]]]
    columns: Optional[list[dict[str, Any]]]
    primary_color: Optional[str]
    accent_color: Optional[str]
    created_at: datetime
    updated_at: datetime

    # Expandierte Felder
    logo_url: Optional[str] = None
    placeholders: Optional[list[str]] = None


class DocumentTemplateUpdate(BaseModel):
    texts: Optional[dict[str, Any]] = None
    sections: Optional[list[dict[str, Any]]] = None
    columns: Optional[list[dict[str, Any]]] = None
    primary_color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    accent_color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    logo_attachment_id: Optional[UUID] = None
