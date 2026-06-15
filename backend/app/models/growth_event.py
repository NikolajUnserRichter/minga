"""Production-Timeline-Events pro Wachstumscharge.

Vollständige Audit-Trail aller Milestones (Einweichen, Aussaat-Start/Ende,
Umsetzen in Keimraum, Wachstumsraum, Kühlung, Packaging Start/Ende).
Jeder Event hat Typ, Zeitstempel, optional Mitarbeiter-Name (Snapshot)
und freie Notizen.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.types import Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GrowthEventType(str, Enum):
    SOAKING_STARTED         = "SOAKING_STARTED"
    SOAKING_COMPLETED       = "SOAKING_COMPLETED"
    SOWING_STARTED          = "SOWING_STARTED"
    SOWING_COMPLETED        = "SOWING_COMPLETED"
    MOVED_TO_GERMINATION    = "MOVED_TO_GERMINATION"
    REMOVED_FROM_GERMINATION = "REMOVED_FROM_GERMINATION"
    MOVED_TO_GROW_ROOM      = "MOVED_TO_GROW_ROOM"
    MOVED_TO_COOLING        = "MOVED_TO_COOLING"
    PACKAGING_STARTED       = "PACKAGING_STARTED"
    PACKAGING_COMPLETED     = "PACKAGING_COMPLETED"
    NOTE                    = "NOTE"  # freie Notiz/Sonstiges


GROWTH_EVENT_LABELS: dict[str, str] = {
    "SOAKING_STARTED":          "Einweichen gestartet",
    "SOAKING_COMPLETED":        "Einweichen beendet",
    "SOWING_STARTED":           "Aussaat gestartet",
    "SOWING_COMPLETED":         "Aussaat abgeschlossen",
    "MOVED_TO_GERMINATION":     "In Keimraum gebracht",
    "REMOVED_FROM_GERMINATION": "Aus Keimraum geholt",
    "MOVED_TO_GROW_ROOM":       "In Wachstumsraum",
    "MOVED_TO_COOLING":         "In Kühlung/Lager",
    "PACKAGING_STARTED":        "Verpackung gestartet",
    "PACKAGING_COMPLETED":      "Verpackung abgeschlossen",
    "NOTE":                     "Notiz",
}


class GrowthBatchEvent(Base):
    """Single timeline event for a grow batch."""
    __tablename__ = "growth_batch_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    grow_batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("grow_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[GrowthEventType] = mapped_column(
        SQLEnum(GrowthEventType), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    employee_name: Mapped[Optional[str]] = mapped_column(String(200))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    extra: Mapped[Optional[dict]] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    grow_batch = relationship("GrowBatch", backref="timeline_events")
