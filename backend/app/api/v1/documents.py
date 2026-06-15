"""Belegkette-API: Auftragsbestätigung (AB), Lieferschein (LS), Verpackungsliste (PL).

Workflow:
    POST /orders/{id}/confirmations        → AB im Status ENTWURF anlegen
    PATCH /confirmations/{id}/send         → an Kunden versendet (immutable)
    GET /confirmations/{id}/pdf            → PDF
    GET /orders/{id}/confirmations         → Liste

    POST /orders/{id}/delivery-notes       → Lieferschein + Packliste anlegen
    PATCH /delivery-notes/{id}/mark-delivered → quittiert; setzt order.actual_delivery_date
    GET /delivery-notes/{id}/pdf
    GET /delivery-notes/{id}/packing-list/pdf
    GET /orders/{id}/delivery-notes
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.api.deps import DBSession
from app.models.order import Order, OrderStatus
from app.models.documents import (
    OrderConfirmation, DeliveryNote, PackingList, PackingListItem,
)
from app.models.enums import ConfirmationStatus, DeliveryNoteStatus
from app.schemas.documents import (
    OrderConfirmationCreate, OrderConfirmationResponse, OrderConfirmationSend,
    DeliveryNoteCreate, DeliveryNoteResponse, DeliveryNoteMarkDelivered,
    PackingListItemCreate,
)
from app.services.pdf_service import PDFService, load_company_settings
from app.services.email_service import send_email, EmailNotConfiguredError

router = APIRouter()


# ==================== Helpers ====================

def _next_document_number(db, model, number_col, prefix: str, today: date) -> str:
    """Generiert {PREFIX}-YYYYMMDD-NNNN sequenziell."""
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


def _load_order_with_lines(db, order_id: UUID) -> Order:
    order = db.execute(
        select(Order)
        .options(joinedload(Order.customer), joinedload(Order.lines))
        .where(Order.id == order_id)
    ).unique().scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")
    return order


# ==================== AUFTRAGSBESTÄTIGUNG ====================

@router.post(
    "/orders/{order_id}/confirmations",
    response_model=OrderConfirmationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_confirmation(order_id: UUID, data: OrderConfirmationCreate, db: DBSession):
    """Neue Auftragsbestätigung im Status ENTWURF."""
    order = _load_order_with_lines(db, order_id)
    if not order.lines:
        raise HTTPException(status_code=400, detail="Bestellung hat keine Positionen — AB nicht möglich")

    today = date.today()
    number = _next_document_number(
        db, OrderConfirmation, OrderConfirmation.confirmation_number, "AB", today
    )
    conf = OrderConfirmation(
        order_id=order.id,
        confirmation_number=number,
        status=ConfirmationStatus.ENTWURF,
        notes=data.notes,
    )
    db.add(conf)
    db.commit()
    db.refresh(conf)
    return conf


@router.get("/orders/{order_id}/confirmations", response_model=list[OrderConfirmationResponse])
def list_confirmations(order_id: UUID, db: DBSession):
    """Alle ABs zu einer Bestellung."""
    confs = db.execute(
        select(OrderConfirmation)
        .where(OrderConfirmation.order_id == order_id)
        .order_by(OrderConfirmation.created_at.desc())
    ).scalars().all()
    return confs


@router.patch("/confirmations/{conf_id}/send", response_model=OrderConfirmationResponse)
def send_confirmation(conf_id: UUID, data: OrderConfirmationSend, db: DBSession):
    """Versendet AB per Email (PDF im Anhang) und markiert sie als VERSENDET.

    Wenn `sent_to_email` leer ist, wird nur der Status gesetzt — z.B. bei
    persönlicher Übergabe."""
    conf = db.execute(
        select(OrderConfirmation)
        .options(joinedload(OrderConfirmation.order).joinedload(Order.customer))
        .where(OrderConfirmation.id == conf_id)
    ).unique().scalar_one_or_none()
    if not conf:
        raise HTTPException(status_code=404, detail="Auftragsbestätigung nicht gefunden")
    if conf.is_locked():
        raise HTTPException(status_code=400, detail="AB ist bereits versendet")

    # Order-Lines explizit laden (vom Mapper nicht eager)
    _load_order_with_lines(db, conf.order_id)

    if data.sent_to_email:
        try:
            pdf = PDFService.generate_confirmation_pdf(conf, settings=load_company_settings(db))
            customer_name = conf.order.customer.name if conf.order and conf.order.customer else "Kunde"
            send_email(
                db=db,
                to=data.sent_to_email,
                subject=f"Auftragsbestätigung {conf.confirmation_number}",
                body=(
                    f"Sehr geehrte Damen und Herren bei {customer_name},\n\n"
                    f"anbei finden Sie die Auftragsbestätigung {conf.confirmation_number}\n"
                    f"zu Ihrer Bestellung {conf.order.order_number}.\n\n"
                    f"Mit freundlichen Grüßen\nIhr Minga-Greens-Team"
                ),
                attachment_bytes=pdf,
                attachment_filename=f"{conf.confirmation_number}.pdf",
            )
        except EmailNotConfiguredError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"E-Mail-Versand fehlgeschlagen: {e}")

    conf.status = ConfirmationStatus.VERSENDET
    conf.sent_at = datetime.now(timezone.utc)
    conf.sent_to_email = data.sent_to_email
    db.commit()
    db.refresh(conf)
    return conf


@router.get("/confirmations/{conf_id}/pdf")
def download_confirmation_pdf(conf_id: UUID, db: DBSession):
    """PDF der AB."""
    conf = db.execute(
        select(OrderConfirmation)
        .options(
            joinedload(OrderConfirmation.order)
            .joinedload(Order.customer)
        )
        .where(OrderConfirmation.id == conf_id)
    ).unique().scalar_one_or_none()
    if not conf:
        raise HTTPException(status_code=404, detail="Auftragsbestätigung nicht gefunden")
    # Lines laden
    _ = _load_order_with_lines(db, conf.order_id)
    pdf = PDFService.generate_confirmation_pdf(conf, settings=load_company_settings(db))
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{conf.confirmation_number}.pdf"'},
    )


# ==================== LIEFERSCHEIN + PACKLISTE ====================

@router.post(
    "/orders/{order_id}/delivery-notes",
    response_model=DeliveryNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_delivery_note(order_id: UUID, data: DeliveryNoteCreate, db: DBSession):
    """Lieferschein + zugehörige Verpackungsliste anlegen.

    Falls `packing_items` leer ist, werden Items 1:1 aus den Order-Lines
    übernommen (ohne Pfand-Container).
    """
    order = _load_order_with_lines(db, order_id)
    if not order.lines:
        raise HTTPException(status_code=400, detail="Bestellung hat keine Positionen")

    today = date.today()
    ls_number = _next_document_number(
        db, DeliveryNote, DeliveryNote.delivery_note_number, "LS", today
    )
    pl_number = _next_document_number(
        db, PackingList, PackingList.packing_list_number, "PL", today
    )

    note = DeliveryNote(
        order_id=order.id,
        delivery_note_number=ls_number,
        status=DeliveryNoteStatus.ENTWURF,
        notes=data.notes,
    )
    db.add(note)
    db.flush()  # note.id

    packing = PackingList(
        delivery_note_id=note.id,
        packing_list_number=pl_number,
        total_weight_g=data.total_weight_g,
        total_packages=data.total_packages,
    )
    db.add(packing)
    db.flush()  # packing.id

    # Items: explizite Liste ODER 1:1 aus Order-Lines
    if data.packing_items:
        items_to_create = data.packing_items
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

    db.commit()
    db.refresh(note)
    return note


@router.get("/orders/{order_id}/delivery-notes", response_model=list[DeliveryNoteResponse])
def list_delivery_notes(order_id: UUID, db: DBSession):
    notes = db.execute(
        select(DeliveryNote)
        .options(joinedload(DeliveryNote.packing_list).joinedload(PackingList.items))
        .where(DeliveryNote.order_id == order_id)
        .order_by(DeliveryNote.created_at.desc())
    ).unique().scalars().all()
    return notes


@router.patch(
    "/delivery-notes/{note_id}/mark-delivered",
    response_model=DeliveryNoteResponse,
)
def mark_delivered(note_id: UUID, data: DeliveryNoteMarkDelivered, db: DBSession):
    """Lieferschein als geliefert markieren. Setzt auch order.actual_delivery_date
    und überführt Order-Status nach GELIEFERT, falls noch in früherem Status."""
    note = db.execute(
        select(DeliveryNote)
        .options(joinedload(DeliveryNote.order))
        .where(DeliveryNote.id == note_id)
    ).unique().scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Lieferschein nicht gefunden")
    if note.is_locked():
        raise HTTPException(status_code=400, detail="Lieferschein ist bereits quittiert")

    note.status = DeliveryNoteStatus.GELIEFERT
    note.delivered_at = datetime.now(timezone.utc)
    note.signed_by = data.signed_by
    note.actual_delivery_date = data.actual_delivery_date or date.today()

    # Order-Sync
    transitioned_to_delivered = False
    if note.order and not note.order.actual_delivery_date:
        note.order.actual_delivery_date = note.actual_delivery_date
        if note.order.status in (OrderStatus.ENTWURF, OrderStatus.BESTAETIGT, OrderStatus.IN_PRODUKTION):
            note.order.status = OrderStatus.GELIEFERT
            transitioned_to_delivered = True

    # Inventory-Deduction IN DERSELBEN TRANSACTION wie Status-Change.
    # Wenn Abzug crasht → kompletter Rollback, Quittierung wird nicht persistiert
    # und der User kann erneut versuchen, ohne dass die Order/LS-State inkonsistent
    # mit dem Inventory wird.
    if transitioned_to_delivered and note.order:
        from app.services.order_fulfillment_service import deduct_inventory_for_order
        order_with_lines = _load_order_with_lines(db, note.order_id)
        try:
            deduct_inventory_for_order(db, order_with_lines, commit=False)
        except Exception as e:
            db.rollback()
            import logging; logging.getLogger(__name__).exception(
                "Inventory-Deduction nach LS-Quittierung fehlgeschlagen: %s", e
            )
            raise HTTPException(
                status_code=500,
                detail=f"Quittierung abgebrochen — Inventory-Abzug fehlgeschlagen: {e}",
            )

    db.commit()
    db.refresh(note)
    return note


@router.get("/delivery-notes/{note_id}/pdf")
def download_delivery_note_pdf(note_id: UUID, db: DBSession):
    note = db.execute(
        select(DeliveryNote)
        .options(
            joinedload(DeliveryNote.order).joinedload(Order.customer),
            joinedload(DeliveryNote.order).joinedload(Order.lines),
        )
        .where(DeliveryNote.id == note_id)
    ).unique().scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Lieferschein nicht gefunden")
    pdf = PDFService.generate_delivery_note_pdf(note, settings=load_company_settings(db))
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{note.delivery_note_number}.pdf"'},
    )


@router.get("/delivery-notes/{note_id}/packing-list/pdf")
def download_packing_list_pdf(note_id: UUID, db: DBSession):
    note = db.execute(
        select(DeliveryNote)
        .options(
            joinedload(DeliveryNote.order).joinedload(Order.customer),
            joinedload(DeliveryNote.packing_list).joinedload(PackingList.items),
        )
        .where(DeliveryNote.id == note_id)
    ).unique().scalar_one_or_none()
    if not note or not note.packing_list:
        raise HTTPException(status_code=404, detail="Verpackungsliste nicht gefunden")
    pdf = PDFService.generate_packing_list_pdf(note.packing_list, settings=load_company_settings(db))
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{note.packing_list.packing_list_number}.pdf"'},
    )
