"""Import-Lauf — die Klammer um einen Datei-Import.

Jeder Commit eines Imports bekommt einen Lauf. Darüber ist die Herkunft
importierter Datensätze nachvollziehbar (Kennzeichnung im Drilldown der
Warenfluss-Reports) und ein misslungener Import in einem Schritt rückrollbar,
solange keine Folgebelege an den importierten Datensätzen hängen.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Integer, DateTime
from sqlalchemy.types import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ImportRun(Base):
    __tablename__ = "import_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # Was importiert wurde (z.B. 'grow_batches') und woher
    entity: Mapped[str] = mapped_column(String(50), nullable=False)
    filename: Mapped[Optional[str]] = mapped_column(String(255))

    # ABGESCHLOSSEN | ZURUECKGEROLLT
    status: Mapped[str] = mapped_column(String(20), default="ABGESCHLOSSEN", nullable=False)

    rows_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    movements_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(100))

    def __repr__(self) -> str:
        return f"<ImportRun({self.entity}, {self.status}, +{self.rows_created})>"
