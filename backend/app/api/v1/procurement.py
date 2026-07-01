"""API-Endpoints für Einkauf/Wareneingang (Purchase Orders)."""
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, Pagination
from app.models.procurement import PurchaseOrder, PurchaseOrderStatus
from app.models.seed import Supplier
from app.schemas.procurement import (
    GoodsReceiptRequest,
    PurchaseOrderCreate,
    PurchaseOrderLineResponse,
    PurchaseOrderListItem,
    PurchaseOrderListResponse,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
)
from app.services.procurement_service import ProcurementService

router = APIRouter(prefix="/procurement/purchase-orders", tags=["Einkauf"])


def _line_to_response(line) -> PurchaseOrderLineResponse:
    resp = PurchaseOrderLineResponse.model_validate(line)
    # Marge gegen Verkaufspreis des verknüpften Produkts berechnen
    product = line.product
    if product is not None and product.base_price is not None and line.unit_price is not None:
        sell = Decimal(product.base_price)
        resp.margin_per_unit = (sell - line.unit_price).quantize(Decimal("0.0001"))
        if sell > 0:
            resp.margin_percent = ((sell - line.unit_price) / sell * 100).quantize(Decimal("0.01"))
    return resp


def _po_to_response(po: PurchaseOrder) -> PurchaseOrderResponse:
    resp = PurchaseOrderResponse.model_validate(po)
    resp.supplier_name = po.supplier.name if po.supplier else None
    resp.lines = [_line_to_response(line) for line in sorted(po.lines, key=lambda l: l.position)]
    return resp


@router.get("", response_model=PurchaseOrderListResponse)
async def list_purchase_orders(
    db: DBSession,
    pagination: Pagination,
    status_filter: Optional[PurchaseOrderStatus] = None,
    supplier_id: Optional[UUID] = None,
):
    """Bestellungen auflisten (schlanke Ansicht, neueste zuerst)."""
    query = select(PurchaseOrder).options(selectinload(PurchaseOrder.supplier))
    if status_filter is not None:
        query = query.where(PurchaseOrder.status == status_filter)
    if supplier_id is not None:
        query = query.where(PurchaseOrder.supplier_id == supplier_id)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    query = query.order_by(PurchaseOrder.order_date.desc()).offset(pagination.offset).limit(pagination.page_size)
    orders = db.execute(query).scalars().all()

    items = []
    for po in orders:
        item = PurchaseOrderListItem.model_validate(po)
        item.supplier_name = po.supplier.name if po.supplier else None
        items.append(item)
    return PurchaseOrderListResponse(items=items, total=total)


@router.post("", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(data: PurchaseOrderCreate, db: DBSession):
    """Neue Bestellung anlegen (Status ENTWURF)."""
    if not db.get(Supplier, data.supplier_id):
        raise HTTPException(status_code=404, detail="Lieferant nicht gefunden")

    svc = ProcurementService(db)
    po = svc.create_purchase_order(
        supplier_id=data.supplier_id,
        lines=[line.model_dump() for line in data.lines],
        requested_delivery_date=data.requested_delivery_date,
        supplier_reference=data.supplier_reference,
        notes=data.notes,
        internal_notes=data.internal_notes,
        discount_percent=data.discount_percent,
        currency=data.currency,
    )
    return _po_to_response(po)


@router.get("/{po_id}", response_model=PurchaseOrderResponse)
async def get_purchase_order(po_id: UUID, db: DBSession):
    po = db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")
    return _po_to_response(po)


@router.patch("/{po_id}", response_model=PurchaseOrderResponse)
async def update_purchase_order(po_id: UUID, data: PurchaseOrderUpdate, db: DBSession):
    po = db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")
    if not po.can_be_modified() and data.status is None:
        raise HTTPException(status_code=409, detail="Nur Bestellungen im Status ENTWURF sind bearbeitbar")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(po, field, value)
    db.commit()
    db.refresh(po)
    return _po_to_response(po)


@router.post("/{po_id}/receive", response_model=PurchaseOrderResponse)
async def receive_goods(po_id: UUID, data: GoodsReceiptRequest, db: DBSession):
    """Wareneingang verbuchen (Teil- oder Vollmengen)."""
    svc = ProcurementService(db)
    try:
        po = svc.receive_goods(po_id, [r.model_dump() for r in data.receipts])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _po_to_response(po)


@router.delete("/{po_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_purchase_order(po_id: UUID, db: DBSession):
    """Bestellung stornieren (Soft-Cancel: Status STORNIERT)."""
    po = db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")
    if po.status == PurchaseOrderStatus.ERHALTEN:
        raise HTTPException(status_code=409, detail="Vollständig erhaltene Bestellung kann nicht storniert werden")
    po.status = PurchaseOrderStatus.STORNIERT
    db.commit()
