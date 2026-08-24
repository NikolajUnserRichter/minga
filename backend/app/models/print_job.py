"""Druckauftrag — die Warteschlange zwischen ERP und dem Drucker vor Ort.

Der ERP-Server steht im Rechenzentrum, der Etikettendrucker im Hofnetz. Eine
Verbindung vom Server zum Drucker gibt es damit nicht und wird es auch nicht
geben. Im Normalfall druckt deshalb der Browser selbst — er sieht beides.

Wo das nicht reicht, weil niemand vor dem Bildschirm sitzt, legt das ERP den
Auftrag hier ab und ein kleiner Agent im Hofnetz holt ihn ab. Das fertige PDF
hängt am Auftrag: gedruckt wird damit genau das, was beim Einreihen galt, und
der Agent muss nichts über Chargen, Sorten und Etikettenformate wissen.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Text, LargeBinary
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.types import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PrintJobStatus(str, Enum):
    """Lebenslauf eines Druckauftrags."""
    OFFEN = "OFFEN"          # wartet auf den Agenten
    IN_ARBEIT = "IN_ARBEIT"  # ein Agent hat ihn übernommen
    GEDRUCKT = "GEDRUCKT"    # erledigt
    FEHLER = "FEHLER"        # Papierstau, Drucker aus, falsche Rolle …


class PrintJob(Base):
    """Ein fertig gerendertes Dokument, das auf einen Drucker wartet."""

    __tablename__ = "print_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    titel: Mapped[str] = mapped_column(String(200), nullable=False)
    dateiname: Mapped[str] = mapped_column(String(255), nullable=False)
    # Eingefroren beim Einreihen — spätere Änderungen an der Charge ändern
    # nichts mehr an dem, was aus dem Drucker kommt.
    #
    # deferred: der Agent fragt die Liste im Sekundentakt ab; dabei sollen
    # nicht jedes Mal alle PDFs mit aus der Datenbank gezogen werden. Geladen
    # wird erst beim Zugriff, also genau im /document-Endpunkt.
    dokument: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    groesse_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Etikettenformat (z.B. 'avery-48x17'), damit der Agent die passende
    # Rolle bzw. das passende Papierfach wählen kann.
    format: Mapped[Optional[str]] = mapped_column(String(40))
    # Zielgerät; leer heißt: Standarddrucker des Agenten.
    drucker: Mapped[Optional[str]] = mapped_column(String(100))
    kopien: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    status: Mapped[PrintJobStatus] = mapped_column(
        SQLEnum(PrintJobStatus), default=PrintJobStatus.OFFEN, nullable=False
    )
    fehler: Mapped[Optional[str]] = mapped_column(Text)
    # Zählt hoch, sooft der Auftrag übernommen wurde — ein Auftrag, der immer
    # wieder scheitert, fällt so auf.
    versuche: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Name des Agenten, der ihn geholt hat (frei gewählt, nur zur Diagnose).
    agent: Mapped[Optional[str]] = mapped_column(String(100))

    erstellt_am: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    erstellt_von: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    geholt_am: Mapped[Optional[datetime]] = mapped_column(DateTime)
    erledigt_am: Mapped[Optional[datetime]] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return f"<PrintJob({self.titel!r}, status={self.status.value})>"
