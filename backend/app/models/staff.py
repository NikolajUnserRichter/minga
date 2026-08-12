"""
Dienstplan: StaffShift — geplante Arbeitsschichten der Mitarbeiter.

Bewusst leichtgewichtig: Mitarbeiter sind Freitext-Namen (kein eigenes
Personal-Modul), eine Schicht ist Name + Tag + Zeitfenster + Aufgabe.
"""
import uuid
from datetime import datetime, date, timezone
from typing import Optional

from sqlalchemy import String, Date, DateTime, Text
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
