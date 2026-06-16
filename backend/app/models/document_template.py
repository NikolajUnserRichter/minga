"""Customizable Document-Templates pro Belegart.

Eine Row pro Belegart (RECHNUNG, AUFTRAGSBESTAETIGUNG, LIEFERSCHEIN,
VERPACKUNGSLISTE, MAHNUNG). Falls keine Row existiert, fällt der
PDFService auf den Code-Default zurück (Backwards-Compat).

Sections-Config + Column-Config sind JSON, damit das Frontend Toggle/
Reorder ohne neue DB-Migrationen unterstützen kann.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import String, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.types import Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentType(str, Enum):
    RECHNUNG            = "RECHNUNG"
    AUFTRAGSBESTAETIGUNG = "AUFTRAGSBESTAETIGUNG"
    LIEFERSCHEIN        = "LIEFERSCHEIN"
    VERPACKUNGSLISTE    = "VERPACKUNGSLISTE"
    MAHNUNG             = "MAHNUNG"


# Default-Sektionen je Belegart (Reihenfolge = Render-Reihenfolge)
DEFAULT_SECTIONS: dict[str, list[dict]] = {
    "RECHNUNG": [
        {"key": "header_logo",    "enabled": True,  "label": "Logo + Briefkopf"},
        {"key": "title",          "enabled": True,  "label": "Titel + Rechnungsnummer"},
        {"key": "meta_block",     "enabled": True,  "label": "Datum + Kunde + Anschrift"},
        {"key": "lines_table",    "enabled": True,  "label": "Positions-Tabelle"},
        {"key": "totals_block",   "enabled": True,  "label": "Netto/MwSt/Gesamt-Summe"},
        {"key": "skonto_hint",    "enabled": True,  "label": "Skonto-Hinweis (wenn Kunde-Skonto > 0)"},
        {"key": "reverse_charge", "enabled": True,  "label": "Reverse-Charge §13b (bei STEUERFREI)"},
        {"key": "ownership",      "enabled": True,  "label": "Eigentumsvorbehalt"},
        {"key": "thanks",         "enabled": True,  "label": "Danke-Text"},
        {"key": "footer",         "enabled": True,  "label": "Footer (Firma + Bank)"},
    ],
    "AUFTRAGSBESTAETIGUNG": [
        {"key": "header_logo",  "enabled": True, "label": "Logo + Briefkopf"},
        {"key": "title",        "enabled": True, "label": "Titel + AB-Nummer"},
        {"key": "meta_block",   "enabled": True, "label": "Bestellung + Kunde + Lieferdatum"},
        {"key": "lines_table",  "enabled": True, "label": "Positions-Tabelle mit Preisen"},
        {"key": "totals_block", "enabled": True, "label": "Summen"},
        {"key": "confirm_text", "enabled": True, "label": "Bestätigungs-Text"},
        {"key": "footer",       "enabled": True, "label": "Footer"},
    ],
    "LIEFERSCHEIN": [
        {"key": "header_logo", "enabled": True,  "label": "Logo + Briefkopf"},
        {"key": "title",       "enabled": True,  "label": "Titel + LS-Nummer"},
        {"key": "meta_block",  "enabled": True,  "label": "Bestellung + Lieferadresse"},
        {"key": "lines_table", "enabled": True,  "label": "Positions-Tabelle (Charge+MHD)"},
        {"key": "signature",   "enabled": True,  "label": "Unterschrifts-Block Empfänger"},
        {"key": "footer",      "enabled": True,  "label": "Footer"},
    ],
    "VERPACKUNGSLISTE": [
        {"key": "header_logo",   "enabled": True,  "label": "Logo + Briefkopf"},
        {"key": "title",         "enabled": True,  "label": "Titel + PL-Nummer"},
        {"key": "meta_block",    "enabled": True,  "label": "Bestellung + Lieferadresse"},
        {"key": "products_table", "enabled": True, "label": "Produkt-Positionen"},
        {"key": "containers",    "enabled": True,  "label": "Pfand-/Mehrweg-Container"},
        {"key": "summary",       "enabled": True,  "label": "Gesamtgewicht + Anzahl Packstücke"},
        {"key": "footer",        "enabled": True,  "label": "Footer"},
    ],
    "MAHNUNG": [
        {"key": "header_logo",  "enabled": True, "label": "Logo + Briefkopf"},
        {"key": "title",        "enabled": True, "label": "Titel (Erinnerung/1./2. Mahnung)"},
        {"key": "meta_block",   "enabled": True, "label": "Rechnungs-Referenz + Kunde + Tage überfällig"},
        {"key": "body_text",    "enabled": True, "label": "Anschreibens-Text"},
        {"key": "amount_block", "enabled": True, "label": "Offener Betrag + Mahngebühr"},
        {"key": "regards",      "enabled": True, "label": "Grußformel"},
        {"key": "footer",       "enabled": True, "label": "Footer (mit IBAN)"},
    ],
}


# Default-Spalten je Belegart-Positions-Tabelle (column_config)
DEFAULT_COLUMNS: dict[str, list[dict]] = {
    "RECHNUNG":    [{"key": "pos",  "label": "Pos",  "enabled": True},
                    {"key": "desc", "label": "Beschreibung", "enabled": True},
                    {"key": "qty",  "label": "Menge", "enabled": True},
                    {"key": "unit", "label": "Einheit", "enabled": True},
                    {"key": "unit_price", "label": "Einzelpreis", "enabled": True},
                    {"key": "line_net",   "label": "Gesamt (Netto)", "enabled": True}],
    "AUFTRAGSBESTAETIGUNG": [{"key": "pos",  "label": "Pos",  "enabled": True},
                             {"key": "desc", "label": "Beschreibung", "enabled": True},
                             {"key": "qty",  "label": "Menge", "enabled": True},
                             {"key": "unit", "label": "Einheit", "enabled": True},
                             {"key": "unit_price", "label": "Einzelpreis", "enabled": True},
                             {"key": "line_net",   "label": "Gesamt (Netto)", "enabled": True}],
    "LIEFERSCHEIN": [{"key": "pos",    "label": "Pos",    "enabled": True},
                     {"key": "desc",   "label": "Beschreibung", "enabled": True},
                     {"key": "qty",    "label": "Menge", "enabled": True},
                     {"key": "unit",   "label": "Einheit", "enabled": True},
                     {"key": "batch",  "label": "Charge", "enabled": True},
                     {"key": "mhd",    "label": "MHD", "enabled": True}],
    "VERPACKUNGSLISTE": [{"key": "pos",   "label": "Pos",    "enabled": True},
                         {"key": "name",  "label": "Produkt", "enabled": True},
                         {"key": "qty",   "label": "Menge", "enabled": True},
                         {"key": "unit",  "label": "Einheit", "enabled": True},
                         {"key": "batch", "label": "Charge", "enabled": True}],
    "MAHNUNG": [],
}


# Default-Textfelder (Free-Text mit Placeholder-Support)
DEFAULT_TEXTS: dict[str, dict[str, str]] = {
    "RECHNUNG": {
        "header_text":  "",  # leer = Firmenname-Default aus Settings
        "thanks_text":  "Vielen Dank für Ihren Auftrag!",
        "ownership_text": "Ware bleibt bis zur vollständigen Bezahlung unser Eigentum (Eigentumsvorbehalt).",
        "footer_text":  "",  # leer = automatischer Footer aus COMPANY_* Settings
    },
    "AUFTRAGSBESTAETIGUNG": {
        "header_text":  "",
        "confirm_text": "Wir bestätigen hiermit Ihren Auftrag wie oben aufgeführt.",
        "footer_text":  "",
    },
    "LIEFERSCHEIN": {
        "header_text":   "",
        "signature_hint": "Bitte prüfen Sie die Ware bei Annahme und quittieren Sie den Empfang.",
        "footer_text":   "",
    },
    "VERPACKUNGSLISTE": {
        "header_text": "",
        "footer_text": "",
    },
    "MAHNUNG": {
        "header_text": "",
        "footer_text": "",
    },
}


class DocumentTemplate(Base):
    """Template-Konfiguration pro Belegart."""
    __tablename__ = "document_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_type: Mapped[DocumentType] = mapped_column(
        SQLEnum(DocumentType), nullable=False, unique=True, index=True
    )

    # Logo (FK auf bestehende attachments-Tabelle, polymorph entity_type=document_template)
    logo_attachment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("attachments.id", ondelete="SET NULL")
    )

    # Frei editierbare Texte (Placeholder erlaubt: {customer_name}, {invoice_number}, …)
    texts: Mapped[Optional[dict]] = mapped_column(JSON)
    # Sektionen-Liste mit enabled+key+order
    sections: Mapped[Optional[list]] = mapped_column(JSON)
    # Spalten-Liste mit enabled+key+label+order
    columns: Mapped[Optional[list]] = mapped_column(JSON)
    # Farben (Hex)
    primary_color: Mapped[Optional[str]] = mapped_column(String(7))   # #166534
    accent_color: Mapped[Optional[str]] = mapped_column(String(7))    # #6b7280

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    logo_attachment = relationship("Attachment", foreign_keys=[logo_attachment_id])
