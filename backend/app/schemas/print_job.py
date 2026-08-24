"""Pydantic-Schemas für die Druck-Warteschlange."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.print_job import PrintJobStatus


class PrintJobResponse(BaseModel):
    """Ein Druckauftrag ohne sein Dokument.

    Die PDF-Bytes bleiben draußen — die holt sich der Agent einzeln unter
    /document ab, statt sie in jeder Liste mitzuschleppen. `groesse_bytes`
    verrät, dass überhaupt eins hinterlegt ist.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    titel: str
    dateiname: str
    groesse_bytes: int
    format: Optional[str] = None
    drucker: Optional[str] = None
    kopien: int
    status: PrintJobStatus
    fehler: Optional[str] = None
    versuche: int
    agent: Optional[str] = None
    erstellt_am: datetime
    erledigt_am: Optional[datetime] = None


class PrintJobClaim(BaseModel):
    """Der Agent meldet beim Übernehmen, wer er ist."""
    agent: Optional[str] = Field(None, max_length=100, description="Name des Agenten, nur zur Diagnose")


class PrintJobFailure(BaseModel):
    """Rückmeldung, wenn der Druck schiefgegangen ist."""
    fehler: str = Field(..., min_length=1, max_length=2000, description="Was der Drucker gemeldet hat")
