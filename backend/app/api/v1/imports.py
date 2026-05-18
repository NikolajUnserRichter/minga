"""Excel-Upload für Stammdaten + Template-Download.

Endpoints:
- GET  /imports/template/{entity}   → XLSX mit Header-Zeile + Beispiel
- POST /imports/{entity}            → Multipart-Upload, parst Rows + upsertet

Unterstützte entities: customers, seeds, products, suppliers, locations
"""
from __future__ import annotations

import io
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Sequence
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy import select

from app.api.deps import DBSession
from app.models.customer import Customer, CustomerType
from app.models.seed import Seed, Supplier
from app.models.product import Product, ProductCategory
from app.models.inventory import InventoryLocation, LocationType
from app.models.unit import UnitOfMeasure
from app.models.enums import TaxRate

router = APIRouter(prefix="/imports", tags=["Excel-Import"])


# ---- Spalten-Definitionen je Entity ---------------------------------------

# Format: (column_header, attr_name, required, type_hint)
COLUMNS = {
    "customers": [
        ("name", "name", True, "str"),
        ("typ", "typ", True, "enum:GASTRO|HANDEL|GEWERBE|PRIVAT"),
        ("email", "email", False, "str"),
        ("telefon", "telefon", False, "str"),
        ("adresse", "adresse", False, "str"),
        ("ust_id", "ust_id", False, "str"),
        ("notizen", "notizen", False, "str"),
    ],
    "suppliers": [
        ("name", "name", True, "str"),
        ("email", "email", False, "str"),
        ("telefon", "telefon", False, "str"),
        ("adresse", "adresse", False, "str"),
        ("ust_id", "ust_id", False, "str"),
        ("product_group", "product_group", False, "enum:SAATGUT|SUBSTRAT|VERPACKUNG|ARBEITSMATERIAL|SONSTIGES"),
        ("is_organic", "is_organic", False, "bool"),
        ("bio_kontrollstelle", "bio_kontrollstelle", False, "str"),
        ("notizen", "notizen", False, "str"),
    ],
    "seeds": [
        ("name", "name", True, "str"),
        ("sorte", "sorte", False, "str"),
        ("lieferant", "lieferant", False, "str"),
        ("keimdauer_tage", "keimdauer_tage", True, "int"),
        ("wachstumsdauer_tage", "wachstumsdauer_tage", True, "int"),
        ("erntefenster_min_tage", "erntefenster_min_tage", True, "int"),
        ("erntefenster_optimal_tage", "erntefenster_optimal_tage", True, "int"),
        ("erntefenster_max_tage", "erntefenster_max_tage", True, "int"),
        ("ertrag_gramm_pro_tray", "ertrag_gramm_pro_tray", True, "decimal"),
        ("verlustquote_prozent", "verlustquote_prozent", False, "decimal"),
        ("saatgut_pro_einheit_gramm", "saatgut_pro_einheit_gramm", False, "decimal"),
        ("cooling_days", "cooling_days", False, "int"),
        ("cooling_shelf_life_days", "cooling_shelf_life_days", False, "int"),
        ("process_type", "process_type", False, "enum:STANDARD|PLATTE|PLATTE_STEINE"),
    ],
    "products": [
        ("sku", "sku", True, "str"),
        ("name", "name", True, "str"),
        ("category", "category", True, "enum:MICROGREEN|SEED|PACKAGING|BUNDLE"),
        ("gtin", "gtin", False, "str"),
        ("old_article_number", "old_article_number", False, "str"),
        ("certification", "certification", False, "enum:BIO|KONVENTIONELL|TRANSITIONAL"),
        ("description", "description", False, "str"),
        ("base_price", "base_price", False, "decimal"),
        ("tax_rate", "tax_rate", False, "enum:REDUZIERT|STANDARD|STEUERFREI"),
        ("shelf_life_days", "shelf_life_days", False, "int"),
    ],
    "locations": [
        ("code", "code", True, "str"),
        ("name", "name", True, "str"),
        ("location_type", "location_type", True, "enum:LAGER|KUEHLRAUM|REGAL|KEIMRAUM|VERSAND"),
        ("description", "description", False, "str"),
        ("temperature_min", "temperature_min", False, "decimal"),
        ("temperature_max", "temperature_max", False, "decimal"),
    ],
}


def _coerce(value: Any, type_hint: str) -> Any:
    if value is None or value == "":
        return None
    try:
        if type_hint == "str":
            return str(value).strip() or None
        if type_hint == "int":
            return int(float(value))
        if type_hint == "decimal":
            return Decimal(str(value).replace(",", "."))
        if type_hint == "bool":
            s = str(value).strip().lower()
            return s in ("true", "1", "ja", "yes", "x")
        if type_hint.startswith("enum:"):
            valid = type_hint.split(":", 1)[1].split("|")
            v = str(value).strip().upper()
            return v if v in valid else None
    except (InvalidOperation, ValueError):
        return None
    return value


def _build_template(entity: str) -> bytes:
    cols = COLUMNS[entity]
    wb = Workbook()
    ws = wb.active
    ws.title = entity
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="166534")
    for idx, (header, _attr, required, type_hint) in enumerate(cols, start=1):
        cell = ws.cell(row=1, column=idx, value=f"{header}{' *' if required else ''}")
        cell.font = header_font
        cell.fill = header_fill
        comment = type_hint
        ws.cell(row=2, column=idx, value=f"[{comment}]")
        ws.column_dimensions[cell.column_letter].width = max(15, len(header) + 4)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@router.get("/template/{entity}")
def download_template(entity: str):
    if entity not in COLUMNS:
        raise HTTPException(status_code=404, detail=f"Unbekannte Entität: {entity}")
    data = _build_template(entity)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="template_{entity}.xlsx"'},
    )


def _parse_rows(file: UploadFile, entity: str) -> tuple[list[dict], list[str]]:
    """Liest XLSX, gibt (rows, errors) zurück."""
    cols = COLUMNS[entity]
    try:
        wb = load_workbook(io.BytesIO(file.file.read()), read_only=True, data_only=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Datei konnte nicht gelesen werden: {e}")
    ws = wb.active

    header_to_idx: dict[str, int] = {}
    for idx, cell in enumerate(next(ws.iter_rows(min_row=1, max_row=1, values_only=True))):
        if cell:
            header_to_idx[str(cell).split(" ")[0].strip().lower()] = idx

    rows: list[dict] = []
    errors: list[str] = []
    for row_num, raw_row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        # Skip type-hint row + completely empty rows
        if all(c is None or str(c).startswith("[") for c in raw_row):
            continue
        if all(c is None or str(c).strip() == "" for c in raw_row):
            continue
        record: dict[str, Any] = {}
        row_error = None
        for header, attr, required, type_hint in cols:
            col_idx = header_to_idx.get(header.lower())
            raw = raw_row[col_idx] if col_idx is not None and col_idx < len(raw_row) else None
            value = _coerce(raw, type_hint)
            if required and value is None:
                row_error = f"Zeile {row_num}: '{header}' fehlt"
                break
            record[attr] = value
        if row_error:
            errors.append(row_error)
            continue
        rows.append(record)
    return rows, errors


def _import_customers(db, rows: list[dict]) -> tuple[int, int]:
    created = updated = 0
    for r in rows:
        typ = CustomerType(r["typ"]) if r.get("typ") else CustomerType.GASTRO
        existing = db.execute(select(Customer).where(Customer.name == r["name"])).scalar_one_or_none()
        if existing:
            for k, v in r.items():
                if v is not None and k != "typ":
                    setattr(existing, k, v)
            existing.typ = typ
            updated += 1
        else:
            db.add(Customer(**{**r, "typ": typ}))
            created += 1
    db.commit()
    return created, updated


def _import_suppliers(db, rows: list[dict]) -> tuple[int, int]:
    created = updated = 0
    for r in rows:
        existing = db.execute(select(Supplier).where(Supplier.name == r["name"])).scalar_one_or_none()
        if existing:
            for k, v in r.items():
                if v is not None:
                    setattr(existing, k, v)
            updated += 1
        else:
            db.add(Supplier(**r))
            created += 1
    db.commit()
    return created, updated


def _import_seeds(db, rows: list[dict]) -> tuple[int, int]:
    created = updated = 0
    for r in rows:
        existing = db.execute(select(Seed).where(Seed.name == r["name"])).scalar_one_or_none()
        if existing:
            for k, v in r.items():
                if v is not None:
                    setattr(existing, k, v)
            updated += 1
        else:
            db.add(Seed(**r))
            created += 1
    db.commit()
    return created, updated


def _import_products(db, rows: list[dict]) -> tuple[int, int]:
    default_unit = db.execute(select(UnitOfMeasure).where(UnitOfMeasure.code == "G")).scalar_one_or_none()
    if not default_unit:
        raise HTTPException(status_code=500, detail="Basiseinheit 'G' fehlt — bitte Stammdaten initialisieren")
    created = updated = 0
    for r in rows:
        category = ProductCategory(r["category"]) if r.get("category") else ProductCategory.MICROGREEN
        tax_rate = TaxRate(r["tax_rate"]) if r.get("tax_rate") else TaxRate.REDUZIERT
        existing = db.execute(select(Product).where(Product.sku == r["sku"])).scalar_one_or_none()
        payload = {**r, "category": category, "tax_rate": tax_rate}
        if existing:
            for k, v in payload.items():
                if v is not None:
                    setattr(existing, k, v)
            updated += 1
        else:
            db.add(Product(**{**payload, "base_unit_id": default_unit.id}))
            created += 1
    db.commit()
    return created, updated


def _import_locations(db, rows: list[dict]) -> tuple[int, int]:
    created = updated = 0
    for r in rows:
        loc_type = LocationType(r["location_type"]) if r.get("location_type") else LocationType.LAGER
        existing = db.execute(select(InventoryLocation).where(InventoryLocation.code == r["code"])).scalar_one_or_none()
        payload = {**r, "location_type": loc_type}
        if existing:
            for k, v in payload.items():
                if v is not None:
                    setattr(existing, k, v)
            updated += 1
        else:
            db.add(InventoryLocation(**payload))
            created += 1
    db.commit()
    return created, updated


IMPORTERS = {
    "customers": _import_customers,
    "suppliers": _import_suppliers,
    "seeds": _import_seeds,
    "products": _import_products,
    "locations": _import_locations,
}


@router.post("/{entity}")
async def import_entity(entity: str, db: DBSession, file: UploadFile = File(...)):
    if entity not in IMPORTERS:
        raise HTTPException(status_code=404, detail=f"Unbekannte Entität: {entity}")
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Nur .xlsx/.xlsm Dateien werden unterstützt")
    rows, parse_errors = _parse_rows(file, entity)
    if not rows and parse_errors:
        return {"created": 0, "updated": 0, "errors": parse_errors}
    try:
        created, updated = IMPORTERS[entity](db, rows)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Import fehlgeschlagen: {e}")
    return {"created": created, "updated": updated, "errors": parse_errors}
