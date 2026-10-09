"""Belegstatus je Bestellung (Paket 4, Abschnitt C; Gernot 08.10.2026, B2)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class BelegstatusLieferschein(BaseModel):
    id: UUID
    nummer: str
    status: str  # ENTWURF | AUSGESTELLT | GELIEFERT


class BelegstatusRechnung(BaseModel):
    id: UUID
    nummer: str  # Entwurf: Platzhalter ENTWURF-…, die Oberfläche zeigt „Entwurf“
    status: str  # InvoiceStatus
    sammelrechnung: bool  # über einen Lieferschein zugeordnet (Sammel-/Monatsrechnung)
    versendet_am: Optional[datetime] = None
    bezahlt: bool


class BelegstatusZeile(BaseModel):
    order_id: UUID
    order_number: str
    order_status: str
    customer_id: UUID
    customer_name: str
    abrechnung: str  # EINZELN | MONATLICH (Customer.invoice_mode)
    liefertag: date
    geliefert: bool
    lieferscheine: list[BelegstatusLieferschein]
    rechnung: Optional[BelegstatusRechnung] = None
    extern_abgerechnet: bool
    rechnung_faellig_ab: date
    luecken: list[str]  # OHNE_RECHNUNG | RECHNUNG_ENTWURF | NICHT_VERSENDET
    unvollstaendig: bool


class BelegstatusListe(BaseModel):
    items: list[BelegstatusZeile]
    total: int  # Zeilen nach allen Filtern (auch nur_unvollstaendig)
    unvollstaendig: int  # unvollständige Zeilen in Zeitraum und Kunde
    heute: date  # Stichtag (Berlin)
