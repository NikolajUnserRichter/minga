"""Steuersatzregeln für Bestell- und Rechnungspositionen und den Produktstamm.

Gernot-Feedback 08.10.2026, A3: Pfandkisten liefen mit 7 % statt 19 %. Der
Produktstamm stand korrekt auf 19 %, aber das Bestellformular schickte fest
REDUZIERT, das Schema setzte REDUZIERT als Default, und die Rechnung aus der
Bestellung übernahm den Satz der Bestellposition.

Regeln:
- Position mit Produkt (direkt oder über eine Verpackungsvariante): der Satz
  des Produktstamms ist verbindlich. Ein mitgeschickter Satz zählt nicht.
- Freitextposition (weder Produkt noch Variante): der Satz vom Client; ohne
  Angabe 7 % (Lebensmittel).

Nicht hier: InvoiceService.add_line. Der Storno (cancel_invoice) ruft add_line
mit product_id und dem Satz der Originalzeile auf — würde add_line den
Produktsatz erzwingen, ergäbe der Storno einer alten 7-%-Pfandrechnung nicht
null.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import TaxRate
from app.models.product import Product, ProductVariant

#: Satz für Freitextpositionen ohne Angabe — Lebensmittel.
FREITEXT_STANDARD = TaxRate.REDUZIERT


def produkt_der_position(
    db: Session,
    product_id: Optional[UUID],
    product_variant_id: Optional[UUID],
) -> Optional[Product]:
    """Das Produkt hinter einer Position: direkt oder über die Variante."""
    if product_id:
        return db.get(Product, product_id)
    if product_variant_id:
        variante = db.get(ProductVariant, product_variant_id)
        return variante.parent_product if variante else None
    return None


def steuersatz_der_position(
    db: Session,
    product_id: Optional[UUID],
    product_variant_id: Optional[UUID],
    client_satz: Optional[TaxRate],
) -> TaxRate:
    """Verbindlicher Satz einer Bestellposition (siehe Modul-Docstring)."""
    produkt = produkt_der_position(db, product_id, product_variant_id)
    if produkt is not None and produkt.tax_rate is not None:
        return produkt.tax_rate
    return client_satz or FREITEXT_STANDARD
