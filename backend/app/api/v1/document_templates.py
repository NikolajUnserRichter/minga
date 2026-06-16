"""API für Document-Templates (anpassbare Belegart-Layouts).

Endpoints (unter /api/v1):
    GET    /document-templates                 → alle 5 Templates (auto-seeded auf erstem Aufruf)
    GET    /document-templates/{document_type} → einzelnes Template
    PATCH  /document-templates/{document_type} → Texte/Sektionen/Spalten/Farben editieren
    GET    /document-templates/{document_type}/preview.pdf → Live-PDF mit Dummy-Daten
    POST   /document-templates/{document_type}/logo  → Logo via attachments-System hochladen
    GET    /document-templates/{document_type}/placeholders → Liste verfügbarer Placeholder
"""
from __future__ import annotations

from io import BytesIO
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import DBSession
from app.models.document_template import (
    DocumentTemplate, DocumentType,
    DEFAULT_SECTIONS, DEFAULT_COLUMNS, DEFAULT_TEXTS,
)
from app.models.attachment import Attachment
from app.schemas.document_template import DocumentTemplateResponse, DocumentTemplateUpdate
from app.services.storage_service import get_storage

router = APIRouter(prefix="/document-templates", tags=["Document-Templates"])


# Liste der verfügbaren Placeholder pro Document-Type (Doku fürs UI)
PLACEHOLDERS_BY_TYPE: dict[str, list[str]] = {
    "RECHNUNG":              ["{customer_name}", "{customer_number}", "{invoice_number}",
                              "{invoice_date}", "{due_date}", "{total_net}", "{total_vat}",
                              "{total_gross}", "{currency}", "{order_number}",
                              "{skonto_percent}", "{skonto_days}"],
    "AUFTRAGSBESTAETIGUNG":  ["{customer_name}", "{customer_number}", "{confirmation_number}",
                              "{order_number}", "{requested_delivery_date}", "{total_gross}"],
    "LIEFERSCHEIN":          ["{customer_name}", "{customer_number}", "{delivery_note_number}",
                              "{order_number}", "{delivery_date}", "{delivery_address}"],
    "VERPACKUNGSLISTE":      ["{customer_name}", "{packing_list_number}",
                              "{delivery_note_number}", "{order_number}",
                              "{total_weight_g}", "{total_packages}"],
    "MAHNUNG":               ["{customer_name}", "{customer_number}", "{invoice_number}",
                              "{invoice_date}", "{due_date}", "{days_overdue}",
                              "{open_amount}", "{dunning_fee}", "{total_due}"],
}


def _seed_default(db, document_type: DocumentType) -> DocumentTemplate:
    """Legt ein Default-Template an wenn noch keines existiert.

    Race-safe: bei parallelen Requests gewinnt der erste INSERT, alle anderen
    fangen die IntegrityError ab und lesen das vom Sieger angelegte Row.
    """
    from sqlalchemy.exc import IntegrityError
    tmpl = db.execute(
        select(DocumentTemplate).where(DocumentTemplate.document_type == document_type)
    ).scalar_one_or_none()
    if tmpl is not None:
        return tmpl
    tmpl = DocumentTemplate(
        document_type=document_type,
        texts=DEFAULT_TEXTS.get(document_type.value, {}),
        sections=DEFAULT_SECTIONS.get(document_type.value, []),
        columns=DEFAULT_COLUMNS.get(document_type.value, []),
        primary_color="#166534",   # Minga-Grün
        accent_color="#6b7280",    # Grau-500
    )
    db.add(tmpl)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        tmpl = db.execute(
            select(DocumentTemplate).where(DocumentTemplate.document_type == document_type)
        ).scalar_one()
        return tmpl
    db.refresh(tmpl)
    return tmpl


def _enrich(db, tmpl: DocumentTemplate) -> DocumentTemplateResponse:
    resp = DocumentTemplateResponse.model_validate(tmpl)
    if tmpl.logo_attachment_id:
        resp.logo_url = f"/api/v1/attachments/{tmpl.logo_attachment_id}/download"
    resp.placeholders = PLACEHOLDERS_BY_TYPE.get(tmpl.document_type.value, [])
    return resp


@router.get("", response_model=list[DocumentTemplateResponse])
def list_templates(db: DBSession):
    """Liefert alle 5 Templates. Auto-Seeded bei erstem Aufruf."""
    out = []
    for dt in DocumentType:
        out.append(_enrich(db, _seed_default(db, dt)))
    return out


@router.get("/{document_type}", response_model=DocumentTemplateResponse)
def get_template(document_type: DocumentType, db: DBSession):
    return _enrich(db, _seed_default(db, document_type))


@router.patch("/{document_type}", response_model=DocumentTemplateResponse)
def update_template(document_type: DocumentType, data: DocumentTemplateUpdate, db: DBSession):
    tmpl = _seed_default(db, document_type)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(tmpl, k, v)
    db.commit()
    db.refresh(tmpl)
    return _enrich(db, tmpl)


@router.post("/{document_type}/logo", response_model=DocumentTemplateResponse, status_code=status.HTTP_201_CREATED)
async def upload_logo(
    document_type: DocumentType,
    db: DBSession,
    file: UploadFile = File(...),
):
    """Logo hochladen (PNG/JPG). Ersetzt ein vorhandenes Logo."""
    tmpl = _seed_default(db, document_type)

    MAX = 5 * 1024 * 1024
    contents = await file.read()
    if len(contents) > MAX:
        raise HTTPException(status_code=413, detail="Logo zu groß (max. 5 MB)")
    if not contents:
        raise HTTPException(status_code=400, detail="Leere Datei")

    # Magic-Byte-Check — Content-Type-Header ist Client-supplied und nicht vertrauenswürdig
    head = contents[:16]
    is_png  = head.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = head.startswith(b"\xff\xd8\xff")
    if not (is_png or is_jpeg):
        raise HTTPException(status_code=415, detail="Nur PNG- oder JPEG-Logos werden akzeptiert")

    storage = get_storage()
    storage_key, size = storage.save(BytesIO(contents), "document_template", str(tmpl.id), file.filename or "logo.png")

    # Altes Logo entfernen
    if tmpl.logo_attachment_id:
        old = db.get(Attachment, tmpl.logo_attachment_id)
        if old:
            storage.delete(old.storage_key)
            db.delete(old)

    att = Attachment(
        entity_type="document_template",
        entity_id=tmpl.id,
        filename=file.filename or "logo.png",
        content_type=file.content_type,
        size_bytes=size,
        storage_key=storage_key,
    )
    db.add(att)
    db.flush()
    tmpl.logo_attachment_id = att.id
    db.commit()
    db.refresh(tmpl)
    return _enrich(db, tmpl)


@router.delete("/{document_type}/logo", response_model=DocumentTemplateResponse)
def remove_logo(document_type: DocumentType, db: DBSession):
    tmpl = _seed_default(db, document_type)
    if tmpl.logo_attachment_id:
        old = db.get(Attachment, tmpl.logo_attachment_id)
        if old:
            get_storage().delete(old.storage_key)
            db.delete(old)
        tmpl.logo_attachment_id = None
        db.commit()
        db.refresh(tmpl)
    return _enrich(db, tmpl)


@router.get("/{document_type}/placeholders")
def list_placeholders(document_type: DocumentType):
    """Liste der verfügbaren {…}-Platzhalter für dieses Belegformat."""
    return PLACEHOLDERS_BY_TYPE.get(document_type.value, [])


@router.get("/{document_type}/preview.pdf")
def preview_pdf(document_type: DocumentType, db: DBSession):
    """Liefert ein PDF mit Dummy-Daten für die Live-Preview im Editor."""
    from app.services.pdf_service import PDFService, load_company_settings
    from app.services.document_template_service import (
        build_dummy_invoice, build_dummy_confirmation, build_dummy_delivery_note,
        build_dummy_packing_list, build_dummy_for_reminder,
    )

    settings = load_company_settings(db)

    if document_type == DocumentType.RECHNUNG:
        pdf = PDFService.generate_invoice_pdf(build_dummy_invoice(), settings=settings, db=db)
    elif document_type == DocumentType.AUFTRAGSBESTAETIGUNG:
        pdf = PDFService.generate_confirmation_pdf(build_dummy_confirmation(), settings=settings, db=db)
    elif document_type == DocumentType.LIEFERSCHEIN:
        pdf = PDFService.generate_delivery_note_pdf(build_dummy_delivery_note(), settings=settings, db=db)
    elif document_type == DocumentType.VERPACKUNGSLISTE:
        pdf = PDFService.generate_packing_list_pdf(build_dummy_packing_list(), settings=settings, db=db)
    elif document_type == DocumentType.MAHNUNG:
        pdf = PDFService.generate_payment_reminder_pdf(build_dummy_for_reminder(), reminder_level=1, dunning_fee=0.0, settings=settings, db=db)
    else:
        raise HTTPException(status_code=400, detail=f"Unbekannter Belegtyp: {document_type}")

    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="preview_{document_type.value}.pdf"'},
    )
