from typing import Optional
"""
Rechnungs-API - Endpoints für Rechnungen, Zahlungen und DATEV-Export
"""
from datetime import date
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
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
    query = select(Invoice)

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

    invoices = db.execute(query).scalars().all()
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
    return invoice


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


@router.post("/{invoice_id}/cancel")
def cancel_invoice(
    invoice_id: UUID,
    data: InvoiceCancelRequest,
    db: DBSession,
):
    """Storniert eine Rechnung und erstellt optional eine Gutschrift."""
    service = InvoiceService(db)
    try:
        invoice, credit_note = service.cancel_invoice(
            invoice_id=invoice_id,
            reason=data.reason,
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
    db: Session = Depends(DBSession),
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
        from_date=data.from_date,
        to_date=data.to_date,
    )


@router.post("/datev-export/download")
def download_datev_export(
    data: DatevExportRequest,
    db: Session = Depends(DBSession),
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
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
        
    from app.services.pdf_service import PDFService
    pdf_content = PDFService.generate_invoice_pdf(invoice)
    
    filename = f"Rechnung_{invoice.invoice_number}.pdf"
    
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        }
    )
