from typing import Optional
"""
Rechnungs-API - Endpoints für Rechnungen, Zahlungen und DATEV-Export
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select

from app.api.deps import DBSession, Pagination
from app.models.invoice import (
    Invoice, InvoiceLine, Payment,
    InvoiceStatus, InvoiceType, PaymentMethod
)
from app.schemas.invoice import (
    InvoiceCreate, InvoiceUpdate, InvoiceResponse, InvoiceDetailResponse,
    InvoiceLineCreate, InvoiceLineUpdate, InvoiceLineResponse,
    PaymentCreate, PaymentResponse,
    InvoiceSendRequest, InvoiceCancelRequest,
    DatevExportRequest, DatevExportResponse,
)
from app.services.invoice_service import InvoiceService
from app.services.datev_service import DatevService
from app.services.email_service import send_email, EmailNotConfiguredError
from app.services.pdf_service import load_company_settings

router = APIRouter(prefix="/invoices", tags=["Rechnungen"])


# ========================================
# INVOICES
# ========================================

@router.get("", response_model=list[InvoiceResponse])
def list_invoices(
    db: DBSession,
    pagination: Pagination,
    status: Optional[InvoiceStatus] = None,
    customer_id: Optional[UUID] = None,
    invoice_type: Optional[InvoiceType] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
):
    """Listet alle Rechnungen mit optionaler Filterung."""
    query = select(Invoice).options(joinedload(Invoice.lines))

    if status:
        query = query.where(Invoice.status == status)

    if customer_id:
        query = query.where(Invoice.customer_id == customer_id)

    if invoice_type:
        query = query.where(Invoice.invoice_type == invoice_type)

    if from_date:
        query = query.where(Invoice.invoice_date >= from_date)

    if to_date:
        query = query.where(Invoice.invoice_date <= to_date)

    query = query.order_by(Invoice.invoice_date.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)

    invoices = db.execute(query).scalars().unique().all()
    return invoices


@router.get("/overdue", response_model=list[InvoiceResponse])
def list_overdue_invoices(db: DBSession):
    """Listet alle überfälligen Rechnungen."""
    service = InvoiceService(db)
    overdue = service.check_overdue_invoices()
    db.commit()
    return overdue


@router.get("/revenue-summary")
def get_revenue_summary(
    from_date: date,
    to_date: date,
    db: DBSession,
):
    """Gibt Umsatzübersicht für Zeitraum zurück."""
    service = InvoiceService(db)
    return service.get_revenue_summary(from_date, to_date)


@router.get("/{invoice_id}", response_model=InvoiceDetailResponse)
def get_invoice(invoice_id: UUID, db: DBSession):
    """Gibt eine einzelne Rechnung mit allen Details zurück."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    antwort = InvoiceDetailResponse.model_validate(invoice)
    # Rückverweis auf die Stornorechnung — für die Verlinkung beider Belege
    antwort.cancelled_by_invoice_id = db.execute(
        select(Invoice.id).where(Invoice.original_invoice_id == invoice_id)
    ).scalar_one_or_none()
    return antwort


@router.post("", response_model=InvoiceResponse, status_code=201)
def create_invoice(data: InvoiceCreate, db: DBSession):
    """Erstellt eine neue Rechnung."""
    service = InvoiceService(db)
    try:
        invoice = service.create_invoice(
            **data.model_dump(exclude={"billing_address", "shipping_address", "lines"})
        )
        
        # Positionen hinzufügen
        if data.lines:
            for line in data.lines:
                service.add_line(
                    invoice_id=invoice.id,
                    **line.model_dump()
                )
        
        db.commit()
        db.refresh(invoice)
        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/from-order/{order_id}", response_model=InvoiceResponse, status_code=201)
def create_invoice_from_order(order_id: UUID, db: DBSession):
    """Erstellt eine Rechnung aus einer Bestellung."""
    service = InvoiceService(db)
    try:
        invoice = service.create_invoice_from_order(order_id)
        db.commit()
        db.refresh(invoice)
        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: UUID,
    data: InvoiceUpdate,
    db: DBSession,
):
    """Aktualisiert eine Rechnung (nur Entwürfe)."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    if invoice.status != InvoiceStatus.ENTWURF:
        raise HTTPException(status_code=400, detail="Nur Entwürfe können bearbeitet werden")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(invoice, field, value)

    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/finalize", response_model=InvoiceResponse)
def finalize_invoice(invoice_id: UUID, db: DBSession):
    """Finalisiert eine Rechnung (Entwurf -> Offen)."""
    service = InvoiceService(db)
    try:
        invoice = service.finalize_invoice(invoice_id)
        db.commit()
        db.refresh(invoice)
        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{invoice_id}/payment-reminder")
def generate_payment_reminder(
    invoice_id: UUID,
    db: DBSession,
    level: int = Query(default=1, ge=1, le=3, description="1=Erinnerung, 2=1.Mahnung, 3=2.Mahnung"),
    dunning_fee: float = Query(default=0.0, ge=0.0),
):
    """Generiert eine Zahlungserinnerung / Mahnung als PDF + erhöht reminder_level."""
    from app.models.invoice import Invoice as InvoiceModel
    from app.services.pdf_service import PDFService
    from io import BytesIO
    from fastapi.responses import StreamingResponse

    invoice = db.execute(
        select(InvoiceModel)
        .options(joinedload(InvoiceModel.customer), joinedload(InvoiceModel.lines))
        .where(InvoiceModel.id == invoice_id)
    ).unique().scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    if invoice.status in (InvoiceStatus.BEZAHLT, InvoiceStatus.STORNIERT):
        raise HTTPException(status_code=400, detail="Bezahlte/stornierte Rechnungen können nicht gemahnt werden")

    pdf = PDFService.generate_payment_reminder_pdf(invoice, reminder_level=level, dunning_fee=dunning_fee, settings=load_company_settings(db), db=db)

    # Mahnstufe persistieren wenn höher
    if level > (invoice.reminder_level or 0):
        invoice.reminder_level = level
        from datetime import datetime as _dt, timezone as _tz
        invoice.last_reminder_sent_at = _dt.now(_tz.utc)
        db.commit()

    filename = f"Zahlungserinnerung_{invoice.invoice_number}_Stufe{level}.pdf"
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{invoice_id}/send")
def send_invoice_email(
    invoice_id: UUID,
    db: DBSession,
    to_email: str = Query(..., description="Empfänger-Adresse"),
):
    """Sendet die Rechnung als PDF-Anhang per E-Mail.

    Setzt zusätzlich sent_at; bei ENTWURF-Status wird automatisch nach OFFEN
    überführt (gleicher Effekt wie /finalize)."""
    from app.models.invoice import Invoice as InvoiceModel  # local import to avoid cycle
    from app.services.pdf_service import PDFService
    from datetime import datetime as _dt, timezone as _tz

    invoice = db.execute(
        select(InvoiceModel)
        .options(joinedload(InvoiceModel.customer), joinedload(InvoiceModel.lines))
        .where(InvoiceModel.id == invoice_id)
    ).unique().scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    if invoice.status == InvoiceStatus.STORNIERT:
        raise HTTPException(status_code=400, detail="Stornierte Rechnungen können nicht versendet werden")
    if not invoice.lines:
        raise HTTPException(status_code=400, detail="Rechnung hat keine Positionen")

    try:
        pdf = PDFService.generate_invoice_pdf(invoice, settings=load_company_settings(db), db=db)
        send_email(
            db=db,
            to=to_email,
            subject=f"Rechnung {invoice.invoice_number} — Minga Greens",
            body=(
                f"Sehr geehrte Damen und Herren bei {invoice.customer.name},\n\n"
                f"anbei finden Sie die Rechnung {invoice.invoice_number} über\n"
                f"{invoice.total:.2f} {invoice.currency}.\n\n"
                f"Fällig am: {invoice.due_date.strftime('%d.%m.%Y') if invoice.due_date else '—'}\n\n"
                f"Mit freundlichen Grüßen\nIhr Minga-Greens-Team"
            ),
            attachment_bytes=pdf,
            attachment_filename=f"{invoice.invoice_number}.pdf",
        )
    except EmailNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"E-Mail-Versand fehlgeschlagen: {e}")

    invoice.sent_at = _dt.now(_tz.utc)
    if invoice.status == InvoiceStatus.ENTWURF:
        invoice.status = InvoiceStatus.OFFEN
    db.commit()
    db.refresh(invoice)
    return {"invoice_number": invoice.invoice_number, "sent_to": to_email, "sent_at": invoice.sent_at}


@router.post("/{invoice_id}/cancel")
def cancel_invoice(
    invoice_id: UUID,
    data: InvoiceCancelRequest,
    db: DBSession,
):
    """Storniert eine Rechnung und erstellt optional eine Gutschrift."""
    service = InvoiceService(db)
    try:
        # Auswahlgrund + Freitext zusammen — beides gehört in die Akte (R1.4)
        grund = f"[{data.reason_code}] {data.reason}" if data.reason_code else data.reason
        invoice, credit_note = service.cancel_invoice(
            invoice_id=invoice_id,
            reason=grund,
            create_credit_note=data.create_credit_note,
        )
        db.commit()
        return {
            "invoice": InvoiceResponse.model_validate(invoice),
            "credit_note": InvoiceResponse.model_validate(credit_note) if credit_note else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========================================
# INVOICE LINES
# ========================================

@router.post("/{invoice_id}/lines", response_model=InvoiceLineResponse, status_code=201)
def add_invoice_line(
    invoice_id: UUID,
    data: InvoiceLineCreate,
    db: DBSession,
):
    """Fügt eine Position zur Rechnung hinzu."""
    service = InvoiceService(db)
    try:
        line = service.add_line(
            invoice_id=invoice_id,
            **data.model_dump(),
        )
        db.commit()
        db.refresh(line)
        return line
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{invoice_id}/lines/{line_id}", response_model=InvoiceLineResponse)
def update_invoice_line(
    invoice_id: UUID,
    line_id: UUID,
    data: InvoiceLineUpdate,
    db: DBSession,
):
    """Aktualisiert eine Rechnungsposition."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    if invoice.status != InvoiceStatus.ENTWURF:
        raise HTTPException(status_code=400, detail="Nur Entwürfe können bearbeitet werden")

    line = db.get(InvoiceLine, line_id)
    if not line or line.invoice_id != invoice_id:
        raise HTTPException(status_code=404, detail="Position nicht gefunden")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(line, field, value)

    # Zeile und Rechnung neu berechnen
    line.calculate_line_total()
    invoice.calculate_totals()

    db.commit()
    db.refresh(line)
    return line


@router.delete("/{invoice_id}/lines/{line_id}", status_code=204)
def delete_invoice_line(
    invoice_id: UUID,
    line_id: UUID,
    db: DBSession,
):
    """Löscht eine Rechnungsposition."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    if invoice.status != InvoiceStatus.ENTWURF:
        raise HTTPException(status_code=400, detail="Nur Entwürfe können bearbeitet werden")

    line = db.get(InvoiceLine, line_id)
    if not line or line.invoice_id != invoice_id:
        raise HTTPException(status_code=404, detail="Position nicht gefunden")

    db.delete(line)
    invoice.calculate_totals()
    db.commit()


# ========================================
# PAYMENTS
# ========================================

@router.get("/{invoice_id}/payments", response_model=list[PaymentResponse])
def list_invoice_payments(invoice_id: UUID, db: DBSession):
    """Listet alle Zahlungen einer Rechnung."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    return invoice.payments


@router.post("/{invoice_id}/payments", response_model=PaymentResponse, status_code=201)
def record_payment(
    invoice_id: UUID,
    data: PaymentCreate,
    db: DBSession,
):
    """Erfasst eine Zahlung für eine Rechnung."""
    service = InvoiceService(db)
    try:
        payment = service.record_payment(
            invoice_id=invoice_id,
            **data.model_dump(exclude={"invoice_id"}),
        )
        db.commit()
        db.refresh(payment)
        return payment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========================================
# DATEV EXPORT
# ========================================

@router.post("/datev-export")
def export_datev(
    data: DatevExportRequest,
    db: DBSession,
):
    """Exportiert Rechnungen im DATEV-Format."""
    service = DatevService(db)
    csv_content, record_count, total_amount = service.export_invoices_csv(
        from_date=data.from_date,
        to_date=data.to_date,
        include_payments=data.include_payments,
    )
    db.commit()

    return DatevExportResponse(
        csv_content=csv_content,
        record_count=record_count,
        total_amount=total_amount,
        filename=f"DATEV_Export_{data.from_date}_{data.to_date}.csv",
        export_date=datetime.now(timezone.utc),
    )


@router.post("/datev-export/download")
def download_datev_export(
    data: DatevExportRequest,
    db: DBSession,
):
    """Exportiert Rechnungen als DATEV CSV-Datei zum Download."""
    service = DatevService(db)
    csv_content, record_count, total_amount = service.export_invoices_csv(
        from_date=data.from_date,
        to_date=data.to_date,
        include_payments=data.include_payments,
    )
    db.commit()

    filename = f"DATEV_Export_{data.from_date}_{data.to_date}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        }
    )

@router.get("/{invoice_id}/pdf")
def get_invoice_pdf(
    invoice_id: UUID,
    db: DBSession,
):
    """Generiert ein PDF für die Rechnung."""
    # Lines + Customer eager laden — PDF-Service iteriert über invoice.lines
    # (Reverse-Charge-Check) und liest customer.billing_address; bei lazy
    # load würde das in strikten Async-Contexts crashen.
    invoice = db.execute(
        select(Invoice)
        .options(joinedload(Invoice.lines), joinedload(Invoice.customer))
        .where(Invoice.id == invoice_id)
    ).unique().scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    from app.services.pdf_service import PDFService
    pdf_content = PDFService.generate_invoice_pdf(invoice, settings=load_company_settings(db), db=db)
    
    filename = f"Rechnung_{invoice.invoice_number}.pdf"
    
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        }
    )


# =====================================================================
# Sammelrechnung (Warenfluss-Release, AP2)
#
# Ein Lauf je Zeitraum: alle nicht abgerechneten Lieferscheine der Kunden
# werden je Artikel + Einheit + Einzelpreis + Steuersatz aggregiert.
# Vorschau rechnet nur; erst das Festschreiben vergibt Nummern und setzt
# delivery_notes.invoice_id — der Doppelabrechnungsschutz (R2.5).
# =====================================================================

from pydantic import BaseModel as _BaseModel, Field as _Field

from app.models.documents import DeliveryNote
from app.models.enums import OrderStatus
from app.models.invoice import InvoiceLineSource
from app.models.order import Order, OrderLine


class BatchRunRequest(_BaseModel):
    period_from: date
    period_to: date
    customer_ids: Optional[list[UUID]] = _Field(None, description="leer = alle Kunden")
    invoice_date: Optional[date] = None


def _abrechenbare_lieferscheine(db, anfrage: BatchRunRequest):
    """Lieferscheine des Zeitraums, die noch in keiner Rechnung stecken.

    Leistungsdatum je Lieferschein: das tatsächliche Lieferdatum, ersatzweise
    das Wunschlieferdatum der Bestellung. Stornierte Bestellungen bleiben
    draußen.
    """
    notes = db.execute(
        select(DeliveryNote)
        .join(Order, DeliveryNote.order_id == Order.id)
        .where(
            DeliveryNote.invoice_id.is_(None),
            Order.status != OrderStatus.STORNIERT,
        )
    ).scalars().all()

    ergebnis = []
    for note in notes:
        leistungsdatum = note.actual_delivery_date or note.order.requested_delivery_date
        if not (anfrage.period_from <= leistungsdatum <= anfrage.period_to):
            continue
        if anfrage.customer_ids and note.order.customer_id not in anfrage.customer_ids:
            continue
        ergebnis.append((note, leistungsdatum))
    return ergebnis


def _aggregiere(notes) -> dict:
    """Je Kunde: Positionen aggregiert nach (Artikel, Einheit, Preis, Steuersatz).

    Merkt sich je Position, welcher Lieferschein wie viel beigetragen hat —
    daraus entstehen beim Festschreiben die invoice_line_sources (R2.3).
    """
    kunden: dict = {}
    for note, leistungsdatum in notes:
        order = note.order
        k = kunden.setdefault(order.customer_id, {
            "customer_id": order.customer_id,
            "customer_name": order.customer.name if order.customer else "—",
            "lieferscheine": [],
            "positionen": {},
        })
        k["lieferscheine"].append(note)
        for line in order.lines:
            key = (line.beschreibung or "Position", line.unit,
                   line.unit_price, line.tax_rate)
            pos = k["positionen"].setdefault(key, {"menge": Decimal("0"), "quellen": []})
            pos["menge"] += line.quantity
            pos["quellen"].append((note.id, line.quantity))
    return kunden


@router.post("/batch-run/preview")
def batch_run_preview(anfrage: BatchRunRequest, db: DBSession):
    """Vorschau des Sammelrechnungslaufs — rechnet, schreibt nichts (R2.6)."""
    kunden = _aggregiere(_abrechenbare_lieferscheine(db, anfrage))
    return {
        "period_from": anfrage.period_from.isoformat(),
        "period_to": anfrage.period_to.isoformat(),
        "kunden": [{
            "customer_id": str(k["customer_id"]),
            "customer_name": k["customer_name"],
            "anzahl_lieferscheine": len(k["lieferscheine"]),
            "positionen": [{
                "description": key[0], "unit": key[1],
                "unit_price": key[2], "tax_rate": key[3].value,
                "quantity": pos["menge"],
            } for key, pos in sorted(k["positionen"].items(), key=lambda e: (e[0][0], e[0][2]))],
            "summe_netto": sum((pos["menge"] * key[2] for key, pos in k["positionen"].items()),
                               Decimal("0")),
        } for k in kunden.values()],
    }


@router.post("/batch-run/commit", status_code=201)
def batch_run_commit(anfrage: BatchRunRequest, db: DBSession):
    """Schreibt den Lauf fest: eine Rechnung je Kunde, Nummern aus dem
    regulären Kreis, Lieferscheine fest zugeordnet (R2.1–R2.5)."""
    kunden = _aggregiere(_abrechenbare_lieferscheine(db, anfrage))
    service = InvoiceService(db)
    rechnungen = []

    for k in kunden.values():
        invoice = service.create_invoice(
            customer_id=k["customer_id"],
            invoice_date=anfrage.invoice_date or date.today(),
            header_text=(
                f"Sammelrechnung — Leistungszeitraum "
                f"{anfrage.period_from.strftime('%d.%m.%Y')}–{anfrage.period_to.strftime('%d.%m.%Y')}"
            ),
        )
        invoice.service_period_start = anfrage.period_from
        invoice.service_period_end = anfrage.period_to

        for (beschreibung, unit, preis, steuersatz), pos in sorted(
            k["positionen"].items(), key=lambda e: (e[0][0], e[0][2])
        ):
            line = service.add_line(
                invoice_id=invoice.id,
                description=beschreibung,
                quantity=pos["menge"],
                unit=unit,
                unit_price=preis,
                tax_rate=steuersatz,
            )
            db.flush()
            for note_id, menge in pos["quellen"]:
                db.add(InvoiceLineSource(
                    invoice_line_id=line.id,
                    delivery_note_id=note_id,
                    quantity=menge,
                ))

        # Doppelabrechnungsschutz: ab jetzt hängt der Lieferschein an dieser
        # Rechnung — der nächste Lauf sieht ihn nicht mehr (R2.5).
        for note in k["lieferscheine"]:
            note.invoice_id = invoice.id

        # Summen über ALLE Zeilen: die lines-Relationship kann nach dem
        # zeilenweisen add_line noch den alten Stand tragen.
        db.flush()
        db.refresh(invoice)
        invoice.calculate_totals()

        invoice.status = InvoiceStatus.OFFEN
        rechnungen.append(invoice)

    db.commit()
    return {
        "rechnungen": [InvoiceResponse.model_validate(r) for r in rechnungen],
    }


@router.get("/{invoice_id}/delivery-notes")
def invoice_delivery_notes(invoice_id: UUID, db: DBSession):
    """Die in einer (Sammel-)Rechnung enthaltenen Lieferscheine (R2.3)."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    notes = db.execute(
        select(DeliveryNote).where(DeliveryNote.invoice_id == invoice_id)
    ).scalars().all()
    return [{
        "id": str(n.id),
        "delivery_note_number": n.delivery_note_number,
        "lieferdatum": (n.actual_delivery_date or n.order.requested_delivery_date).isoformat(),
        "betrag_netto": sum((l.quantity * l.unit_price for l in n.order.lines), Decimal("0")),
    } for n in notes]
