"""Helpers für Document-Templates:
1. Placeholder-Resolution in Texten
2. Dummy-Datensätze für Preview-PDFs

Die Dummy-Builder erzeugen In-Memory-Objekte (kein DB-Write), damit der
Editor live ein PDF rendern kann ohne echte Bestellungen anlegen zu müssen.
"""
from __future__ import annotations

from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Optional
import re
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.document_template import DocumentTemplate, DocumentType
from app.models.enums import TaxRate, ConfirmationStatus, DeliveryNoteStatus, OrderStatus
from app.models.invoice import InvoiceType


# ---------- Placeholder-Replacement ---------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def apply_placeholders(text: Optional[str], context: dict) -> str:
    """Ersetzt {key} in `text` durch context[key] (oder lässt es stehen)."""
    if not text:
        return ""
    def _sub(m):
        key = m.group(1)
        return str(context.get(key, m.group(0)))
    return _PLACEHOLDER_RE.sub(_sub, text)


def load_template(db: Session, document_type: DocumentType) -> Optional[DocumentTemplate]:
    """Lädt das Template für einen Belegtyp oder None (Code-Default greift)."""
    from sqlalchemy import select
    return db.execute(
        select(DocumentTemplate).where(DocumentTemplate.document_type == document_type)
    ).scalar_one_or_none()


def section_enabled(tmpl: Optional[DocumentTemplate], section_key: str, *, default: bool = True) -> bool:
    """True wenn die Sektion gerendert werden soll. Default = aktiv."""
    if not tmpl or not tmpl.sections:
        return default
    for s in tmpl.sections:
        if s.get("key") == section_key:
            return bool(s.get("enabled", True))
    return default


def get_columns(tmpl: Optional[DocumentTemplate], default_columns: list[dict]) -> list[dict]:
    """Liefert die aktiven Spalten als Liste, fallback auf Defaults."""
    if not tmpl or not tmpl.columns:
        return [c for c in default_columns if c.get("enabled", True)]
    return [c for c in tmpl.columns if c.get("enabled", True)]


def get_text(tmpl: Optional[DocumentTemplate], key: str, default: str, context: Optional[dict] = None) -> str:
    """Liefert den Custom-Text aus dem Template oder den Default. Wendet Placeholder an."""
    raw = default
    if tmpl and tmpl.texts and tmpl.texts.get(key):
        raw = tmpl.texts[key]
    return apply_placeholders(raw, context or {})


def get_logo_path(db: Session, tmpl: Optional[DocumentTemplate]) -> Optional[str]:
    """Liefert den absoluten Filesystem-Pfad zum Logo, falls hochgeladen."""
    if not tmpl or not tmpl.logo_attachment_id:
        return None
    from app.models.attachment import Attachment
    att = db.get(Attachment, tmpl.logo_attachment_id)
    if not att:
        return None
    from app.services.storage_service import get_storage
    storage = get_storage()
    resolver = getattr(storage, "resolve_path", None)
    if resolver is None:
        return None  # S3 oder anderes Backend → ReportLab kann keinen Pfad nutzen
    path = resolver(att.storage_key)
    return str(path) if path else None


# ---------- Dummy-Builder für Live-Preview --------------------------------

def _dummy_customer():
    return SimpleNamespace(
        id=uuid4(),
        name="Beispiel-Kunde GmbH",
        customer_number="KD-99999",
        email="kontakt@beispiel.de",
        skonto_percent=Decimal("2.0"),
        skonto_days=10,
        discount_percent=Decimal("3.8"),
        packaging_fee_amount=Decimal("5.00"),
        billing_address=SimpleNamespace(
            strasse="Beispielstraße",
            hausnummer="42",
            plz="80331",
            ort="München",
            land="DE",
        ),
        shipping_address=None,
    )


def _dummy_lines(count: int = 3):
    """Erzeugt OrderLine-ähnliche SimpleNamespaces."""
    return [
        SimpleNamespace(
            id=uuid4(),
            position=i + 1,
            product_id=uuid4(),
            beschreibung=name,
            description=name,
            quantity=Decimal(str(qty)),
            unit="STK",
            unit_price=Decimal(str(price)),
            line_total=Decimal(str(qty * price)).quantize(Decimal("0.01")),
            line_net=Decimal(str(qty * price)).quantize(Decimal("0.01")),
            line_vat=(Decimal(str(qty * price)) * Decimal("0.07")).quantize(Decimal("0.01")),
            line_gross=(Decimal(str(qty * price)) * Decimal("1.07")).quantize(Decimal("0.01")),
            discount_percent=Decimal("0"),
            tax_rate=TaxRate.REDUZIERT,
            batch_number=f"H-2026-{100 + i}",
            harvest=None,
        )
        for i, (name, qty, price) in enumerate([
            ("Sonnenblume Microgreens 80g", 5, 3.50),
            ("Erbsensprossen 100g", 3, 3.20),
            ("Radieschen Microgreens 80g", 2, 3.80),
        ])
    ]


def _dummy_order(with_lines: bool = True):
    o = SimpleNamespace(
        id=uuid4(),
        order_number="BE-20260616-0099",
        customer=_dummy_customer(),
        customer_id=None,
        order_date=datetime.now(timezone.utc),
        requested_delivery_date=date.today() + timedelta(days=2),
        delivery_address={"strasse": "Beispielstraße", "hausnummer": "42", "plz": "80331", "ort": "München"},
        billing_address={"strasse": "Beispielstraße", "hausnummer": "42", "plz": "80331", "ort": "München"},
        lines=_dummy_lines() if with_lines else [],
        total_net=Decimal("25.40"),
        total_vat=Decimal("1.78"),
        total_gross=Decimal("27.18"),
        currency="EUR",
        discount_percent=Decimal("0"),
        discount_amount=Decimal("0"),
        status=OrderStatus.ENTWURF,
        actual_delivery_date=None,
    )
    return o


def build_dummy_invoice():
    """Invoice-ähnlich (für generate_invoice_pdf)."""
    cust = _dummy_customer()
    lines = _dummy_lines()
    subtotal = sum(l.line_net for l in lines)
    tax = sum(l.line_vat for l in lines)
    return SimpleNamespace(
        id=uuid4(),
        invoice_number="RE-2026-99999",
        invoice_type=InvoiceType.RECHNUNG,
        customer=cust,
        customer_id=None,
        order_id=None,
        invoice_date=date.today(),
        delivery_date=date.today() - timedelta(days=2),
        due_date=date.today() + timedelta(days=14),
        billing_address=None,
        shipping_address=None,
        subtotal=subtotal,
        discount_percent=Decimal("0"),
        discount_amount=Decimal("0"),
        tax_amount=tax,
        total=(subtotal + tax),
        paid_amount=Decimal("0"),
        currency="EUR",
        lines=lines,
        reminder_level=0,
    )


def build_dummy_confirmation():
    order = _dummy_order()
    return SimpleNamespace(
        id=uuid4(),
        confirmation_number="AB-20260616-0099",
        order=order,
        order_id=order.id,
        notes=None,
        status=ConfirmationStatus.ENTWURF,
    )


def build_dummy_delivery_note():
    order = _dummy_order()
    note = SimpleNamespace(
        id=uuid4(),
        delivery_note_number="LS-20260616-0099",
        order=order,
        order_id=order.id,
        notes=None,
        status=DeliveryNoteStatus.ENTWURF,
        packing_list=None,
    )
    return note


def build_dummy_packing_list():
    note = build_dummy_delivery_note()
    items = [
        SimpleNamespace(
            id=uuid4(),
            sort_order=1,
            product_name="Sonnenblume Microgreens 80g",
            quantity=Decimal("5"),
            unit="STK",
            batch_number="H-2026-100",
            is_returnable_container=False,
            container_type=None,
            container_count=None,
        ),
        SimpleNamespace(
            id=uuid4(),
            sort_order=2,
            product_name="Mehrwegkiste 12-Fach",
            quantity=Decimal("2"),
            unit="STK",
            batch_number=None,
            is_returnable_container=True,
            container_type="KISTE_12",
            container_count=2,
        ),
    ]
    pl = SimpleNamespace(
        id=uuid4(),
        packing_list_number="PL-20260616-0099",
        delivery_note=note,
        items=items,
        total_weight_g=Decimal("400.0"),
        total_packages=2,
        notes=None,
    )
    note.packing_list = pl
    return pl


def build_dummy_for_reminder():
    return build_dummy_invoice()
