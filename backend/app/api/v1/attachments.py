"""Datei-Anhänge API: Upload / List / Download / Update / Delete.

Endpoints:
    POST   /attachments/{entity_type}/{entity_id}   → multipart upload
    GET    /attachments/{entity_type}/{entity_id}   → Metadaten-Liste
    GET    /attachments/{att_id}/download           → Binary
    PATCH  /attachments/{att_id}                    → Metadata-Update
    DELETE /attachments/{att_id}                    → Datei + Eintrag löschen

entity_type ∈ {supplier, product, harvest}.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import DBSession
from app.models.attachment import Attachment, ATTACHMENT_ENTITY_TYPES, CERTIFICATE_TYPES
from app.models.seed import Supplier
from app.models.product import Product
from app.models.production import Harvest
from app.models.inventory import SeedInventory
from app.schemas.attachment import AttachmentResponse, AttachmentUpdate
from app.services.storage_service import get_storage

router = APIRouter(prefix="/attachments", tags=["Anhänge"])


ENTITY_MODELS = {
    "supplier": Supplier,
    "product": Product,
    "harvest": Harvest,
    "seed_inventory": SeedInventory,
}


def _validate_entity_type(entity_type: str):
    if entity_type not in ATTACHMENT_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Ungültiger entity_type '{entity_type}'. Erlaubt: {', '.join(ATTACHMENT_ENTITY_TYPES)}",
        )


def _ensure_entity_exists(db, entity_type: str, entity_id: UUID):
    model = ENTITY_MODELS[entity_type]
    if not db.get(model, entity_id):
        raise HTTPException(status_code=404, detail=f"{entity_type.capitalize()} nicht gefunden")


@router.get("/{att_id}/download")
def download_attachment(att_id: UUID, db: DBSession):
    """Datei-Download (Original-Mimetype). Hier zuerst registriert, sonst würde
    /{entity_type}/{entity_id} die UUID schlucken (Route-Order)."""
    att = db.get(Attachment, att_id)
    if not att:
        raise HTTPException(status_code=404, detail="Anhang nicht gefunden")
    storage = get_storage()
    try:
        fp = storage.open(att.storage_key)
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="Datei nicht mehr im Storage vorhanden")

    return StreamingResponse(
        fp,
        media_type=att.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{att.filename}"'},
    )


@router.patch("/{att_id}", response_model=AttachmentResponse)
def update_attachment(att_id: UUID, data: AttachmentUpdate, db: DBSession):
    """Aktualisiert nur Metadaten (Zertifikat-Typ, Gültigkeit, Notizen)."""
    att = db.get(Attachment, att_id)
    if not att:
        raise HTTPException(status_code=404, detail="Anhang nicht gefunden")
    payload = data.model_dump(exclude_unset=True)
    if "certificate_type" in payload and payload["certificate_type"] and payload["certificate_type"] not in CERTIFICATE_TYPES:
        raise HTTPException(status_code=400, detail=f"Ungültiger certificate_type")
    for k, v in payload.items():
        setattr(att, k, v)
    db.commit()
    db.refresh(att)
    return att


@router.delete("/{att_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(att_id: UUID, db: DBSession):
    """Löscht Eintrag + Datei im Storage."""
    att = db.get(Attachment, att_id)
    if not att:
        raise HTTPException(status_code=404, detail="Anhang nicht gefunden")
    storage = get_storage()
    storage.delete(att.storage_key)
    db.delete(att)
    db.commit()
    return None


@router.post("/{entity_type}/{entity_id}", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    entity_type: str,
    entity_id: UUID,
    db: DBSession,
    file: UploadFile = File(...),
    certificate_type: Optional[str] = Form(None),
    bio_kontrollstelle: Optional[str] = Form(None),
    valid_until: Optional[date] = Form(None),
    notes: Optional[str] = Form(None),
):
    """Datei-Upload mit optionalen Zertifikat-Metadaten."""
    _validate_entity_type(entity_type)
    _ensure_entity_exists(db, entity_type, entity_id)

    if certificate_type and certificate_type not in CERTIFICATE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Ungültiger certificate_type. Erlaubt: {', '.join(CERTIFICATE_TYPES)}",
        )

    # Max 20 MB
    MAX_SIZE = 20 * 1024 * 1024
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Datei zu groß (max. 20 MB)")
    if not contents:
        raise HTTPException(status_code=400, detail="Leere Datei")

    storage = get_storage()
    storage_key, size = storage.save(BytesIO(contents), entity_type, str(entity_id), file.filename or "upload.bin")

    att = Attachment(
        entity_type=entity_type,
        entity_id=entity_id,
        filename=file.filename or "upload.bin",
        content_type=file.content_type,
        size_bytes=size,
        storage_key=storage_key,
        certificate_type=certificate_type,
        bio_kontrollstelle=bio_kontrollstelle,
        valid_until=valid_until,
        notes=notes,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


@router.get("/{entity_type}/{entity_id}", response_model=list[AttachmentResponse])
def list_attachments(entity_type: str, entity_id: UUID, db: DBSession):
    """Liste aller Anhänge zu einer Entität."""
    _validate_entity_type(entity_type)
    rows = db.execute(
        select(Attachment)
        .where(Attachment.entity_type == entity_type, Attachment.entity_id == entity_id)
        .order_by(Attachment.uploaded_at.desc())
    ).scalars().all()
    return rows


