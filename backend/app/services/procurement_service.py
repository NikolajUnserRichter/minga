"""
Procurement-Service — Business-Logik für Einkauf/Wareneingang.

Kapselt Bestellanlage (inkl. fortlaufender EK-Nummer), Summenberechnung
und Wareneingangs-Verbuchung (Teil-/Vollmengen + Statuswechsel).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.invoice import TaxRate
from app.models.inventory import InventoryItemType, InventoryMovement, MovementType
from app.models.procurement import (
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    TradeGoodsInventory,
)


class ProcurementService:
    def __init__(self, db: Session):
        self.db = db

    # ---------- Nummernkreis ----------

    def _next_po_number(self) -> str:
        """Fortlaufende EK-Nummer im Format EK-{Jahr}-{4-stellig}."""
        year = datetime.now(timezone.utc).year
        prefix = f"EK-{year}-"
        count = self.db.execute(
            select(func.count())
            .select_from(PurchaseOrder)
            .where(PurchaseOrder.po_number.like(f"{prefix}%"))
        ).scalar() or 0
        return f"{prefix}{count + 1:04d}"

    # ---------- Bestellung anlegen ----------

    def create_purchase_order(
        self,
        *,
        supplier_id: UUID,
        lines: Sequence[dict],
        requested_delivery_date: Optional[date] = None,
        supplier_reference: Optional[str] = None,
        notes: Optional[str] = None,
        internal_notes: Optional[str] = None,
        discount_percent: Decimal = Decimal("0.00"),
        currency: str = "EUR",
        created_by: Optional[UUID] = None,
    ) -> PurchaseOrder:
        po = PurchaseOrder(
            po_number=self._next_po_number(),
            supplier_id=supplier_id,
            supplier_reference=supplier_reference,
            status=PurchaseOrderStatus.ENTWURF,
            requested_delivery_date=requested_delivery_date,
            discount_percent=discount_percent or Decimal("0.00"),
            currency=currency or "EUR",
            notes=notes,
            internal_notes=internal_notes,
            created_by=created_by,
        )

        for idx, raw in enumerate(lines, start=1):
            line = PurchaseOrderLine(
                position=idx,
                product_id=raw.get("product_id"),
                product_sku=raw.get("product_sku"),
                beschreibung=raw.get("beschreibung") or raw.get("description"),
                quantity=Decimal(str(raw["quantity"])),
                unit=raw["unit"],
                unit_price=Decimal(str(raw["unit_price"])),
                tax_rate=raw.get("tax_rate") or TaxRate.STANDARD,
                discount_percent=Decimal(str(raw.get("discount_percent", "0.00"))),
            )
            line.calculate_line_totals()
            po.lines.append(line)

        po.calculate_totals()
        self.db.add(po)
        self.db.commit()
        self.db.refresh(po)
        return po

    # ---------- Wareneingang ----------

    def receive_goods(self, po_id: UUID, receipts: Sequence[dict]) -> PurchaseOrder:
        """Wareneingang verbuchen.

        ``receipts``: Liste von ``{"line_id": UUID, "quantity": Decimal}``.
        Erhöht ``quantity_received`` je Position, verhindert Übermengen und
        setzt den Bestellstatus (TEILWEISE_ERHALTEN / ERHALTEN) neu.
        """
        po = self.db.get(PurchaseOrder, po_id)
        if po is None:
            raise ValueError(f"Bestellung {po_id} nicht gefunden")
        if po.status == PurchaseOrderStatus.STORNIERT:
            raise ValueError("Stornierte Bestellung kann keinen Wareneingang erhalten")

        lines_by_id = {line.id: line for line in po.lines}
        for receipt in receipts:
            line = lines_by_id.get(receipt["line_id"])
            if line is None:
                raise ValueError(f"Position {receipt['line_id']} gehört nicht zu Bestellung {po_id}")
            qty = Decimal(str(receipt["quantity"]))
            if qty <= 0:
                raise ValueError("Wareneingangsmenge muss positiv sein")
            new_received = (line.quantity_received or Decimal("0")) + qty
            if new_received > line.quantity:
                raise ValueError(
                    f"Wareneingang ({new_received}) übersteigt Bestellmenge ({line.quantity}) "
                    f"für Position {line.position}"
                )
            line.quantity_received = new_received
            # Bestand fortschreiben (nur für produktbezogene Positionen)
            if line.product_id is not None:
                self._post_trade_goods_receipt(po, line, qty)

        po.recompute_receipt_status()
        self.db.commit()
        self.db.refresh(po)
        return po

    def _post_trade_goods_receipt(
        self, po: PurchaseOrder, line: PurchaseOrderLine, qty: Decimal
    ) -> None:
        """Handelsware-Bestand erhöhen + Lagerbewegung (EINGANG) erfassen.

        Aggregiert je Produkt: eine aktive Bestandszeile pro product_id.
        """
        stock = self.db.execute(
            select(TradeGoodsInventory).where(
                TradeGoodsInventory.product_id == line.product_id,
                TradeGoodsInventory.is_active.is_(True),
            )
        ).scalars().first()

        if stock is None:
            stock = TradeGoodsInventory(
                product_id=line.product_id,
                sku=line.product_sku or (line.product.sku if line.product else None),
                name=line.beschreibung or (line.product.name if line.product else None),
                quantity_on_hand=Decimal("0"),
                unit=line.unit,
                last_purchase_price=line.unit_price,
            )
            self.db.add(stock)
            self.db.flush()

        qty_before = stock.quantity_on_hand or Decimal("0")
        qty_after = qty_before + qty
        stock.quantity_on_hand = qty_after
        stock.last_purchase_price = line.unit_price  # letzter EK-Preis

        self.db.add(
            InventoryMovement(
                movement_type=MovementType.EINGANG,
                item_type=InventoryItemType.HANDELSWARE,
                trade_goods_id=stock.id,
                quantity=qty,
                unit=line.unit,
                quantity_before=qty_before,
                quantity_after=qty_after,
                to_location_id=stock.location_id,
                reference_number=po.po_number,
                reason="Wareneingang Einkaufsbestellung",
            )
        )
