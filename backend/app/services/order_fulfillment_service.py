"""Order-Fulfillment: Inventory-Deduction beim GELIEFERT-Trigger.

Wird aufgerufen sobald eine Order in den Status GELIEFERT übergeht
(via status-update-Endpoint ODER via delivery-note mark-delivered).

Logik:
- Reguläre Produkt-Line → Bestand des Produkts reduzieren
- FIXED-Bundle (is_bundle=True) → Bestand jeder Bundle-Komponente reduzieren
  (qty_per_bundle * line.quantity)
- VARIABLE-Bundle (is_variable_bundle=True) → Bestand jeder gewählten Sorte
  reduzieren (selection.quantity * line.quantity)

Idempotenz: Order.inventory_deducted_at wird gesetzt. Mehrfach-Aufrufe
sind no-ops.

Unit-Behandlung: aktuell werden nur Gramm-Mengen vom finished_goods_g
abgezogen. STK/SCHALE/TRAY werden geloggt, aber nicht abgezogen (würde
einen Verpackungs-Multiplikator brauchen — Folgewave).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Order, OrderLine
from app.models.product import Product, BundleComponent
from app.models.inventory import (
    FinishedGoodsInventory, InventoryMovement, MovementType, InventoryItemType,
)

logger = logging.getLogger(__name__)


# Einheits-Multiplikatoren für Umrechnung in Gramm
_UNIT_TO_GRAMS = {
    "g":  Decimal("1"),
    "G":  Decimal("1"),
    "kg": Decimal("1000"),
    "KG": Decimal("1000"),
}


def _to_grams(qty: Decimal, unit: str) -> Optional[Decimal]:
    """Konvertiert Menge nach Gramm. Gibt None zurück wenn nicht möglich."""
    mult = _UNIT_TO_GRAMS.get(unit)
    if mult is None:
        return None
    return qty * mult


def _deduct_from_finished_goods(
    db: Session,
    product_id: UUID,
    qty_grams: Decimal,
    order: Order,
    line: Optional[OrderLine],
) -> bool:
    """Bucht den Abgang aus dem ältesten Bestand desselben Produkts (FIFO).

    Wenn der Bestand auf mehrere Chargen aufgeteilt ist, durchläuft die
    Funktion sie in Reihenfolge des Anlegedatums.
    """
    remaining = qty_grams
    # with_for_update() lockt die selektierten Rows bis zum Commit der
    # umgebenden Transaktion. Schützt gegen Race-Conditions zwischen
    # parallelen GELIEFERT-Übergängen (zwei Worker dedukten sonst beide
    # vom gleichen Bestand und verbrauchen ihn doppelt).
    # SQLite: no-op (alle TX seriell), PostgreSQL: row-level lock.
    inventories = db.execute(
        select(FinishedGoodsInventory)
        .where(
            FinishedGoodsInventory.product_id == product_id,
            FinishedGoodsInventory.current_quantity_g > 0,
        )
        .order_by(FinishedGoodsInventory.created_at.asc())
        .with_for_update()
    ).scalars().all()

    if not inventories:
        logger.warning(
            "Inventory-Deduction: kein Bestand für product_id=%s (qty=%sg). "
            "Buche keine Reduktion (Order=%s).",
            product_id, qty_grams, order.order_number
        )
        return False

    for inv in inventories:
        if remaining <= 0:
            break
        before = inv.current_quantity_g
        deduct = min(remaining, before)
        inv.current_quantity_g = before - deduct
        movement = InventoryMovement(
            movement_type=MovementType.AUSGANG,
            item_type=InventoryItemType.FERTIGWARE,
            finished_goods_id=inv.id,
            quantity=-deduct,
            unit="g",
            quantity_before=before,
            quantity_after=inv.current_quantity_g,
            order_id=order.id,
            order_item_id=line.id if line else None,
        )
        db.add(movement)
        remaining -= deduct

    if remaining > 0:
        logger.warning(
            "Inventory-Deduction: nur %sg von %sg verbucht (kein Bestand mehr). "
            "Order=%s, Produkt=%s.",
            (qty_grams - remaining), qty_grams, order.order_number, product_id
        )
    return True


def deduct_inventory_for_order(db: Session, order: Order, *, dry_run: bool = False, commit: bool = True) -> dict:
    """Hauptfunktion. Idempotent. Gibt eine Zusammenfassung zurück.

    Mit commit=False bleibt die Transaction offen — der Aufrufer ist
    verantwortlich, die Status-Änderung und den Inventory-Abzug atomar zu
    committen. Damit wird vermieden, dass der Order-Status auf GELIEFERT
    steht, der Bestand aber noch nicht abgezogen wurde (oder umgekehrt).
    """
    if order.inventory_deducted_at and not dry_run:
        return {"status": "skipped", "reason": "bereits gebucht", "at": str(order.inventory_deducted_at)}

    deductions = []
    warnings = []

    for line in order.lines:
        if not line.product_id:
            continue
        product = db.get(Product, line.product_id)
        if not product:
            warnings.append(f"Produkt {line.product_id} nicht gefunden")
            continue

        # FIXED-Bundle: Komponenten ausbuchen
        if product.is_bundle and not product.is_variable_bundle:
            components = db.execute(
                select(BundleComponent).where(BundleComponent.parent_product_id == product.id)
            ).scalars().all()
            if not components:
                warnings.append(f"Bundle {product.sku} hat keine Komponenten konfiguriert")
                continue
            for comp in components:
                qty_per_bundle = Decimal(str(comp.quantity or 1))
                comp_qty_grams = _to_grams(line.quantity * qty_per_bundle, line.unit or "g")
                if comp_qty_grams is None:
                    warnings.append(f"Einheit '{line.unit}' kann nicht in Gramm umgerechnet werden (Position {line.position})")
                    continue
                if not dry_run:
                    _deduct_from_finished_goods(db, comp.child_product_id, comp_qty_grams, order, line)
                deductions.append({
                    "type": "bundle_component",
                    "parent_sku": product.sku,
                    "child_product_id": str(comp.child_product_id),
                    "quantity_g": str(comp_qty_grams),
                })

        # VARIABLE-Bundle: Sorten-Auswahl ausbuchen
        elif product.is_variable_bundle:
            selections = line.variable_bundle_selections or []
            if not selections:
                warnings.append(f"Variable Bundle {product.sku} ohne Sorten-Auswahl")
                continue
            for sel in selections:
                child_pid = sel.get("product_id")
                child_qty = Decimal(str(sel.get("quantity", 1) or 1))
                if not child_pid:
                    continue
                # Variable-Bundle-Slots haben keinen fest definierten g/Slot-Wert,
                # solange ProductVariant nicht eindeutig auf den Sorten-Bestand
                # mappt. Statt 100g hart anzunehmen und damit Bestand systematisch
                # falsch zu reduzieren, melden wir das laut und überspringen den
                # Abzug. Die Folgewave nimmt items_per_pack/Tray-Gewicht aus dem
                # ProductVariant-Mapping.
                msg = (
                    f"Variable-Bundle '{product.sku}' Sorte product_id={child_pid}: "
                    f"Abzug übersprungen — pro-Slot-Gewicht nicht definiert. "
                    f"Bitte manuell korrigieren oder Sorten-Variante pflegen."
                )
                logger.warning(msg)
                warnings.append(msg)
                deductions.append({
                    "type": "variable_bundle_sort",
                    "bundle_sku": product.sku,
                    "child_product_id": str(child_pid),
                    "quantity_g": None,
                    "skipped": True,
                })

        # Reguläres Produkt
        else:
            qty_grams = _to_grams(line.quantity, line.unit or "g")
            if qty_grams is None:
                warnings.append(f"Einheit '{line.unit}' kann nicht in Gramm umgerechnet werden (Position {line.position})")
                continue
            if not dry_run:
                _deduct_from_finished_goods(db, product.id, qty_grams, order, line)
            deductions.append({
                "type": "product",
                "sku": product.sku,
                "quantity_g": str(qty_grams),
            })

    if not dry_run:
        order.inventory_deducted_at = datetime.now(timezone.utc)
        if commit:
            db.commit()
        # sonst: Aufrufer committet zusammen mit dem Status-Change

    return {
        "status": "ok",
        "deductions": deductions,
        "warnings": warnings,
        "dry_run": dry_run,
    }
