from typing import Optional
"""
Produkt-API - Endpoints für Produkte, GrowPlans und Preislisten
"""
from datetime import date
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import DBSession, PaginationParams
from app.models.product import (
    Product, ProductGroup, GrowPlan, PriceList, PriceListItem,
    ProductCategory
)
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductResponse, ProductDetailResponse,
    ProductGroupCreate, ProductGroupUpdate, ProductGroupResponse,
    GrowPlanCreate, GrowPlanUpdate, GrowPlanResponse,
    PriceListCreate, PriceListUpdate, PriceListResponse,
    PriceListItemCreate, PriceListItemUpdate, PriceListItemResponse,
)
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Produkte"])


# ========================================
# PRODUCTS
# ========================================

@router.get("", response_model=list[ProductResponse])
def list_products(
    db: DBSession,
    pagination: PaginationParams = Depends(),
    category: Optional[ProductCategory] = None,
    is_active: bool = True,
    search: Optional[str] = None,
):
    """Listet alle Produkte mit optionaler Filterung."""
    query = select(Product).where(Product.is_active == is_active)

    if category:
        query = query.where(Product.category == category)

    if search:
        query = query.where(
            Product.name.ilike(f"%{search}%") |
            Product.sku.ilike(f"%{search}%")
        )

    query = query.offset(pagination.offset).limit(pagination.page_size)
    products = db.execute(query).scalars().all()
    return products


@router.get("/statistics")
def get_product_statistics(db: DBSession):
    """Gibt Produktstatistiken zurück."""
    service = ProductService(db)
    return service.get_product_statistics()


@router.get("/{product_id}", response_model=ProductDetailResponse)
def get_product(product_id: UUID, db: DBSession):
    """Gibt ein einzelnes Produkt mit Details zurück."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")
    return product


@router.post("", response_model=ProductResponse, status_code=201)
def create_product(data: ProductCreate, db: DBSession):
    """Erstellt ein neues Produkt."""
    service = ProductService(db)
    try:
        product = service.create_product(**data.model_dump())
        db.commit()
        db.refresh(product)
        return product
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/microgreen", response_model=ProductResponse, status_code=201)
def create_microgreen_product(
    seed_id: UUID,
    grow_plan_id: UUID,
    base_price: Decimal,
    db: DBSession,
    sku_prefix: str = "MG",
):
    """Erstellt ein Microgreen-Produkt aus Saatgut und GrowPlan."""
    service = ProductService(db)
    try:
        product = service.create_microgreen_product(
            seed_id=seed_id,
            grow_plan_id=grow_plan_id,
            base_price=base_price,
            sku_prefix=sku_prefix,
        )
        db.commit()
        db.refresh(product)
        return product
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: UUID,
    data: ProductUpdate,
    db: DBSession,
):
    """Aktualisiert ein Produkt."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204)
def deactivate_product(product_id: UUID, db: DBSession):
    """Deaktiviert ein Produkt (soft delete)."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")

    product.is_active = False
    db.commit()


@router.get("/{product_id}/price")
def get_product_price(
    product_id: UUID,
    db: DBSession,
    customer_id: Optional[UUID] = None,
    quantity: Decimal = Decimal("1"),
    price_date: Optional[date] = None,
):
    """Ermittelt den Preis für ein Produkt."""
    service = ProductService(db)
    try:
        price = service.get_product_price(
            product_id=product_id,
            customer_id=customer_id,
            quantity=quantity,
            price_date=price_date,
        )
        return {"product_id": product_id, "price": price, "quantity": quantity}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ========================================
# PRODUCT GROUPS
# ========================================

groups_router = APIRouter(prefix="/product-groups", tags=["Produktgruppen"])


@groups_router.get("", response_model=list[ProductGroupResponse])
def list_product_groups(
    db: DBSession,
    parent_id: Optional[UUID] = None,
):
    """Listet alle Produktgruppen."""
    query = select(ProductGroup)
    if parent_id:
        query = query.where(ProductGroup.parent_id == parent_id)
    else:
        query = query.where(ProductGroup.parent_id == None)

    groups = db.execute(query).scalars().all()
    return groups


@groups_router.get("/{group_id}", response_model=ProductGroupResponse)
def get_product_group(group_id: UUID, db: DBSession):
    """Gibt eine Produktgruppe zurück."""
    group = db.get(ProductGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Produktgruppe nicht gefunden")
    return group


@groups_router.post("", response_model=ProductGroupResponse, status_code=201)
def create_product_group(data: ProductGroupCreate, db: DBSession):
    """Erstellt eine neue Produktgruppe."""
    service = ProductService(db)
    try:
        group = service.create_product_group(**data.model_dump())
        db.commit()
        db.refresh(group)
        return group
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@groups_router.patch("/{group_id}", response_model=ProductGroupResponse)
def update_product_group(
    group_id: UUID,
    data: ProductGroupUpdate,
    db: DBSession,
):
    """Aktualisiert eine Produktgruppe."""
    group = db.get(ProductGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Produktgruppe nicht gefunden")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(group, field, value)

    db.commit()
    db.refresh(group)
    return group


# ========================================
# GROW PLANS
# ========================================

grow_plans_router = APIRouter(prefix="/grow-plans", tags=["Wachstumspläne"])


@grow_plans_router.get("", response_model=list[GrowPlanResponse])
def list_grow_plans(
    db: DBSession,
    is_active: bool = True,
):
    """Listet alle Wachstumspläne."""
    query = select(GrowPlan).where(GrowPlan.is_active == is_active)
    plans = db.execute(query).scalars().all()
    return plans


@grow_plans_router.get("/{plan_id}", response_model=GrowPlanResponse)
def get_grow_plan(plan_id: UUID, db: DBSession):
    """Gibt einen Wachstumsplan zurück."""
    plan = db.get(GrowPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Wachstumsplan nicht gefunden")
    return plan


@grow_plans_router.post("", response_model=GrowPlanResponse, status_code=201)
def create_grow_plan(data: GrowPlanCreate, db: DBSession):
    """Erstellt einen neuen Wachstumsplan."""
    service = ProductService(db)
    try:
        plan = service.create_grow_plan(**data.model_dump())
        db.commit()
        db.refresh(plan)
        return plan
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@grow_plans_router.patch("/{plan_id}", response_model=GrowPlanResponse)
def update_grow_plan(
    plan_id: UUID,
    data: GrowPlanUpdate,
    db: DBSession,
):
    """Aktualisiert einen Wachstumsplan."""
    plan = db.get(GrowPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Wachstumsplan nicht gefunden")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(plan, field, value)

    db.commit()
    db.refresh(plan)
    return plan


@grow_plans_router.get("/{plan_id}/calculate-sow-date")
def calculate_sow_date(
    plan_id: UUID,
    target_harvest_date: date,
    db: DBSession,
):
    """Berechnet das Aussaat-Datum für ein gewünschtes Erntedatum."""
    service = ProductService(db)
    try:
        sow_date = service.calculate_sow_date(plan_id, target_harvest_date)
        return {
            "grow_plan_id": plan_id,
            "target_harvest_date": target_harvest_date,
            "sow_date": sow_date,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@grow_plans_router.get("/{plan_id}/calculate-harvest-window")
def calculate_harvest_window(
    plan_id: UUID,
    sow_date: date,
    db: DBSession,
):
    """Berechnet das Erntefenster für ein Aussaat-Datum."""
    service = ProductService(db)
    try:
        start, optimal, end = service.calculate_harvest_window(plan_id, sow_date)
        return {
            "grow_plan_id": plan_id,
            "sow_date": sow_date,
            "harvest_window": {
                "start": start,
                "optimal": optimal,
                "end": end,
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ========================================
# PRICE LISTS
# ========================================

price_lists_router = APIRouter(prefix="/price-lists", tags=["Preislisten"])


@price_lists_router.get("", response_model=list[PriceListResponse])
def list_price_lists(
    db: DBSession,
    is_active: bool = True,
):
    """Listet alle Preislisten."""
    query = select(PriceList).where(PriceList.is_active == is_active)
    lists = db.execute(query).scalars().all()
    return lists


@price_lists_router.get("/default", response_model=PriceListResponse)
def get_default_price_list(db: DBSession):
    """Gibt die Standard-Preisliste zurück."""
    price_list = db.execute(
        select(PriceList).where(PriceList.is_default == True, PriceList.is_active == True)
    ).scalar_one_or_none()

    if not price_list:
        raise HTTPException(status_code=404, detail="Keine Standard-Preisliste gefunden")
    return price_list


@price_lists_router.get("/{list_id}", response_model=PriceListResponse)
def get_price_list(list_id: UUID, db: DBSession):
    """Gibt eine Preisliste mit allen Positionen zurück."""
    price_list = db.get(PriceList, list_id)
    if not price_list:
        raise HTTPException(status_code=404, detail="Preisliste nicht gefunden")
    return price_list


@price_lists_router.post("", response_model=PriceListResponse, status_code=201)
def create_price_list(data: PriceListCreate, db: DBSession):
    """Erstellt eine neue Preisliste."""
    service = ProductService(db)
    try:
        price_list = service.create_price_list(**data.model_dump())
        db.commit()
        db.refresh(price_list)
        return price_list
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@price_lists_router.patch("/{list_id}", response_model=PriceListResponse)
def update_price_list(
    list_id: UUID,
    data: PriceListUpdate,
    db: DBSession,
):
    """Aktualisiert eine Preisliste."""
    price_list = db.get(PriceList, list_id)
    if not price_list:
        raise HTTPException(status_code=404, detail="Preisliste nicht gefunden")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(price_list, field, value)

    db.commit()
    db.refresh(price_list)
    return price_list


@price_lists_router.post("/{list_id}/copy", response_model=PriceListResponse, status_code=201)
def copy_price_list(
    list_id: UUID,
    new_code: str,
    new_name: str,
    db: DBSession,
    price_adjustment_percent: Decimal = Decimal("0"),
):
    """Kopiert eine Preisliste mit optionaler Preisanpassung."""
    service = ProductService(db)
    try:
        new_list = service.copy_price_list(
            source_id=list_id,
            new_code=new_code,
            new_name=new_name,
            price_adjustment_percent=price_adjustment_percent,
        )
        db.commit()
        db.refresh(new_list)
        return new_list
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@price_lists_router.post("/{list_id}/items", response_model=PriceListItemResponse, status_code=201)
def add_price_list_item(
    list_id: UUID,
    data: PriceListItemCreate,
    db: DBSession,
):
    """Fügt einen Preis zur Preisliste hinzu."""
    service = ProductService(db)
    try:
        item = service.add_price_list_item(
            price_list_id=list_id,
            **data.model_dump(exclude={"price_list_id"}),
        )
        db.commit()
        db.refresh(item)
        return item
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@price_lists_router.patch("/{list_id}/items/{item_id}", response_model=PriceListItemResponse)
def update_price_list_item(
    list_id: UUID,
    item_id: UUID,
    data: PriceListItemUpdate,
    db: DBSession,
):
    """Aktualisiert einen Preis in der Preisliste."""
    item = db.get(PriceListItem, item_id)
    if not item or item.price_list_id != list_id:
        raise HTTPException(status_code=404, detail="Preislistenposition nicht gefunden")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return item


@price_lists_router.delete("/{list_id}/items/{item_id}", status_code=204)
def delete_price_list_item(
    list_id: UUID,
    item_id: UUID,
    db: DBSession,
):
    """Löscht einen Preis aus der Preisliste."""
    item = db.get(PriceListItem, item_id)
    if not item or item.price_list_id != list_id:
        raise HTTPException(status_code=404, detail="Preislistenposition nicht gefunden")

    db.delete(item)
    db.commit()
