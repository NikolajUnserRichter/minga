"""
API Endpoints für Vertrieb (Kunden, Bestellungen, Abonnements)
"""
from datetime import date
from uuid import UUID
from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from app.api.deps import DBSession, Pagination
from app.models.customer import Customer, CustomerType, Subscription
from app.models.order import Order, OrderItem, OrderStatus
from app.models.seed import Seed
from app.schemas.customer import (
    CustomerCreate, CustomerUpdate, CustomerResponse, CustomerListResponse,
    SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse, SubscriptionListResponse
)
from app.schemas.order import (
    OrderCreate, OrderUpdate, OrderResponse, OrderListResponse, OrderItemResponse
)

router = APIRouter()


# ============== Customer Endpoints ==============

@router.get("/customers", response_model=CustomerListResponse)
async def list_customers(
    db: DBSession,
    pagination: Pagination,
    typ: CustomerType | None = None,
    aktiv: bool | None = None,
    search: str | None = None
):
    """
    Kundenliste abrufen.

    Filter:
    - **typ**: GASTRO, HANDEL, PRIVAT
    - **aktiv**: Nur aktive/inaktive Kunden
    - **search**: Suche nach Name
    """
    query = select(Customer)

    if typ:
        query = query.where(Customer.typ == typ)
    if aktiv is not None:
        query = query.where(Customer.aktiv == aktiv)
    if search:
        query = query.where(Customer.name.ilike(f"%{search}%"))

    # Total Count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Paginated Results
    query = query.order_by(Customer.name)
    query = query.offset(pagination.offset).limit(pagination.page_size)
    customers = db.execute(query).scalars().all()

    return CustomerListResponse(
        items=[CustomerResponse.model_validate(c) for c in customers],
        total=total
    )


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: UUID, db: DBSession):
    """Einzelnen Kunden abrufen."""
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kunde nicht gefunden"
        )
    return CustomerResponse.model_validate(customer)


@router.post("/customers", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(customer_data: CustomerCreate, db: DBSession):
    """Neuen Kunden anlegen."""
    customer = Customer(**customer_data.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@router.patch("/customers/{customer_id}", response_model=CustomerResponse)
async def update_customer(customer_id: UUID, customer_data: CustomerUpdate, db: DBSession):
    """Kunden aktualisieren."""
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kunde nicht gefunden"
        )

    update_data = customer_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)

    db.commit()
    db.refresh(customer)
    return CustomerResponse.model_validate(customer)


# ============== Subscription Endpoints ==============

@router.get("/subscriptions", response_model=SubscriptionListResponse)
async def list_subscriptions(
    db: DBSession,
    pagination: Pagination,
    kunde_id: UUID | None = None,
    aktiv: bool | None = None
):
    """
    Abonnements abrufen.

    Filter:
    - **kunde_id**: Abos eines bestimmten Kunden
    - **aktiv**: Nur aktive Abos
    """
    query = select(Subscription).options(
        joinedload(Subscription.kunde),
        joinedload(Subscription.seed)
    )

    if kunde_id:
        query = query.where(Subscription.kunde_id == kunde_id)
    if aktiv is not None:
        query = query.where(Subscription.aktiv == aktiv)

    # Total Count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Paginated Results
    query = query.offset(pagination.offset).limit(pagination.page_size)
    subscriptions = db.execute(query).scalars().unique().all()

    items = []
    for sub in subscriptions:
        response = SubscriptionResponse.model_validate(sub)
        response.kunde_name = sub.kunde.name if sub.kunde else None
        response.seed_name = sub.seed.name if sub.seed else None
        items.append(response)

    return SubscriptionListResponse(items=items, total=total)


@router.post("/subscriptions", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(sub_data: SubscriptionCreate, db: DBSession):
    """
    Neues Abonnement anlegen.

    Wichtig für Forecasting: Regelmäßige Bestellungen werden automatisch
    in die Absatzprognose einbezogen.
    """
    # Validierung
    customer = db.get(Customer, sub_data.kunde_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")

    seed = db.get(Seed, sub_data.seed_id)
    if not seed:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")

    subscription = Subscription(**sub_data.model_dump())
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    response = SubscriptionResponse.model_validate(subscription)
    response.kunde_name = customer.name
    response.seed_name = seed.name
    return response


@router.patch("/subscriptions/{sub_id}", response_model=SubscriptionResponse)
async def update_subscription(sub_id: UUID, sub_data: SubscriptionUpdate, db: DBSession):
    """Abonnement aktualisieren."""
    subscription = db.execute(
        select(Subscription)
        .options(joinedload(Subscription.kunde), joinedload(Subscription.seed))
        .where(Subscription.id == sub_id)
    ).scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=404, detail="Abonnement nicht gefunden")

    update_data = sub_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(subscription, field, value)

    db.commit()
    db.refresh(subscription)

    response = SubscriptionResponse.model_validate(subscription)
    response.kunde_name = subscription.kunde.name
    response.seed_name = subscription.seed.name
    return response


# ============== Order Endpoints ==============

@router.get("/orders", response_model=OrderListResponse)
async def list_orders(
    db: DBSession,
    pagination: Pagination,
    kunde_id: UUID | None = None,
    status_filter: OrderStatus | None = Query(None, alias="status"),
    von_datum: date | None = None,
    bis_datum: date | None = None
):
    """
    Bestellungen abrufen.

    Filter:
    - **kunde_id**: Bestellungen eines Kunden
    - **status**: OFFEN, BESTAETIGT, IN_PRODUKTION, BEREIT, GELIEFERT, STORNIERT
    - **von_datum** / **bis_datum**: Lieferdatum-Zeitraum
    """
    query = select(Order).options(
        joinedload(Order.kunde),
        joinedload(Order.positionen).joinedload(OrderItem.seed)
    )

    if kunde_id:
        query = query.where(Order.kunde_id == kunde_id)
    if status_filter:
        query = query.where(Order.status == status_filter)
    if von_datum:
        query = query.where(Order.liefer_datum >= von_datum)
    if bis_datum:
        query = query.where(Order.liefer_datum <= bis_datum)

    # Total Count (ohne joins)
    count_query = select(func.count(Order.id))
    if kunde_id:
        count_query = count_query.where(Order.kunde_id == kunde_id)
    if status_filter:
        count_query = count_query.where(Order.status == status_filter)
    total = db.execute(count_query).scalar() or 0

    # Paginated Results
    query = query.order_by(Order.liefer_datum.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    orders = db.execute(query).scalars().unique().all()

    items = []
    for order in orders:
        response = OrderResponse.model_validate(order)
        response.kunde_name = order.kunde.name if order.kunde else None
        response.positionen = []
        for pos in order.positionen:
            pos_response = OrderItemResponse.model_validate(pos)
            pos_response.seed_name = pos.seed.name if pos.seed else None
            response.positionen.append(pos_response)
        items.append(response)

    return OrderListResponse(items=items, total=total)


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: UUID, db: DBSession):
    """Einzelne Bestellung abrufen."""
    order = db.execute(
        select(Order)
        .options(
            joinedload(Order.kunde),
            joinedload(Order.positionen).joinedload(OrderItem.seed)
        )
        .where(Order.id == order_id)
    ).scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    response = OrderResponse.model_validate(order)
    response.kunde_name = order.kunde.name if order.kunde else None
    response.positionen = []
    for pos in order.positionen:
        pos_response = OrderItemResponse.model_validate(pos)
        pos_response.seed_name = pos.seed.name if pos.seed else None
        response.positionen.append(pos_response)

    return response


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(order_data: OrderCreate, db: DBSession):
    """
    Neue Bestellung anlegen.

    Erstellt Order mit allen Positionen.
    """
    # Kunde validieren
    customer = db.get(Customer, order_data.kunde_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")

    # Order erstellen
    order = Order(
        kunde_id=order_data.kunde_id,
        liefer_datum=order_data.liefer_datum,
        notizen=order_data.notizen,
        status=OrderStatus.OFFEN
    )
    db.add(order)
    db.flush()  # ID generieren

    # Positionen erstellen
    for pos_data in order_data.positionen:
        seed = db.get(Seed, pos_data.seed_id)
        if not seed:
            raise HTTPException(
                status_code=404,
                detail=f"Produkt {pos_data.seed_id} nicht gefunden"
            )

        item = OrderItem(
            order_id=order.id,
            seed_id=pos_data.seed_id,
            menge=pos_data.menge,
            einheit=pos_data.einheit,
            preis_pro_einheit=pos_data.preis_pro_einheit
        )
        db.add(item)

    db.commit()
    db.refresh(order)

    # Response bauen
    order = db.execute(
        select(Order)
        .options(
            joinedload(Order.kunde),
            joinedload(Order.positionen).joinedload(OrderItem.seed)
        )
        .where(Order.id == order.id)
    ).scalar_one()

    response = OrderResponse.model_validate(order)
    response.kunde_name = customer.name
    response.positionen = []
    for pos in order.positionen:
        pos_response = OrderItemResponse.model_validate(pos)
        pos_response.seed_name = pos.seed.name if pos.seed else None
        response.positionen.append(pos_response)

    return response


@router.patch("/orders/{order_id}", response_model=OrderResponse)
async def update_order(order_id: UUID, order_data: OrderUpdate, db: DBSession):
    """Bestellung aktualisieren (Status, Lieferdatum, Notizen)."""
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    update_data = order_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(order, field, value)

    db.commit()

    return await get_order(order_id, db)


@router.post("/orders/{order_id}/status/{new_status}", response_model=OrderResponse)
async def update_order_status(order_id: UUID, new_status: OrderStatus, db: DBSession):
    """Schneller Status-Update für Bestellung."""
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    order.status = new_status
    db.commit()

    return await get_order(order_id, db)
