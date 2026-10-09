"""Belegstatus je Bestellung (Paket 4, Abschnitt C; Gernot 08.10.2026, B2).

Eine Zeile je nicht stornierter Bestellung: Lieferschein erstellt, Rechnung
erstellt, Rechnung versendet, bezahlt. Schreibt nichts.

Regeln (dieselben Wege wie Sammel- und Monatslauf):
- Liefertag = tatsächliches, sonst Wunschlieferdatum der Bestellung.
- Rechnung der Bestellung = nicht stornierte Rechnung vom Typ RECHNUNG über
  Invoice.order_id oder über einen Lieferschein der Bestellung
  (wie InvoiceService.aktive_rechnung_zur_bestellung); eine
  festgeschriebene geht dem Entwurf vor.
- Versendet = Invoice.sent_at (erster erfolgreicher Mailversand, Paket 3
  Q2), sonst der erste Eintrag der Rechnung im Versandprotokoll
  (document_dispatches, auch „ohne Mail markiert“). Rechnungen von vor dem
  Protokoll haben nur sent_at.
- Geliefert = Status GELIEFERT oder FAKTURIERT, ein quittierter
  Lieferschein, oder BESTAETIGT/IN_PRODUKTION mit Liefertag vor heute
  (gelieferte Bestellungen bleiben oft auf BESTAETIGT stehen, Spec A1).
- FAKTURIERT ohne Rechnung im System = extern abgerechnet (Altbestand über
  DATEV, Spec-Nachtrag 08.10.2026) — keine Lücke. Hat die Bestellung eine
  stornierte Rechnung (Invoice.order_id), ist sie nie extern: Der Storno
  setzt FAKTURIERT nicht zurück, ohne Neuausstellung fehlt die Rechnung.
- Fällig ist die Rechnung beim Einzelkunden ab dem Liefertag, beim
  Monatskunden ab dem 1. des Folgemonats (Monatslauf, B5).
- Unvollständig = geliefert, nicht extern abgerechnet, fällig und: ohne
  Rechnung (OHNE_RECHNUNG), nur Entwurf (RECHNUNG_ENTWURF) oder nicht
  versendet (NICHT_VERSENDET).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.customer import InvoiceMode
from app.models.documents import DeliveryNote, DocumentDispatch
from app.models.enums import DeliveryNoteStatus, OrderStatus
from app.models.invoice import Invoice, InvoiceStatus, InvoiceType
from app.models.order import Order

OHNE_RECHNUNG = "OHNE_RECHNUNG"
RECHNUNG_ENTWURF = "RECHNUNG_ENTWURF"
NICHT_VERSENDET = "NICHT_VERSENDET"

_GELIEFERT = (OrderStatus.GELIEFERT, OrderStatus.FAKTURIERT)
_UNTERWEGS = (OrderStatus.BESTAETIGT, OrderStatus.IN_PRODUKTION)


def rechnung_faellig_ab(liefertag: date, monatlich: bool) -> date:
    """Einzelkunde: der Liefertag. Monatskunde: der 1. des Folgemonats."""
    if not monatlich:
        return liefertag
    return (liefertag.replace(day=1) + timedelta(days=32)).replace(day=1)


def belegstatus(
    db: Session,
    *,
    heute: date,
    von: Optional[date] = None,
    bis: Optional[date] = None,
    kunde_id: Optional[UUID] = None,
) -> list[dict]:
    """Alle Zeilen im Zeitraum (Liefertag) und für den Kunden, neueste zuerst.

    Fünf Abfragen, keine je Bestellung; die Auswahl der Bestellungen geht als
    Unterabfrage in die Abfragen nach Lieferscheinen und Rechnungen.
    """
    liefertag = func.coalesce(Order.actual_delivery_date, Order.requested_delivery_date)
    bedingungen = [Order.status != OrderStatus.STORNIERT]
    if von:
        bedingungen.append(liefertag >= von)
    if bis:
        bedingungen.append(liefertag <= bis)
    if kunde_id:
        bedingungen.append(Order.customer_id == kunde_id)
    auswahl = select(Order.id).where(*bedingungen)

    auftraege = db.execute(
        select(Order).options(joinedload(Order.customer)).where(*bedingungen)
        .order_by(liefertag.desc(), Order.order_number.desc())
    ).scalars().all()

    lieferscheine: dict[UUID, list[DeliveryNote]] = {}
    for ls in db.execute(
        select(DeliveryNote).where(DeliveryNote.order_id.in_(auswahl))
        .order_by(DeliveryNote.delivery_note_number)
    ).scalars():
        lieferscheine.setdefault(ls.order_id, []).append(ls)

    aktiv = (Invoice.invoice_type == InvoiceType.RECHNUNG, Invoice.status != InvoiceStatus.STORNIERT)
    rechnungen: dict[UUID, dict[UUID, Invoice]] = {}
    # Bestellungen mit stornierter Rechnung sind nie „extern abgerechnet“: Der
    # Storno setzt FAKTURIERT nicht zurück. Eine stornierte Sammel- oder
    # Monatsrechnung hängt danach an keinem Lieferschein mehr (R1.6) und
    # bleibt hier unsichtbar — wie im Sammellauf.
    mit_storno: set[UUID] = set()
    for inv in db.execute(
        select(Invoice).where(Invoice.order_id.in_(auswahl), Invoice.invoice_type == InvoiceType.RECHNUNG)
    ).scalars():
        if inv.status == InvoiceStatus.STORNIERT:
            mit_storno.add(inv.order_id)
        else:
            rechnungen.setdefault(inv.order_id, {})[inv.id] = inv
    for order_id, inv in db.execute(
        select(DeliveryNote.order_id, Invoice)
        .join(Invoice, DeliveryNote.invoice_id == Invoice.id)
        .where(DeliveryNote.order_id.in_(auswahl), *aktiv)
    ).all():
        rechnungen.setdefault(order_id, {})[inv.id] = inv

    rechnung_ids = {inv_id for je_auftrag in rechnungen.values() for inv_id in je_auftrag}
    protokoll: dict[UUID, datetime] = dict(db.execute(
        select(DocumentDispatch.invoice_id, func.min(DocumentDispatch.sent_at))
        .where(DocumentDispatch.invoice_id.in_(rechnung_ids))
        .group_by(DocumentDispatch.invoice_id)
    ).all()) if rechnung_ids else {}

    zeilen = []
    for o in auftraege:
        tag = o.actual_delivery_date or o.requested_delivery_date
        kunde = o.customer
        monatlich = kunde is not None and kunde.invoice_mode == InvoiceMode.MONATLICH
        notes = lieferscheine.get(o.id, [])
        # festgeschrieben vor Entwurf, dann nach Nummer
        kandidaten = sorted(
            rechnungen.get(o.id, {}).values(),
            key=lambda r: (r.status == InvoiceStatus.ENTWURF, r.invoice_number),
        )
        rechnung = kandidaten[0] if kandidaten else None
        extern = rechnung is None and o.status == OrderStatus.FAKTURIERT and o.id not in mit_storno
        geliefert = (
            o.status in _GELIEFERT
            or any(n.status == DeliveryNoteStatus.GELIEFERT for n in notes)
            or (o.status in _UNTERWEGS and tag < heute)
        )
        faellig_ab = rechnung_faellig_ab(tag, monatlich)
        versendet_am = None if rechnung is None else (rechnung.sent_at or protokoll.get(rechnung.id))

        luecken: list[str] = []
        if geliefert and not extern and heute >= faellig_ab:
            if rechnung is None:
                luecken.append(OHNE_RECHNUNG)
            elif rechnung.status == InvoiceStatus.ENTWURF:
                luecken.append(RECHNUNG_ENTWURF)
            elif versendet_am is None:
                luecken.append(NICHT_VERSENDET)

        zeilen.append({
            "order_id": o.id,
            "order_number": o.order_number,
            "order_status": o.status.value,
            "customer_id": o.customer_id,
            "customer_name": kunde.name if kunde else "",
            "abrechnung": (InvoiceMode.MONATLICH if monatlich else InvoiceMode.EINZELN).value,
            "liefertag": tag,
            "geliefert": geliefert,
            "lieferscheine": [
                {"id": n.id, "nummer": n.delivery_note_number, "status": n.status.value} for n in notes
            ],
            "rechnung": None if rechnung is None else {
                "id": rechnung.id,
                "nummer": rechnung.invoice_number,
                "status": rechnung.status.value,
                "sammelrechnung": rechnung.order_id != o.id,
                "versendet_am": versendet_am,
                "bezahlt": rechnung.status == InvoiceStatus.BEZAHLT,
            },
            "extern_abgerechnet": extern,
            "rechnung_faellig_ab": faellig_ab,
            "luecken": luecken,
            "unvollstaendig": bool(luecken),
        })
    return zeilen
