"""Monatslauf — Protokoll und Sperre der Monatsrechnungen (B5).

Ein Eintrag je Lauf, automatisch (Scheduler, 1. des Folgemonats 06:30) oder
von Hand (Admin, POST /invoices/monthly-proposals/run). Der Teilindex lässt
je Monat höchstens EINEN laufenden Lauf zu, gleich welcher Art: zwei
Prozesse, ein Doppelklick oder Scheduler und Admin gleichzeitig legen damit
keine doppelten Entwürfe an.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from app.database import Base


class BillingRun(Base):
    __tablename__ = "billing_runs"
    __table_args__ = (
        Index(
            "ux_billing_runs_laufend", "monat", unique=True,
            sqlite_where=text("status = 'LAEUFT'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Leistungsmonat JJJJ-MM
    monat: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    # MONAT_AUTO (Scheduler) | MONAT_MANUELL (Admin)
    art: Mapped[str] = mapped_column(String(20), nullable=False)
    # LAEUFT | FERTIG | FEHLER
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="LAEUFT")
    # naive UTC — SQLite speichert ohne Zeitzone, verglichen wird ebenso
    gestartet_am: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    beendet_am: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # Login des Admins; NULL = Scheduler
    ausgeloest_von: Mapped[Optional[str]] = mapped_column(String(100))
    # angelegte Belege, übersprungene Kunden mit Grund, Fehler je Kunde
    ergebnis: Mapped[Optional[dict]] = mapped_column(JSON)
    fehler: Mapped[Optional[str]] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<BillingRun({self.monat}, {self.art}, {self.status})>"
