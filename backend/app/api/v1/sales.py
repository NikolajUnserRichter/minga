from typing import Optional
"""
API Endpoints für Vertrieb (Kunden, Bestellungen, Abonnements)
Erweitert mit ERP-Standard Order Header-Line Architektur
"""
from datetime import date, datetime
from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from app.api.deps import DBSession, Pagination, CurrentUser
from app.models.customer import Customer, CustomerType, Subscription
from app.models.order import Order, OrderLine, OrderStatus, OrderAuditLog, TaxRate
from app.models.seed import Seed
from app.models.product import Product
from app.schemas.customer import (
    CustomerCreate, CustomerUpdate, CustomerResponse, CustomerListResponse,
    SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse, SubscriptionListResponse
)
from app.schemas.order import (
    OrderCreate, OrderUpdate, OrderResponse, OrderListResponse,
    OrderLineCreate, OrderLineUpdate, OrderLineResponse,
    OrderStatusUpdate, OrderAuditLogResponse, OrderSummary,
    BulkStatusUpdate
)
from app.tasks.forecast_tasks import update_forecast_from_order

router = APIRouter()


# ============== Customer Endpoints ==============

@router.get("/customers", response_model=CustomerListResponse)
async def list_customers(
    db: DBSession,
    pagination: Pagination,
    typ: Optional[CustomerType] = None,
    aktiv: Optional[bool] = None,
    search: Optional[str] = None
):
    """
    Kundenliste abrufen.

    Filter:
    - **typ**: GASTRO, HANDEL, GEWERBE, PRIVAT
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
    data = customer_data.model_dump()
    # Adressen müssen separat behandelt werden oder leer initialisiert
    # SQLAlchemy mag addresses=None nicht für Beziehungen
    if "addresses" in data:
        del data["addresses"]
    
    customer = Customer(**data)
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


@router.delete("/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(customer_id: UUID, db: DBSession):
    """
    Kunden löschen (nur wenn keine Bestellungen/Rechnungen vorhanden).

    Soft-Delete: Deaktiviert Kunden mit vorhandenen Referenzen.
    Hard-Delete: Entfernt Kunden ohne Referenzen.
    """
    customer = db.execute(
        select(Customer)
        .options(joinedload(Customer.orders), joinedload(Customer.invoices))
        .where(Customer.id == customer_id)
    ).scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")

    if customer.can_be_deleted():
        # Hard delete möglich
        db.delete(customer)
    else:
        # Soft delete (deaktivieren)
        customer.deactivate()

    db.commit()
    return None


@router.post("/customers/{customer_id}/reactivate", response_model=CustomerResponse)
async def reactivate_customer(customer_id: UUID, db: DBSession):
    """Deaktivierten Kunden reaktivieren."""
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")

    customer.reactivate()
    db.commit()
    db.refresh(customer)
    return CustomerResponse.model_validate(customer)


# ============== Subscription Endpoints ==============

@router.get("/subscriptions", response_model=SubscriptionListResponse)
async def list_subscriptions(
    db: DBSession,
    pagination: Pagination,
    kunde_id: Optional[UUID] = None,
    aktiv: Optional[bool] = None
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


# ============== Order Endpoints (Header-Line Architecture) ==============

def _generate_order_number(db: DBSession) -> str:
    """Generiert sequenzielle Bestellnummer im Format BE-YYYYMMDD-NNNN."""
    today = date.today()
    prefix = f"BE-{today.strftime('%Y%m%d')}"

    # Höchste Nummer des Tages finden
    last_order = db.execute(
        select(Order)
        .where(Order.order_number.like(f"{prefix}-%"))
        .order_by(Order.order_number.desc())
    ).scalar_one_or_none()

    if last_order:
        last_num = int(last_order.order_number.split('-')[-1])
        next_num = last_num + 1
    else:
        next_num = 1

    return f"{prefix}-{next_num:04d}"


def _calculate_line_amounts(line: OrderLine) -> None:
    """Berechnet Positionsbeträge (Netto, MwSt, Brutto)."""
    # Nettobetrag
    subtotal = line.quantity * line.unit_price
    if line.discount_percent:
        subtotal = subtotal * (1 - line.discount_percent / 100)
    line.line_net = subtotal.quantize(Decimal("0.01"))

    # MwSt
    tax_rate = line.tax_rate.rate
    line.line_vat = (line.line_net * tax_rate).quantize(Decimal("0.01"))

    # Brutto
    line.line_gross = line.line_net + line.line_vat


def _calculate_order_totals(order: Order) -> None:
    """Berechnet Gesamtbeträge der Bestellung."""
    order.total_net = sum(line.line_net for line in order.lines)
    order.total_vat = sum(line.line_vat for line in order.lines)
    order.total_gross = order.total_net + order.total_vat


def _create_audit_log(
    db: DBSession,
    order: Order,
    user_id: UUID,
    action: str,
    old_values: Optional[dict] = None,
    new_values: Optional[dict] = None,
    reason: Optional[str] = None
) -> OrderAuditLog:
    """Erstellt Audit-Log-Eintrag für Bestellung."""
    audit_log = OrderAuditLog(
        order_id=order.id,
        user_id=user_id,
        action=action,
        old_values=old_values,
        new_values=new_values,
        reason=reason
    )
    db.add(audit_log)
    return audit_log


@router.get("/orders", response_model=OrderListResponse)
async def list_orders(
    db: DBSession,
    pagination: Pagination,
    kunde_id: Optional[UUID] = None,
    status_filter: Optional[OrderStatus] = Query(None, alias="status"),
    von_datum: Optional[date] = None,
    bis_datum: Optional[date] = None
):
    """
    Bestellungen abrufen.

    Filter:
    - **kunde_id**: Bestellungen eines Kunden
    - **status**: ENTWURF, BESTAETIGT, IN_PRODUKTION, GELIEFERT, FAKTURIERT, STORNIERT
    - **von_datum** / **bis_datum**: Lieferdatum-Zeitraum
    """
    query = select(Order).options(
        joinedload(Order.customer),
        joinedload(Order.lines).joinedload(OrderLine.product)
    )

    if kunde_id:
        query = query.where(Order.customer_id == kunde_id)
    if status_filter:
        query = query.where(Order.status == status_filter)
    if von_datum:
        query = query.where(Order.requested_delivery_date >= von_datum)
    if bis_datum:
        query = query.where(Order.requested_delivery_date <= bis_datum)

    # Total Count (ohne joins)
    count_query = select(func.count(Order.id))
    if kunde_id:
        count_query = count_query.where(Order.customer_id == kunde_id)
    if status_filter:
        count_query = count_query.where(Order.status == status_filter)
    total = db.execute(count_query).scalar() or 0

    query = query.order_by(Order.requested_delivery_date.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    orders = db.execute(query).scalars().unique().all()

    items = []
    for order in orders:
        response = _build_order_response(order)
        items.append(response)

    return OrderListResponse(items=items, total=total)


def _build_order_response(order: Order) -> OrderResponse:
    """Baut OrderResponse aus Order-Objekt."""
    lines = []
    for line in order.lines:
        line_response = OrderLineResponse(
            id=line.id,
            order_id=line.order_id,
            position=line.position,
            product_id=line.product_id,
            product_name=line.product.name if line.product else line.beschreibung or "",
            quantity=line.quantity,
            unit=line.unit,
            unit_price=line.unit_price,
            discount_percent=line.discount_percent,
            line_net=line.line_net,
            tax_rate=line.tax_rate,
            line_vat=line.line_vat,
            line_gross=line.line_gross,
            requested_delivery_date=line.requested_delivery_date,
            seed_id=line.seed_id,
            product_sku=line.product_sku,
            product_description=line.beschreibung, # Mapping beschreibung -> product_description
            harvest_id=line.harvest_id,
            batch_number=line.batch_number,
            created_at=line.created_at,
            updated_at=line.updated_at
        )
        lines.append(line_response)

    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        customer_id=order.customer_id,
        kunde_name=order.kunde.name if order.kunde else None,
        customer_reference=order.customer_reference,
        billing_address=order.billing_address,
        delivery_address=order.delivery_address,
        order_date=order.order_date,
        requested_delivery_date=order.requested_delivery_date,
        confirmed_delivery_date=order.confirmed_delivery_date,
        actual_delivery_date=order.actual_delivery_date,
        status=order.status,
        total_net=order.total_net,
        total_vat=order.total_vat,
        total_gross=order.total_gross,
        currency=order.currency,
        discount_percent=order.discount_percent,
        discount_amount=order.discount_amount,
        notes=order.notes,
        internal_notes=order.internal_notes,
        invoice_id=order.invoice_id,
        lines=lines,
        created_at=order.created_at,
        updated_at=order.updated_at,
        created_by=order.created_by,
        updated_by=order.updated_by
    )


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: UUID, db: DBSession):
    """Einzelne Bestellung abrufen."""
    order = db.execute(
        select(Order)
        .options(
            joinedload(Order.customer),
            joinedload(Order.lines).joinedload(OrderLine.product)
        )
        .where(Order.id == order_id)
    ).unique().scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    return _build_order_response(order)


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(order_data: OrderCreate, db: DBSession, user: CurrentUser):
    """
    Neue Bestellung anlegen.

    Erstellt Order-Header mit allen Positionen.
    Positionen müssen angegeben werden - leere Bestellungen sind nicht erlaubt.
    """
    # Kunde validieren
    customer = db.get(Customer, order_data.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")

    if not customer.aktiv:
        raise HTTPException(status_code=400, detail="Kunde ist deaktiviert")

    # Mindestens eine Position erforderlich
    if not order_data.lines or len(order_data.lines) == 0:
        raise HTTPException(
            status_code=400,
            detail="Bestellung muss mindestens eine Position enthalten"
        )

    # Bestellnummer generieren
    order_number = _generate_order_number(db)

    # Adressen vom Kunden übernehmen falls nicht angegeben
    billing_addr = order_data.billing_address
    if not billing_addr and customer.billing_address:
        billing_addr = {
            "name": customer.billing_address.name or customer.name,
            "strasse": customer.billing_address.strasse,
            "hausnummer": customer.billing_address.hausnummer,
            "plz": customer.billing_address.plz,
            "ort": customer.billing_address.ort,
            "land": customer.billing_address.land
        }

    delivery_addr = order_data.delivery_address
    if not delivery_addr and customer.shipping_address:
        delivery_addr = {
            "name": customer.shipping_address.name or customer.name,
            "strasse": customer.shipping_address.strasse,
            "hausnummer": customer.shipping_address.hausnummer,
            "plz": customer.shipping_address.plz,
            "ort": customer.shipping_address.ort,
            "land": customer.shipping_address.land
        }

    # Order erstellen
    order = Order(
        order_number=order_number,
        customer_id=order_data.customer_id,
        customer_reference=order_data.customer_reference,
        billing_address=billing_addr,
        delivery_address=delivery_addr,
        requested_delivery_date=order_data.requested_delivery_date,
        notes=order_data.notes,
        status=OrderStatus.ENTWURF,
        currency=order_data.currency or "EUR",
        created_by=UUID(user["id"]) if user else None
    )
    db.add(order)
    db.flush()  # ID generieren

    # Positionen erstellen
    for idx, line_data in enumerate(order_data.lines, start=1):
        product = None
        product_name = line_data.product_name

        if line_data.product_id:
            product = db.get(Product, line_data.product_id)
            if not product:
                raise HTTPException(
                    status_code=404,
                    detail=f"Produkt {line_data.product_id} nicht gefunden"
                )
            product_name = product.name

        line = OrderLine(
            order_id=order.id,
            position=idx,
            product_id=line_data.product_id,
            beschreibung=product_name,
            quantity=line_data.quantity,
            unit=line_data.unit,
            unit_price=line_data.unit_price,
            discount_percent=line_data.discount_percent,
            tax_rate=line_data.tax_rate or TaxRate.REDUZIERT,  # Lebensmittel: 7%
            requested_delivery_date=line_data.requested_delivery_date
        )
        _calculate_line_amounts(line)
        db.add(line)
        order.lines.append(line)

    # Gesamtbeträge berechnen
    _calculate_order_totals(order)

    db.commit()

    # Response bauen
    order = db.execute(
        select(Order)
        .options(
            joinedload(Order.customer),
            joinedload(Order.lines).joinedload(OrderLine.product)
        )
        .where(Order.id == order.id)
    ).unique().scalar_one()

    # Forecast-Neuberechnung triggern
    update_forecast_from_order.delay(str(order.id), "CREATE")

    return _build_order_response(order)


@router.patch("/orders/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: UUID,
    order_data: OrderUpdate,
    db: DBSession,
    user: CurrentUser
):
    """
    Bestellung aktualisieren.

    Änderungen an bestätigten Bestellungen werden im Audit-Log protokolliert.
    """
    order = db.execute(
        select(Order)
        .options(joinedload(Order.lines))
        .where(Order.id == order_id)
    ).unique().scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    if order.status == OrderStatus.STORNIERT:
        raise HTTPException(status_code=400, detail="Stornierte Bestellung kann nicht bearbeitet werden")

    # Alte Werte für Audit-Log speichern
    old_values = {}
    new_values = {}

    update_data = order_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field == "lines":
            continue  # Lines separat behandeln
        old_value = getattr(order, field, None)
        if old_value != value:
            old_values[field] = str(old_value) if old_value else None
            new_values[field] = str(value) if value else None
            setattr(order, field, value)

    order.updated_by = UUID(user["id"]) if user else None
    order.updated_at = datetime.utcnow()

    # Audit-Log für bestätigte Bestellungen
    if order.status != OrderStatus.ENTWURF and old_values:
        _create_audit_log(
            db, order,
            user_id=UUID(user["id"]) if user else None,
            action="UPDATE",
            old_values=old_values,
            new_values=new_values,
            reason=order_data.change_reason
        )

    db.commit()

    # Forecast-Neuberechnung triggern
    update_forecast_from_order.delay(str(order.id), "UPDATE")

    return await get_order(order_id, db)


@router.post("/orders/{order_id}/confirm", response_model=OrderResponse)
async def confirm_order(
    order_id: UUID,
    db: DBSession,
    user: CurrentUser,
    confirmed_delivery_date: Optional[date] = None
):
    """
    Bestellung bestätigen.

    Wechselt Status von ENTWURF zu BESTAETIGT.
    Optional kann ein bestätigtes Lieferdatum angegeben werden.
    """
    order = db.execute(
        select(Order)
        .options(joinedload(Order.lines))
        .where(Order.id == order_id)
    ).unique().scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    if order.status != OrderStatus.ENTWURF:
        raise HTTPException(
            status_code=400,
            detail=f"Bestellung hat Status {order.status.value}, kann nicht bestätigt werden"
        )

    if len(order.lines) == 0:
        raise HTTPException(
            status_code=400,
            detail="Bestellung ohne Positionen kann nicht bestätigt werden"
        )

    old_status = order.status.value
    order.status = OrderStatus.BESTAETIGT
    order.confirmed_delivery_date = confirmed_delivery_date or order.requested_delivery_date
    order.updated_by = UUID(user["id"]) if user else None
    order.updated_at = datetime.utcnow()

    _create_audit_log(
        db, order,
        user_id=UUID(user["id"]) if user else None,
        action="CONFIRM",
        old_values={"status": old_status},
        new_values={"status": order.status.value}
    )

    db.commit()

    # Forecast-Neuberechnung triggern
    update_forecast_from_order.delay(str(order.id), "CONFIRM")

    return await get_order(order_id, db)


@router.post("/orders/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: UUID,
    status_update: OrderStatusUpdate,
    db: DBSession,
    user: CurrentUser
):
    """
    Bestellstatus aktualisieren.

    Erlaubte Übergänge:
    - ENTWURF → BESTAETIGT, STORNIERT
    - BESTAETIGT → IN_PRODUKTION, STORNIERT
    - IN_PRODUKTION → GELIEFERT
    - GELIEFERT → FAKTURIERT
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    old_status = order.status
    new_status = status_update.status

    # Status-Übergangs-Validierung
    valid_transitions = {
        OrderStatus.ENTWURF: [OrderStatus.BESTAETIGT, OrderStatus.STORNIERT],
        OrderStatus.BESTAETIGT: [OrderStatus.IN_PRODUKTION, OrderStatus.STORNIERT],
        OrderStatus.IN_PRODUKTION: [OrderStatus.GELIEFERT],
        OrderStatus.GELIEFERT: [OrderStatus.FAKTURIERT],
        OrderStatus.FAKTURIERT: [],
        OrderStatus.STORNIERT: []
    }

    if new_status not in valid_transitions.get(old_status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Ungültiger Statusübergang: {old_status.value} → {new_status.value}"
        )

    order.status = new_status
    order.updated_by = UUID(user["id"]) if user else None
    order.updated_at = datetime.utcnow()

    _create_audit_log(
        db, order,
        user_id=UUID(user["id"]) if user else None,
        action="STATUS_CHANGE",
        old_values={"status": old_status.value},
        new_values={"status": new_status.value},
        reason=status_update.reason
    )

    db.commit()

    # Forecast bei Stornierung triggern
    if new_status == OrderStatus.STORNIERT:
        update_forecast_from_order.delay(str(order.id), "CANCEL")

    return await get_order(order_id, db)


@router.delete("/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(order_id: UUID, db: DBSession, user: CurrentUser):
    """
    Bestellung löschen (nur Entwürfe).

    Bestätigte Bestellungen müssen storniert werden.
    """
    order = db.execute(
        select(Order)
        .options(joinedload(Order.lines))
        .where(Order.id == order_id)
    ).unique().scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    if order.status != OrderStatus.ENTWURF:
        raise HTTPException(
            status_code=400,
            detail=f"Nur Entwürfe können gelöscht werden. Diese Bestellung hat Status {order.status.value}"
        )

    # Positionen werden durch cascade gelöscht
    db.delete(order)
    db.commit()

    return None


# ============== Order Line Endpoints ==============

@router.post("/orders/{order_id}/lines", response_model=OrderLineResponse, status_code=status.HTTP_201_CREATED)
async def add_order_line(
    order_id: UUID,
    line_data: OrderLineCreate,
    db: DBSession,
    user: CurrentUser
):
    """
    Position zu Bestellung hinzufügen.

    Nur für Entwürfe erlaubt. Bestätigte Bestellungen erfordern Änderungsprotokoll.
    """
    order = db.execute(
        select(Order)
        .options(joinedload(Order.lines))
        .where(Order.id == order_id)
    ).unique().scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    if order.status not in [OrderStatus.ENTWURF, OrderStatus.BESTAETIGT]:
        raise HTTPException(
            status_code=400,
            detail=f"Positionen können nicht hinzugefügt werden bei Status {order.status.value}"
        )

    # Nächste Position
    max_pos = max([l.position for l in order.lines], default=0)

    product = None
    product_name = line_data.product_name

    if line_data.product_id:
        product = db.get(Product, line_data.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Produkt {line_data.product_id} nicht gefunden")
        product_name = product.name

    line = OrderLine(
        order_id=order.id,
        position=max_pos + 1,
        product_id=line_data.product_id,
        beschreibung=product_name,
        quantity=line_data.quantity,
        unit=line_data.unit,
        unit_price=line_data.unit_price,
        discount_percent=line_data.discount_percent,
        tax_rate=line_data.tax_rate or TaxRate.REDUZIERT,
        requested_delivery_date=line_data.requested_delivery_date
    )
    _calculate_line_amounts(line)
    db.add(line)

    order.lines.append(line)
    _calculate_order_totals(order)
    order.updated_by = UUID(user["id"]) if user else None
    order.updated_at = datetime.utcnow()

    # Audit-Log für bestätigte Bestellungen
    if order.status != OrderStatus.ENTWURF:
        _create_audit_log(
            db, order,
            user_id=UUID(user["id"]) if user else None,
            action="ADD_LINE",
            new_values={
                "position": line.position,
                "product": product_name,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price)
            }
        )

    db.commit()
    db.refresh(line)

    return OrderLineResponse(
        id=line.id,
        order_id=line.order_id,
        position=line.position,
        product_id=line.product_id,
        product_name=product_name or "",
        quantity=line.quantity,
        unit=line.unit,
        unit_price=line.unit_price,
        discount_percent=line.discount_percent,
        line_net=line.line_net,
        tax_rate=line.tax_rate,
        line_vat=line.line_vat,
        line_gross=line.line_gross,
        requested_delivery_date=line.requested_delivery_date
    )


@router.patch("/orders/{order_id}/lines/{line_id}", response_model=OrderLineResponse)
async def update_order_line(
    order_id: UUID,
    line_id: UUID,
    line_data: OrderLineUpdate,
    db: DBSession,
    user: CurrentUser
):
    """Position aktualisieren."""
    order = db.execute(
        select(Order)
        .options(joinedload(Order.lines))
        .where(Order.id == order_id)
    ).scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    line = next((l for l in order.lines if l.id == line_id), None)
    if not line:
        raise HTTPException(status_code=404, detail="Position nicht gefunden")

    # Alte Werte für Audit
    old_values = {
        "quantity": str(line.quantity),
        "unit_price": str(line.unit_price)
    }

    update_data = line_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(line, field, value)

    _calculate_line_amounts(line)
    _calculate_order_totals(order)
    order.updated_by = UUID(user["id"]) if user else None
    order.updated_at = datetime.utcnow()

    # Audit-Log für bestätigte Bestellungen
    if order.status != OrderStatus.ENTWURF:
        _create_audit_log(
            db, order,
            user_id=UUID(user["id"]) if user else None,
            action="UPDATE_LINE",
            old_values=old_values,
            new_values={
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price)
            }
        )

    db.commit()
    db.refresh(line)

    return OrderLineResponse(
        id=line.id,
        order_id=line.order_id,
        position=line.position,
        product_id=line.product_id,
        product_name=line.product.name if line.product else line.beschreibung or "",
        quantity=line.quantity,
        unit=line.unit,
        unit_price=line.unit_price,
        discount_percent=line.discount_percent,
        line_net=line.line_net,
        tax_rate=line.tax_rate,
        line_vat=line.line_vat,
        line_gross=line.line_gross,
        requested_delivery_date=line.requested_delivery_date
    )


@router.delete("/orders/{order_id}/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order_line(
    order_id: UUID,
    line_id: UUID,
    db: DBSession,
    user: CurrentUser
):
    """Position löschen."""
    order = db.execute(
        select(Order)
        .options(joinedload(Order.lines))
        .where(Order.id == order_id)
    ).scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    line = next((l for l in order.lines if l.id == line_id), None)
    if not line:
        raise HTTPException(status_code=404, detail="Position nicht gefunden")

    # Mindestens eine Position muss bleiben (bei bestätigten Bestellungen)
    if order.status != OrderStatus.ENTWURF and len(order.lines) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Bestätigte Bestellung muss mindestens eine Position haben"
        )

    # Audit-Log
    if order.status != OrderStatus.ENTWURF:
        _create_audit_log(
            db, order,
            user_id=UUID(user["id"]) if user else None,
            action="DELETE_LINE",
            old_values={
                "position": line.position,
                "product": line.beschreibung,
                "quantity": str(line.quantity)
            }
        )

    order.lines.remove(line)
    db.delete(line)

    _calculate_order_totals(order)
    order.updated_by = UUID(user["id"]) if user else None
    order.updated_at = datetime.utcnow()

    db.commit()
    return None


# ============== Order Audit Log ==============

@router.get("/orders/{order_id}/audit-log", response_model=list[OrderAuditLogResponse])
async def get_order_audit_log(order_id: UUID, db: DBSession):
    """Änderungsprotokoll einer Bestellung abrufen."""
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    audit_logs = db.execute(
        select(OrderAuditLog)
        .where(OrderAuditLog.order_id == order_id)
        .order_by(OrderAuditLog.created_at.desc())
    ).scalars().all()

    return [OrderAuditLogResponse.model_validate(log) for log in audit_logs]


# ============== Bulk Operations ==============

@router.post("/orders/bulk-status", response_model=list[OrderSummary])
async def bulk_update_status(
    bulk_update: BulkStatusUpdate,
    db: DBSession,
    user: CurrentUser
):
    """Mehrere Bestellungen gleichzeitig auf einen Status setzen."""
    orders = db.execute(
        select(Order).where(Order.id.in_(bulk_update.order_ids))
    ).scalars().all()

    if len(orders) != len(bulk_update.order_ids):
        raise HTTPException(
            status_code=404,
            detail="Eine oder mehrere Bestellungen nicht gefunden"
        )

    updated = []
    for order in orders:
        old_status = order.status
        order.status = bulk_update.status
        order.updated_by = UUID(user["id"]) if user else None
        order.updated_at = datetime.utcnow()

        _create_audit_log(
            db, order,
            user_id=UUID(user["id"]) if user else None,
            action="BULK_STATUS_CHANGE",
            old_values={"status": old_status.value},
            new_values={"status": bulk_update.status.value},
            reason=bulk_update.reason
        )

        updated.append(OrderSummary(
            id=order.id,
            order_number=order.order_number,
            status=order.status,
            total_gross=order.total_gross
        ))

    db.commit()
    return updated
