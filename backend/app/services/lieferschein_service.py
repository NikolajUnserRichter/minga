"""Lieferschein anlegen — eine Regel für „Neuer LS“, die Packliste im
Tagesplan und das Ausliefern (Paket 4, B; G31, X07).

Abgerechnet wird über Lieferscheine: Sammel- und Monatslauf nehmen je
Bestellung einen noch nicht abgerechneten Lieferschein
(invoices._abrechenbare_lieferscheine), die Rechnung aus der Bestellung
belegt ihn (InvoiceService.create_invoice_from_order), ein Storno gibt ihn
frei. Eine gelieferte Bestellung ohne Lieferschein fehlte im Monatslauf
still — er meldete sie nur als OHNE_LIEFERSCHEIN. Deshalb legt der Wechsel
auf GELIEFERT einen an, wenn die Bestellung noch keinen hat
(order_status_service.setze_status). Committet nie.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.documents import DeliveryNote, PackingList, PackingListItem
from app.models.enums import DeliveryNoteStatus
from app.models.order import Order
from app.schemas.documents import PackingListItemCreate


def naechste_belegnummer(db: Session, model, number_col, prefix: str, today: date) -> str:
    """Generiert {PREFIX}-YYYYMMDD-NNNN sequenziell (AB, LS, PL)."""
    date_part = today.strftime("%Y%m%d")
    full_prefix = f"{prefix}-{date_part}"
    last = db.execute(
        select(model)
        .where(number_col.like(f"{full_prefix}-%"))
        .order_by(number_col.desc())
        .limit(1)
    ).scalar_one_or_none()
    next_num = (int(getattr(last, number_col.key).split("-")[-1]) + 1) if last else 1
    return f"{full_prefix}-{next_num:04d}"


def lieferschein_anlegen(
    db: Session,
    order: Order,
    *,
    notes: Optional[str] = None,
    packing_items: Optional[list[PackingListItemCreate]] = None,
    total_weight_g: Optional[Decimal] = None,
    total_packages: Optional[int] = None,
    actual_delivery_date: Optional[date] = None,
) -> DeliveryNote:
    """Lieferschein (ENTWURF) samt Packliste anlegen. Ohne packing_items
    1:1 aus den Bestellpositionen (ohne Pfand-Erweiterungen). Prüft weder
    Positionen noch vorhandene Lieferscheine — das tun die Aufrufer.
    Committet nicht."""
    today = date.today()
    ls_number = naechste_belegnummer(
        db, DeliveryNote, DeliveryNote.delivery_note_number, "LS", today
    )
    pl_number = naechste_belegnummer(
        db, PackingList, PackingList.packing_list_number, "PL", today
    )

    note = DeliveryNote(
        order_id=order.id,
        delivery_note_number=ls_number,
        status=DeliveryNoteStatus.ENTWURF,
        notes=notes,
        actual_delivery_date=actual_delivery_date,
    )
    db.add(note)
    db.flush()  # note.id

    packing = PackingList(
        delivery_note_id=note.id,
        packing_list_number=pl_number,
        total_weight_g=total_weight_g,
        total_packages=total_packages,
    )
    db.add(packing)
    db.flush()  # packing.id

    # Items: explizite Liste ODER 1:1 aus Order-Lines
    if packing_items:
        items_to_create = packing_items
    else:
        items_to_create = [
            PackingListItemCreate(
                order_line_id=line.id,
                product_name=line.beschreibung or "Position",
                quantity=line.quantity,
                unit=line.unit,
                batch_number=line.batch_number,
                harvest_id=line.harvest_id,
                sort_order=line.position,
            )
            for line in order.lines
        ]

    for idx, item in enumerate(items_to_create, start=1):
        db.add(PackingListItem(
            packing_list_id=packing.id,
            order_line_id=item.order_line_id,
            sort_order=item.sort_order or idx,
            product_name=item.product_name,
            quantity=item.quantity,
            unit=item.unit,
            batch_number=item.batch_number,
            harvest_id=item.harvest_id,
            is_returnable_container=item.is_returnable_container,
            container_type=item.container_type,
            container_count=item.container_count,
        ))
    db.flush()
    return note


def lieferschein_beim_ausliefern(db: Session, order: Order) -> Optional[DeliveryNote]:
    """Beim Wechsel auf GELIEFERT: Lieferschein anlegen, wenn die Bestellung
    noch keinen hat (z. B. Tagesplan „Ausgeliefert“ ohne Packliste, Abo-
    Lieferung). Status ENTWURF wie jeder neue Lieferschein — quittiert hat der
    Kunde nichts; er trägt den Liefertag der Bestellung. Ein vorhandener
    Lieferschein bleibt der einzige (Gernot liefert nicht in Teilen). Ohne
    Positionen keiner. Committet nicht."""
    vorhanden = db.execute(
        select(DeliveryNote.id).where(DeliveryNote.order_id == order.id).limit(1)
    ).scalar_one_or_none()
    if vorhanden is not None or not order.lines:
        return None
    return lieferschein_anlegen(db, order, actual_delivery_date=order.actual_delivery_date)
