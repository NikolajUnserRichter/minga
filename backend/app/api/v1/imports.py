"""Excel-Upload für Stammdaten + Template-Download.

Endpoints:
- GET  /imports/template/{entity}   → XLSX mit Header-Zeile + Beispiel
- POST /imports/{entity}            → Multipart-Upload, parst Rows + upsertet

Unterstützte entities: customers, seeds, products, suppliers, locations
"""
from __future__ import annotations

import io
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Sequence
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy import func, select

from app.api.deps import DBSession
from app.models.customer import Customer, CustomerType
from app.models.seed import Seed, Supplier
from app.models.product import Product, ProductCategory
from app.models.inventory import InventoryLocation, LocationType
from app.models.unit import UnitOfMeasure
from app.models.enums import TaxRate
from app.models.order import Order, OrderLine, OrderStatus

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
    "order_history": [
        ("bestell_nr_extern", "bestell_nr_extern", True, "str"),
        ("kunde", "kunde", True, "str"),
        ("bestelldatum", "bestelldatum", True, "date"),
        ("lieferdatum", "lieferdatum", True, "date"),
        ("produkt_sku", "produkt_sku", True, "str"),
        ("menge", "menge", True, "decimal"),
        ("einheit", "einheit", False, "str"),
        ("einzelpreis", "einzelpreis", True, "decimal"),
        ("status", "status", False, "enum:ENTWURF|BESTAETIGT|IN_PRODUKTION|GELIEFERT|FAKTURIERT|STORNIERT"),
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
        if type_hint == "date":
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            s = str(value).strip()
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(s, fmt).date()
                except ValueError:
                    continue
            return None
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


def _generate_historic_order_number(db, order_date: date, used_numbers: set[str]) -> str:
    """Generiert BE-YYYYMMDD-NNNN für ein historisches Datum.

    Berücksichtigt sowohl bereits existierende DB-Nummern als auch
    Nummern, die in dieser Import-Transaktion bereits vergeben wurden
    (used_numbers), damit Massenimporte kollisionsfrei bleiben."""
    prefix = f"BE-{order_date.strftime('%Y%m%d')}"
    last = db.execute(
        select(Order)
        .where(Order.order_number.like(f"{prefix}-%"))
        .order_by(Order.order_number.desc())
        .limit(1)
    ).scalar_one_or_none()
    next_num = (int(last.order_number.split("-")[-1]) + 1) if last else 1
    while f"{prefix}-{next_num:04d}" in used_numbers:
        next_num += 1
    number = f"{prefix}-{next_num:04d}"
    used_numbers.add(number)
    return number


def _import_order_history(db, rows: list[dict]) -> tuple[int, int]:
    """Importiert historische Bestellungen für Forecast-Training.

    Gruppiert Zeilen nach `bestell_nr_extern` → eine Bestellung pro Gruppe.
    Idempotent über customer_reference (re-runs überspringen vorhandene)."""
    if not rows:
        return 0, 0

    # 1) Gruppieren
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["bestell_nr_extern"]].append(r)

    # 2) Customer-Cache (case-insensitive Name-Lookup)
    customers_by_name: dict[str, Customer] = {}
    products_by_sku: dict[str, Product] = {}

    def _get_customer(name: str) -> Optional[Customer]:
        key = name.strip().lower()
        if key in customers_by_name:
            return customers_by_name[key]
        c = db.execute(
            select(Customer).where(func.lower(Customer.name) == key)
        ).scalar_one_or_none()
        if c:
            customers_by_name[key] = c
        return c

    def _get_product(sku: str) -> Optional[Product]:
        if sku in products_by_sku:
            return products_by_sku[sku]
        p = db.execute(select(Product).where(Product.sku == sku)).scalar_one_or_none()
        if p:
            products_by_sku[sku] = p
        return p

    created = skipped = 0
    used_numbers: set[str] = set()
    for ext_nr, group_rows in groups.items():
        # Idempotenz: gleicher customer_reference schon importiert → skip
        existing = db.execute(
            select(Order).where(Order.customer_reference == ext_nr).limit(1)
        ).scalar_one_or_none()
        if existing:
            skipped += 1
            continue

        head = group_rows[0]
        customer = _get_customer(head["kunde"])
        if not customer:
            raise HTTPException(
                status_code=400,
                detail=f"Bestellung '{ext_nr}': Kunde '{head['kunde']}' nicht gefunden — bitte zuerst Stammdaten importieren",
            )

        status_str = head.get("status") or "GELIEFERT"
        try:
            order_status = OrderStatus(status_str)
        except ValueError:
            order_status = OrderStatus.GELIEFERT

        order_number = _generate_historic_order_number(db, head["bestelldatum"], used_numbers)

        order = Order(
            order_number=order_number,
            customer_id=customer.id,
            customer_reference=ext_nr,
            order_date=datetime.combine(head["bestelldatum"], datetime.min.time()),
            requested_delivery_date=head["lieferdatum"],
            actual_delivery_date=head["lieferdatum"] if order_status == OrderStatus.GELIEFERT else None,
            status=order_status,
            currency="EUR",
            total_net=Decimal("0"),
            total_vat=Decimal("0"),
            total_gross=Decimal("0"),
            discount_percent=Decimal("0"),
            discount_amount=Decimal("0"),
        )
        db.add(order)
        db.flush()  # order.id verfügbar machen

        for position, line_row in enumerate(group_rows, start=1):
            product = _get_product(line_row["produkt_sku"])
            if not product:
                raise HTTPException(
                    status_code=400,
                    detail=f"Bestellung '{ext_nr}': SKU '{line_row['produkt_sku']}' nicht gefunden",
                )
            line = OrderLine(
                order_id=order.id,
                position=position,
                product_id=product.id,
                product_sku=product.sku,
                product_name=product.name,
                quantity=line_row["menge"],
                unit=line_row.get("einheit") or "g",
                unit_price=line_row["einzelpreis"],
                discount_percent=Decimal("0"),
                tax_rate=product.tax_rate or TaxRate.REDUZIERT,
            )
            line.calculate_line_totals()
            db.add(line)
            order.lines.append(line)

        order.calculate_totals()
        created += 1

    db.commit()
    return created, skipped


IMPORTERS = {
    "customers": _import_customers,
    "suppliers": _import_suppliers,
    "seeds": _import_seeds,
    "products": _import_products,
    "locations": _import_locations,
    "order_history": _import_order_history,
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
