"""Attachment-Model — polymorphe Anhänge an Lieferant/Produkt/Erntecharge.

Die Datei selbst liegt im Filesystem (oder später S3); hier wird nur Metadaten
und der `storage_key` persistiert. Die Auflösung übernimmt StorageService.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import String, Integer, Date, DateTime, Text
from sqlalchemy.types import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# Erlaubte entity_types
ATTACHMENT_ENTITY_TYPES = ("supplier", "product", "harvest", "seed_inventory")

# Erlaubte certificate_types
CERTIFICATE_TYPES = (
    "BIO",          # EU-BIO-Zertifikat
    "ANALYSE",      # Labor-Analyse
    "DATENBLATT",   # Produkt-Datenblatt / Spezifikation
    "SONSTIGES",
)


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)

    certificate_type: Mapped[Optional[str]] = mapped_column(String(40))
    bio_kontrollstelle: Mapped[Optional[str]] = mapped_column(String(100))
    valid_until: Mapped[Optional[date]] = mapped_column(Date)

    notes: Mapped[Optional[str]] = mapped_column(Text)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
