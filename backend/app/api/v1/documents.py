"""Belegkette-API: Auftragsbestätigung (AB), Lieferschein (LS), Verpackungsliste (PL).

Workflow:
    POST /orders/{id}/confirmations        → AB im Status ENTWURF anlegen
    PATCH /confirmations/{id}/send         → an Kunden versendet (immutable)
    GET /confirmations/{id}/pdf            → PDF
    GET /orders/{id}/confirmations         → Liste

    POST /orders/{id}/delivery-notes       → Lieferschein + Packliste anlegen
    PATCH /delivery-notes/{id}/mark-delivered → quittiert; setzt order.actual_delivery_date
    POST /delivery-notes/{id}/send         → per E-Mail (eine Mail an alle), Protokoll
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

from app.api.deps import DBSession, CurrentUser
from app.models.order import Order, OrderStatus
from app.models.documents import (
    OrderConfirmation, DeliveryNote, PackingList,
)
from app.services.beleg_dateiname import beleg_dateiname, bestellkunde, content_disposition
from app.models.enums import ConfirmationStatus, DeliveryNoteStatus, DispatchDocType
from app.schemas.documents import (
    OrderConfirmationCreate, OrderConfirmationResponse, OrderConfirmationSend,
    DeliveryNoteCreate, DeliveryNoteResponse, DeliveryNoteMarkDelivered,
    BelegVersandRequest,
)
from app.services.pdf_service import PDFService, load_company_settings
from app.services.lieferschein_service import lieferschein_anlegen, naechste_belegnummer
from app.services.email_service import EmailNotConfiguredError
from app.services.belegversand import (
    empfaenger_fuer_versand, erster_nachweis, firmenzusatz, gruss,
    markiere_ohne_mail, pdf_pruefsumme, versende_beleg,
)
from app.services.order_status_service import (
    BestandsbuchungFehler, StatuswechselFehler, heute_berlin, setze_status, trage_lieferdatum_nach,
)

router = APIRouter()


# ==================== Helpers ====================

# {PREFIX}-YYYYMMDD-NNNN: eine Nummernregel für AB, LS und PL (Paket 4, B)
_next_document_number = naechste_belegnummer


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
def send_confirmation(conf_id: UUID, data: OrderConfirmationSend, db: DBSession, user: CurrentUser):
    """AB per E-Mail versenden (eine Mail, alle Empfänger im An-Feld) oder nur
    als versendet markieren.

    - `to` bzw. das ältere `sent_to_email`, oder `use_customer_recipients`
      (AB-Empfänger des Kunden, sonst Haupt-E-Mail): Mail mit PDF.
    - Leerer Body: keine Mail, nur Status VERSENDET (persönliche Übergabe).
    - Eine versendete AB darf erneut per Mail hinaus (etwa an eine vergessene
      Adresse), aber nur mit unverändertem PDF: Das PDF entsteht bei jedem
      Abruf aus den aktuellen Bestellpositionen, und unter derselben
      AB-Nummer darf kein anderer Inhalt hinausgehen.
    Jeder Versand und jede Markierung steht im Versandprotokoll.
    """
    conf = db.execute(
        select(OrderConfirmation)
        .options(joinedload(OrderConfirmation.order).joinedload(Order.customer))
        .where(OrderConfirmation.id == conf_id)
    ).unique().scalar_one_or_none()
    if not conf:
        raise HTTPException(status_code=404, detail="Auftragsbestätigung nicht gefunden")

    # Order-Lines explizit laden (vom Mapper nicht eager)
    order = _load_order_with_lines(db, conf.order_id)
    customer = order.customer

    try:
        an, cc = empfaenger_fuer_versand(
            customer, DispatchDocType.AB,
            to=data.to, cc=data.cc, use_customer_recipients=data.use_customer_recipients,
        )
    except ValueError as e:  # auch KeinEmpfaenger und die Obergrenze An + Cc
        raise HTTPException(status_code=400, detail=str(e))

    if not an and conf.is_locked():
        raise HTTPException(status_code=400, detail="AB ist bereits versendet")

    pdf = PDFService.generate_confirmation_pdf(conf, settings=load_company_settings(db), db=db)

    if not an:
        markiere_ohne_mail(
            db, doc_type=DispatchDocType.AB, document_number=conf.confirmation_number,
            pdf=pdf, user=user, customer_id=order.customer_id, order_id=order.id,
            confirmation_id=conf.id, kunde=bestellkunde(order),
        )
        conf.status = ConfirmationStatus.VERSENDET
        db.commit()
        db.refresh(conf)
        return conf

    if conf.is_locked():
        nachweis = erster_nachweis(conf.dispatches)
        if nachweis is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Für AB {conf.confirmation_number} gibt es keinen Versandnachweis mit "
                    f"Prüfsumme (vor der Umstellung versendet). Bitte eine neue AB anlegen."
                ),
            )
        if nachweis.attachment_sha256 != pdf_pruefsumme(pdf):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Bestellung oder Belegvorlage wurden seit dem ersten Versand von AB "
                    f"{conf.confirmation_number} geändert. Bitte eine neue AB anlegen."
                ),
            )

    customer_name = customer.name if customer else "Kunde"
    try:
        eintrag = versende_beleg(
            db,
            doc_type=DispatchDocType.AB,
            document_number=conf.confirmation_number,
            an=an,
            cc=cc,
            betreff=f"Auftragsbestätigung {conf.confirmation_number}{firmenzusatz(db)}",
            text=(
                f"Sehr geehrte Damen und Herren bei {customer_name},\n\n"
                f"anbei finden Sie die Auftragsbestätigung {conf.confirmation_number}\n"
                f"zu Ihrer Bestellung {order.order_number}.\n\n"
                f"{gruss(db)}"
            ),
            pdf=pdf,
            user=user,
            customer_id=order.customer_id,
            order_id=order.id,
            confirmation_id=conf.id,
            kunde=bestellkunde(order),
        )
    except EmailNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"E-Mail-Versand fehlgeschlagen: {e}")

    conf.status = ConfirmationStatus.VERSENDET
    # sent_at/sent_to_email: erster MAIL-Versand (Kurzanzeige); maßgeblich ist das Protokoll
    if conf.sent_at is None:
        conf.sent_at = eintrag.sent_at
        conf.sent_to_email = ", ".join(an)[:200]
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
    pdf = PDFService.generate_confirmation_pdf(conf, settings=load_company_settings(db), db=db)
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition(
            beleg_dateiname(conf.confirmation_number, kunde=bestellkunde(conf.order)))},
    )


# ==================== LIEFERSCHEIN + PACKLISTE ====================

@router.post(
    "/orders/{order_id}/delivery-notes",
    response_model=DeliveryNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_delivery_note(
    order_id: UUID,
    data: DeliveryNoteCreate,
    db: DBSession,
    zusaetzlich: bool = False,
):
    """Lieferschein + zugehörige Verpackungsliste anlegen.

    Falls `packing_items` leer ist, werden Items 1:1 aus den Order-Lines
    übernommen (ohne Pfand-Container).

    Ein weiterer Lieferschein zu derselben Bestellung nur mit
    `?zusaetzlich=true`. Abgerechnet wird die Bestellung (einmal), nicht der
    Lieferschein — ein zweiter ist also kein Abrechnungsrisiko mehr, aber fast
    immer ein Versehen. Gewollt ist er, wenn die Bestellung nach dem ersten
    Lieferschein geändert wurde und die Packliste (ein Schnappschuss) neu
    gebraucht wird.
    """
    order = _load_order_with_lines(db, order_id)
    if not order.lines:
        raise HTTPException(status_code=400, detail="Bestellung hat keine Positionen")

    vorhandene = db.execute(
        select(DeliveryNote.delivery_note_number)
        .where(DeliveryNote.order_id == order.id)
        .order_by(DeliveryNote.delivery_note_number)
    ).scalars().all()
    if vorhandene and not zusaetzlich:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Zu dieser Bestellung gibt es bereits den Lieferschein "
                f"{', '.join(vorhandene)}. Ein weiterer Lieferschein wird nicht "
                f"zusätzlich berechnet; er ist nur nötig, wenn die Packliste nach "
                f"einer Bestelländerung neu erstellt werden muss."
            ),
        )

    # Paket 4, B: dieselbe Anlage wie beim Ausliefern (lieferschein_service)
    note = lieferschein_anlegen(
        db, order,
        notes=data.notes,
        packing_items=data.packing_items,
        total_weight_g=data.total_weight_g,
        total_packages=data.total_packages,
    )

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


@router.post("/delivery-notes/{note_id}/send", response_model=DeliveryNoteResponse)
def send_delivery_note(note_id: UUID, data: BelegVersandRequest, db: DBSession, user: CurrentUser):
    """Lieferschein per E-Mail versenden (Paket 3, Q2) — gleiche Regeln wie die AB.

    - Mail: `to` oder `use_customer_recipients` (LS-Empfänger, sonst Haupt-E-Mail).
    - Leerer Body: keine Mail, nur ENTWURF → AUSGESTELLT.
    - ENTWURF wird mit dem ersten Versand AUSGESTELLT; ein quittierter
      Lieferschein (GELIEFERT) bleibt GELIEFERT und geht als Kopie hinaus.
    - Erneuter Versand nur mit unverändertem PDF (Inhalt aus den aktuellen
      Bestellpositionen, siehe send_confirmation).
    Anhang ist das Lieferschein-PDF, ohne Packliste.
    """
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
    order = note.order
    customer = order.customer if order else None

    try:
        an, cc = empfaenger_fuer_versand(
            customer, DispatchDocType.LS,
            to=data.to, cc=data.cc, use_customer_recipients=data.use_customer_recipients,
        )
    except ValueError as e:  # auch KeinEmpfaenger und die Obergrenze An + Cc
        raise HTTPException(status_code=400, detail=str(e))

    if not an and note.status != DeliveryNoteStatus.ENTWURF:
        raise HTTPException(status_code=400, detail="Lieferschein ist bereits ausgestellt")

    pdf = PDFService.generate_delivery_note_pdf(note, settings=load_company_settings(db), db=db)

    if not an:
        markiere_ohne_mail(
            db, doc_type=DispatchDocType.LS, document_number=note.delivery_note_number,
            pdf=pdf, user=user, customer_id=order.customer_id if order else None,
            order_id=note.order_id, delivery_note_id=note.id, kunde=bestellkunde(order),
        )
        note.status = DeliveryNoteStatus.AUSGESTELLT
        db.commit()
        db.refresh(note)
        return note

    nachweis = erster_nachweis(note.dispatches)
    if nachweis is not None and nachweis.attachment_sha256 != pdf_pruefsumme(pdf):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Bestellung oder Belegvorlage wurden seit dem ersten Versand von "
                f"Lieferschein {note.delivery_note_number} geändert. Bitte einen neuen "
                f"Lieferschein anlegen."
            ),
        )

    customer_name = customer.name if customer else "Kunde"
    try:
        versende_beleg(
            db,
            doc_type=DispatchDocType.LS,
            document_number=note.delivery_note_number,
            an=an,
            cc=cc,
            betreff=f"Lieferschein {note.delivery_note_number}{firmenzusatz(db)}",
            text=(
                f"Sehr geehrte Damen und Herren bei {customer_name},\n\n"
                f"anbei finden Sie den Lieferschein {note.delivery_note_number}\n"
                f"zu Ihrer Bestellung {order.order_number if order else '—'}.\n\n"
                f"{gruss(db)}"
            ),
            pdf=pdf,
            user=user,
            customer_id=order.customer_id if order else None,
            order_id=note.order_id,
            delivery_note_id=note.id,
            kunde=bestellkunde(order),
        )
    except EmailNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"E-Mail-Versand fehlgeschlagen: {e}")

    if note.status == DeliveryNoteStatus.ENTWURF:
        note.status = DeliveryNoteStatus.AUSGESTELLT
    db.commit()
    db.refresh(note)
    return note


@router.patch(
    "/delivery-notes/{note_id}/mark-delivered",
    response_model=DeliveryNoteResponse,
)
def mark_delivered(note_id: UUID, data: DeliveryNoteMarkDelivered, db: DBSession, user: CurrentUser):
    """Lieferschein quittieren.

    Steht die Bestellung noch vor GELIEFERT, wechselt sie über dieselbe Regel
    wie der Status-Endpunkt (order_status_service.setze_status): Übergang
    geprüft, Lieferdatum, Bestandsabzug, Audit-Log. Ist sie schon geliefert
    und fehlt ihr das Lieferdatum (Altfälle vor Oktober 2026), wird es aus
    dem Lieferschein nachgetragen.
    """
    note = db.execute(
        select(DeliveryNote)
        .options(joinedload(DeliveryNote.order))
        .where(DeliveryNote.id == note_id)
    ).unique().scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Lieferschein nicht gefunden")
    if note.is_locked():
        raise HTTPException(status_code=400, detail="Lieferschein ist bereits quittiert")

    lieferdatum = data.actual_delivery_date or heute_berlin()
    if lieferdatum > heute_berlin():
        raise HTTPException(
            status_code=400,
            detail=f"Lieferdatum {lieferdatum:%d.%m.%Y} liegt in der Zukunft",
        )

    note.status = DeliveryNoteStatus.GELIEFERT
    note.delivered_at = datetime.now(timezone.utc)
    note.signed_by = data.signed_by
    note.actual_delivery_date = lieferdatum

    order = note.order
    grund = f"Lieferschein {note.delivery_note_number} quittiert"
    if order and order.status in (OrderStatus.GELIEFERT, OrderStatus.FAKTURIERT):
        trage_lieferdatum_nach(db, order, lieferdatum, user=user, reason=grund)
    elif order:
        try:
            setze_status(
                db, order, OrderStatus.GELIEFERT,
                user=user,
                action="LIEFERSCHEIN_QUITTIERT",
                reason=grund,
                lieferdatum=lieferdatum,
            )
        except StatuswechselFehler as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Lieferschein nicht quittiert — {e}")
        except BestandsbuchungFehler as e:
            db.rollback()
            import logging; logging.getLogger(__name__).exception(
                "Bestandsabzug nach LS-Quittierung fehlgeschlagen: %s", e
            )
            raise HTTPException(
                status_code=500,
                detail=f"Quittierung abgebrochen — Bestandsabzug fehlgeschlagen: {e}",
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
    pdf = PDFService.generate_delivery_note_pdf(note, settings=load_company_settings(db), db=db)
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition(
            beleg_dateiname(note.delivery_note_number, kunde=bestellkunde(note.order)))},
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
    pdf = PDFService.generate_packing_list_pdf(note.packing_list, settings=load_company_settings(db), db=db)
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition(
            beleg_dateiname(note.packing_list.packing_list_number, kunde=bestellkunde(note.order)))},
    )
