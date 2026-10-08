"""Steuersatzregeln für Bestell- und Rechnungspositionen und den Produktstamm.

Gernot-Feedback 08.10.2026, A3: Pfandkisten liefen mit 7 % statt 19 %. Der
Produktstamm stand korrekt auf 19 %, aber das Bestellformular schickte fest
REDUZIERT, das Schema setzte REDUZIERT als Default, und die Rechnung aus der
Bestellung übernahm den Satz der Bestellposition.

Regeln:

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -k TestS1Produktstamm -v`
Erwartet: **5 failed, 3 passed.**
- Fehlschläge:
  - `…pfandkennzeichen…`: `'REDUZIERT' == 'STANDARD'`
  - `…kategorie_pfand…`: `'PACKAGING' == 'PFAND'`, weil der PATCH die Kategorie verwirft
  - `…leerer_kategorie…`: `assert 200 == 422`, weil der PATCH das Feld heute still verwirft. Ohne den Validator aus Step 4 käme nach dem Fix ein Datenbankfehler statt 422.
  - `…reimport…`: `'REDUZIERT' == 'STANDARD'`
  - `…neuer_pfandartikel…`: `assert False is True`. Er scheitert schon an der Zeile `assert p["is_deposit"] is True`, vor der Satzprüfung: Der Import setzt heute für `category=PFAND` kein Pfandkennzeichen.
- Grün schon jetzt: `…ausdruecklicher_satz…`, `…kippt_den_satz_nicht` und `…ohne_kategorie…`. Sie sichern ab, dass die Regel nicht zu weit greift.

- [ ] **Step 3: `pfand_vorgaben` in `steuersatz.py`**

Import ergänzen: `from app.models.product import Product, ProductCategory, ProductVariant`. Im Modul-Docstring unter „Regeln:“ ergänzen:

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
from app.models.product import Product, ProductCategory, ProductVariant

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


def pfand_vorgaben(
    werte: dict,
    explizit: set[str],
    bisher: Optional[Product] = None,
) -> dict:
    """Pfandregel für Anlegen (bisher=None), Ändern und Import eines Produkts.

    - Kategorie PFAND heißt: das ist ein Pfandgebinde. Ohne ausdrückliche
      Angabe wird das Pfandkennzeichen gesetzt.
    - Wird ein Artikel zum Pfandartikel, gilt der Regelsatz 19 % — Pfand auf
      Mehrweggebinde ist kein Lebensmittelumsatz. Ein ausdrücklich
      mitgeschickter Satz bleibt unangetastet.
    - Beim Ändern zählt nur der Übergang. Ist der Artikel schon Pfand bzw.
      schon PFAND, wird nichts nachgezogen — sonst überschriebe jedes
      Speichern einen bewusst gewählten Satz.

    Gibt eine Kopie von `werte` zurück; `explizit` sind die Felder, die der
    Aufrufer ausdrücklich angegeben hat.
    """
    werte = dict(werte)
    wird_pfandkategorie = werte.get("category") == ProductCategory.PFAND and (
        bisher is None or bisher.category != ProductCategory.PFAND
    )
    if wird_pfandkategorie and "is_deposit" not in explizit:
        werte["is_deposit"] = True
    wird_pfand = bool(werte.get("is_deposit")) and (bisher is None or not bisher.is_deposit)
    if wird_pfand and "tax_rate" not in explizit:
        werte["tax_rate"] = TaxRate.STANDARD
    return werte
