"""
Dienstplan: StaffShift — geplante Arbeitsschichten der Mitarbeiter.

Bewusst leichtgewichtig: Mitarbeiter sind Freitext-Namen (kein eigenes
Personal-Modul), eine Schicht ist Name + Tag + Zeitfenster + Aufgabe.
"""
import uuid
from datetime import datetime, date, timezone
from typing import Optional

from sqlalchemy import String, Date, DateTime, Text, Boolean
from sqlalchemy.types import Uuid

from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StaffShift(Base):
    __tablename__ = "staff_shifts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    employee_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    datum: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Zeitfenster als "HH:MM" (einfach editierbar, keine TZ-Fallen)
    start_time: Mapped[Optional[str]] = mapped_column(String(5))
    end_time: Mapped[Optional[str]] = mapped_column(String(5))

    # Aufgabe/Bereich, z.B. "Aussaat", "Ernte + Verpacken", "Auslieferung"
    aufgabe: Mapped[Optional[str]] = mapped_column(String(200))
    notizen: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        return f"<StaffShift({self.employee_name}, {self.datum})>"


class StaffTask(Base):
    """Aufgabe ohne Produktionsbezug — Kisten spülen, Hanfmatten auffüllen, Müll rausstellen.

    Bewusst pro Termin eine Zeile: Wiederholungen werden beim Anlegen
    ausmaterialisiert (`serie_id` klammert sie). So bleibt die Tagesabfrage
    ein simpler Datumsfilter und jeder Termin lässt sich einzeln abhaken.
    """

    __tablename__ = "staff_tasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    titel: Mapped[str] = mapped_column(String(200), nullable=False)
    beschreibung: Mapped[Optional[str]] = mapped_column(Text)

    datum: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Zuordnung ist optional: manche Aufgaben hängen am Tag, nicht an einer Person
    employee_name: Mapped[Optional[str]] = mapped_column(String(200), index=True)

    erledigt: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    erledigt_am: Mapped[Optional[datetime]] = mapped_column(DateTime)

    serie_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        return f"<StaffTask({self.titel}, {self.datum})>"
