from typing import Optional
"""
API Endpoints für Vertrieb (Kunden, Bestellungen, Abonnements)
Erweitert mit ERP-Standard Order Header-Line Architektur
"""
from datetime import date, datetime, timezone
from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, HTTPException, status, Query, Response
from sqlalchemy import select, func, or_
from sqlalchemy.orm import joinedload

from app.api.deps import DBSession, Pagination, CurrentUser
from app.models.customer import Customer, CustomerType, Contact, CustomerAddress, AddressType, Subscription
from app.models.order import Order, OrderLine, OrderStatus, OrderAuditLog, TaxRate
from app.models.seed import Seed
from app.models.product import Product, ProductVariant
from app.models.unit import UnitOfMeasure
from app.schemas.customer import (
    CustomerCreate, CustomerUpdate, CustomerResponse, CustomerListResponse,
    ContactCreate, ContactUpdate, ContactResponse,
    CustomerAddressBase, CustomerAddressUpdate, CustomerAddressResponse,
    SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse, SubscriptionListResponse
)
from app.schemas.order import (
    OrderCreate, OrderUpdate, OrderResponse, OrderListResponse,
    OrderLineCreate, OrderLineUpdate, OrderLineResponse,
    OrderStatusUpdate, OrderAuditLogResponse, OrderSummary,
    BulkStatusUpdate
)
from app.tasks.forecast_tasks import update_forecast_from_order
from app.services.datev_service import DatevService

import logging

logger = logging.getLogger(__name__)


def _trigger_forecast_update(order_id: str, action: str) -> None:
    """Fire-and-forget Forecast-Update. Wenn Redis nicht erreichbar ist
    (z.B. Railway-Demo ohne Worker), nicht den Request abbrechen."""
    try:
        update_forecast_from_order.delay(order_id, action)
    except Exception as exc:
        logger.warning("Forecast-Update fire-and-forget übersprungen (%s): %s", action, exc)


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
    - **search**: Suche nach Name oder E-Mail (case-insensitive, umlaut-sicher via ILIKE)
    """
    query = select(Customer)

    if typ:
        query = query.where(Customer.typ == typ)
    if aktiv is not None:
        query = query.where(Customer.aktiv == aktiv)
    if search and search.strip():
        safe_search = search.strip().replace("%", "\\%").replace("_", "\\_")
        like = f"%{safe_search}%"
        query = query.where(
            or_(Customer.name.ilike(like), Customer.email.ilike(like))
        )

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
    """Neuen Kunden anlegen. Wenn customer_number leer ist, wird automatisch
    KD-NNNNN sequenziell generiert (5-stellig, beginnend bei 10001)."""
    data = customer_data.model_dump()
    if "addresses" in data:
        del data["addresses"]

    # Auto-Kundennummer wenn nicht angegeben
    if not data.get("customer_number"):
        last_with_num = db.execute(
            select(Customer)
            .where(Customer.customer_number.like("KD-%"))
            .order_by(Customer.customer_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        if last_with_num and last_with_num.customer_number:
            try:
                last_num = int(last_with_num.customer_number.split("-")[-1])
            except (ValueError, IndexError):
                last_num = 10000
        else:
            last_num = 10000
        data["customer_number"] = f"KD-{last_num + 1:05d}"

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


# ============== Customer Address Endpoints ==============

@router.get("/customers/{customer_id}/addresses", response_model=list[CustomerAddressResponse])
async def list_addresses(customer_id: UUID, db: DBSession):
    """Adressen eines Kunden (Rechnungs-/Lieferadressen)."""
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")
    addresses = db.execute(
        select(CustomerAddress)
        .where(CustomerAddress.customer_id == customer_id)
        .order_by(CustomerAddress.is_default.desc(), CustomerAddress.address_type)
    ).scalars().all()
    return [CustomerAddressResponse.model_validate(a) for a in addresses]


@router.post("/customers/{customer_id}/addresses", response_model=CustomerAddressResponse, status_code=status.HTTP_201_CREATED)
async def create_address(customer_id: UUID, data: CustomerAddressBase, db: DBSession):
    """Adresse zu einem Kunden hinzufügen. customer_id kommt aus dem Pfad."""
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")

    if data.is_default:
        # Andere Default-Adressen gleichen Typs zurücksetzen
        existing_defaults = db.execute(
            select(CustomerAddress).where(
                CustomerAddress.customer_id == customer_id,
                CustomerAddress.address_type == data.address_type,
                CustomerAddress.is_default == True,
            )
        ).scalars().all()
        for ed in existing_defaults:
            ed.is_default = False

    address = CustomerAddress(customer_id=customer_id, **data.model_dump())
    db.add(address)
    db.commit()
    db.refresh(address)
    return CustomerAddressResponse.model_validate(address)


@router.patch("/customers/{customer_id}/addresses/{address_id}", response_model=CustomerAddressResponse)
async def update_address(customer_id: UUID, address_id: UUID, data: CustomerAddressUpdate, db: DBSession):
    address = db.get(CustomerAddress, address_id)
    if not address or address.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Adresse nicht gefunden")
    update_data = data.model_dump(exclude_unset=True)
    if update_data.get("is_default") is True:
        # Andere Defaults gleichen Typs zurücksetzen
        target_type = update_data.get("address_type", address.address_type)
        others = db.execute(
            select(CustomerAddress).where(
                CustomerAddress.customer_id == customer_id,
                CustomerAddress.address_type == target_type,
                CustomerAddress.is_default == True,
                CustomerAddress.id != address_id,
            )
        ).scalars().all()
        for o in others:
            o.is_default = False
    for field, value in update_data.items():
        setattr(address, field, value)
    db.commit()
    db.refresh(address)
    return CustomerAddressResponse.model_validate(address)


@router.delete("/customers/{customer_id}/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(customer_id: UUID, address_id: UUID, db: DBSession):
    address = db.get(CustomerAddress, address_id)
    if not address or address.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Adresse nicht gefunden")
    db.delete(address)
    db.commit()


# ============== Customer-Pricing Endpoints ==============

from app.models.customer_price import CustomerPrice
from app.schemas.customer_price import (
    CustomerPriceCreate, CustomerPriceUpdate, CustomerPriceResponse,
)
from app.services.pricing_service import resolve_unit_price as _resolve_unit_price


def _enrich_price(db, price: CustomerPrice) -> CustomerPriceResponse:
    resp = CustomerPriceResponse.model_validate(price)
    if price.product:
        resp.product_name = price.product.name
        resp.product_sku  = price.product.sku
    return resp


@router.get("/customers/{customer_id}/prices", response_model=list[CustomerPriceResponse])
async def list_customer_prices(customer_id: UUID, db: DBSession):
    """Listet alle Sonderpreise eines Kunden, sortiert nach Produktname."""
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")
    prices = db.execute(
        select(CustomerPrice)
        .options(joinedload(CustomerPrice.product))
        .where(CustomerPrice.customer_id == customer_id)
        .order_by(CustomerPrice.valid_from.desc())
    ).scalars().all()
    return [_enrich_price(db, p) for p in prices]


@router.post("/customers/{customer_id}/prices", response_model=CustomerPriceResponse, status_code=status.HTTP_201_CREATED)
async def create_customer_price(customer_id: UUID, data: CustomerPriceCreate, db: DBSession):
    """Legt einen Sonderpreis für ein Produkt fest. valid_from defaultet
    auf heute, valid_until auf NULL (= unbegrenzt)."""
    if not db.get(Customer, customer_id):
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")
    if not db.get(Product, data.product_id):
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")

    payload = data.model_dump()
    if payload.get("valid_from") is None:
        from datetime import date as _date
        payload["valid_from"] = _date.today()
    # Datumsbereich validieren: end >= start
    vf, vu = payload.get("valid_from"), payload.get("valid_until")
    if vf and vu and vu < vf:
        raise HTTPException(
            status_code=400,
            detail=f"valid_until ({vu}) liegt vor valid_from ({vf}) — Sonderpreis wäre nie aktiv",
        )

    price = CustomerPrice(customer_id=customer_id, **payload)
    db.add(price)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Sonderpreis konnte nicht angelegt werden (ggf. Duplikat für gleichen Zeitraum): {e}",
        )
    db.refresh(price)
    # Product eager-laden für die Response
    price = db.execute(
        select(CustomerPrice).options(joinedload(CustomerPrice.product)).where(CustomerPrice.id == price.id)
    ).unique().scalar_one()
    return _enrich_price(db, price)


@router.patch("/customer-prices/{price_id}", response_model=CustomerPriceResponse)
async def update_customer_price(price_id: UUID, data: CustomerPriceUpdate, db: DBSession):
    """Aktualisiert einen Sonderpreis."""
    price = db.execute(
        select(CustomerPrice).options(joinedload(CustomerPrice.product)).where(CustomerPrice.id == price_id)
    ).unique().scalar_one_or_none()
    if not price:
        raise HTTPException(status_code=404, detail="Sonderpreis nicht gefunden")
    updates = data.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(price, k, v)
    # Datumsbereich validieren NACH dem Setzen (kombiniertes Bild aus
    # bestehenden + neuen Werten)
    if price.valid_until and price.valid_until < price.valid_from:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"valid_until ({price.valid_until}) liegt vor valid_from ({price.valid_from}) — Sonderpreis wäre nie aktiv",
        )
    db.commit()
    db.refresh(price)
    return _enrich_price(db, price)


@router.delete("/customer-prices/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer_price(price_id: UUID, db: DBSession):
    """Entfernt einen Sonderpreis (regulärer Preis greift dann wieder)."""
    price = db.get(CustomerPrice, price_id)
    if not price:
        raise HTTPException(status_code=404, detail="Sonderpreis nicht gefunden")
    db.delete(price)
    db.commit()
    return None


@router.get("/customers/{customer_id}/effective-price/{product_id}")
async def get_effective_price(customer_id: UUID, product_id: UUID, db: DBSession):
    """Liefert den gültigen Preis für die Order-UI-Vorbelegung. Antwortet mit
    {unit_price, is_customer_specific, base_price}."""
    if not db.get(Customer, customer_id):
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")
    price, is_customer = _resolve_unit_price(
        db, customer_id=customer_id, product_id=product_id, default=product.base_price
    )
    return {
        "unit_price": str(price),
        "is_customer_specific": is_customer,
        "base_price": str(product.base_price) if product.base_price is not None else None,
    }


# ============== Contact (Ansprechpartner) Endpoints ==============

@router.get("/customers/{customer_id}/contacts", response_model=list[ContactResponse])
async def list_contacts(customer_id: UUID, db: DBSession):
    """Ansprechpartner eines Kunden listen."""
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")
    contacts = db.execute(
        select(Contact).where(Contact.customer_id == customer_id).order_by(Contact.is_primary.desc(), Contact.name)
    ).scalars().all()
    return [ContactResponse.model_validate(c) for c in contacts]


@router.post("/customers/{customer_id}/contacts", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(customer_id: UUID, data: ContactCreate, db: DBSession):
    """Neuen Ansprechpartner anlegen."""
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")
    contact = Contact(customer_id=customer_id, **data.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return ContactResponse.model_validate(contact)


@router.patch("/customers/{customer_id}/contacts/{contact_id}", response_model=ContactResponse)
async def update_contact(customer_id: UUID, contact_id: UUID, data: ContactUpdate, db: DBSession):
    contact = db.get(Contact, contact_id)
    if not contact or contact.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Ansprechpartner nicht gefunden")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    db.commit()
    db.refresh(contact)
    return ContactResponse.model_validate(contact)


@router.delete("/customers/{customer_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(customer_id: UUID, contact_id: UUID, db: DBSession):
    contact = db.get(Contact, contact_id)
    if not contact or contact.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Ansprechpartner nicht gefunden")
    db.delete(contact)
    db.commit()


@router.get("/customers/export/datev")
async def export_customers_datev(db: DBSession):
    """Exportiert Kundenstammdaten im DATEV-Format."""
    service = DatevService(db)
    csv_content = service.export_customers_csv()
    
    filename = f"DATEV_Debitoren_{date.today()}.csv"
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        }
    )


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

    # Entweder Product ODER Saatgut muss gewählt sein (Abos auf neuer Produkt-Welt
    # oder Legacy-Saatgut-Welt)
    payload = sub_data.model_dump()
    product_id = payload.get("product_id")
    seed_id = payload.get("seed_id")

    product = None
    seed = None
    if product_id:
        product = db.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Produkt {product_id} nicht gefunden")
    elif seed_id:
        seed = db.get(Seed, seed_id)
        if not seed:
            raise HTTPException(status_code=404, detail=f"Saatgut {seed_id} nicht gefunden")
    else:
        raise HTTPException(
            status_code=400,
            detail="Bitte Produkt oder Saatgut auswählen",
        )

    subscription = Subscription(**payload)
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    response = SubscriptionResponse.model_validate(subscription)
    response.kunde_name = customer.name
    response.seed_name = (seed.name if seed else (product.name if product else None))
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

@router.post("/subscriptions/process-today", status_code=status.HTTP_200_OK)
async def process_today_subscriptions():
    """Löst manuell den Subscription-Run für heute aus."""
    from app.tasks.subscription_tasks import process_daily_subscriptions
    # Synchron ausführen um Ergebnis zu sehen
    result = process_daily_subscriptions()
    return {"message": "Subscription run completed", "details": result}

# ============== Order Endpoints (Header-Line Architecture) ==============

def _generate_order_number(db: DBSession) -> str:
    """Generiert sequenzielle Bestellnummer im Format BE-YYYYMMDD-NNNN.

    Uses SELECT ... FOR UPDATE to prevent duplicate numbers under
    concurrent access.
    """
    today = date.today()
    prefix = f"BE-{today.strftime('%Y%m%d')}"

    # Lock matching rows to prevent concurrent duplicates
    last_order = db.execute(
        select(Order)
        .where(Order.order_number.like(f"{prefix}-%"))
        .order_by(Order.order_number.desc())
        .with_for_update()
        .limit(1)
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
            product_variant_id=line.product_variant_id,
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
            variable_bundle_selections=line.variable_bundle_selections,
            created_at=line.created_at,
            updated_at=line.updated_at
        )
        lines.append(line_response)

    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        customer_id=order.customer_id,
        customer_name=order.customer.name if order.customer else None,
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

    # Kreditlimit prüfen
    if customer.credit_limit is not None:
        # Offene Bestellungen des Kunden summieren
        open_order_total = db.execute(
            select(func.coalesce(func.sum(Order.total_gross), Decimal("0")))
            .where(
                Order.customer_id == customer.id,
                Order.status.in_([
                    OrderStatus.ENTWURF, OrderStatus.BESTAETIGT, OrderStatus.IN_PRODUKTION
                ])
            )
        ).scalar() or Decimal("0")

        # Neuen Bestellwert schätzen (Summe aller Positionen)
        estimated_total = Decimal("0")
        for ld in order_data.lines:
            line_net = ld.quantity * ld.unit_price
            if ld.discount_percent:
                line_net = line_net * (1 - ld.discount_percent / 100)
            tax_rate = (ld.tax_rate or TaxRate.REDUZIERT).rate
            estimated_total += line_net + (line_net * tax_rate)

        if open_order_total + estimated_total > customer.credit_limit:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Kreditlimit überschritten: Limit {customer.credit_limit:.2f} EUR, "
                    f"offene Bestellungen {open_order_total:.2f} EUR, "
                    f"neue Bestellung ~{estimated_total:.2f} EUR"
                )
            )

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
        line_unit = line_data.unit
        line_price = line_data.unit_price

        if line_data.product_id:
            product = db.get(Product, line_data.product_id)
            if not product:
                raise HTTPException(
                    status_code=404,
                    detail=f"Produkt {line_data.product_id} nicht gefunden"
                )
            product_name = product.name

            # Customer-spezifischer Preis schlägt Default-Preis,
            # aber nur wenn der User keinen Preis explizit geliefert hat.
            # (line_data.unit_price > 0 = User-Override, sonst Auto-Lookup)
            # WICHTIG: on_date = HEUTE, nicht delivery_date. Wir wollen den
            # Preis "zum Bestellzeitpunkt" — sonst würde ein zukünftiger
            # Preistarif, dessen valid_from <= delivery_date ist, schon jetzt
            # greifen und der Kunde sähe einen anderen Preis als erwartet.
            if line_data.unit_price in (None, 0, Decimal("0")):
                from datetime import date as _date
                cp_price, is_cp = _resolve_unit_price(
                    db,
                    customer_id=order_data.customer_id,
                    product_id=line_data.product_id,
                    default=product.base_price,
                    on_date=_date.today(),
                )
                line_price = cp_price

        # Variante: ergänzt Name, Einheit (aus packaging_unit) und Preis (aus override
        # oder Eltern-Basispreis), wenn nicht explizit gesetzt.
        if line_data.product_variant_id:
            variant = db.get(ProductVariant, line_data.product_variant_id)
            if not variant:
                raise HTTPException(status_code=404, detail="Verpackungs-Variante nicht gefunden")
            if line_data.product_id and variant.parent_product_id != line_data.product_id:
                raise HTTPException(
                    status_code=400,
                    detail="Variante gehört nicht zum gewählten Produkt"
                )
            product_name = f"{product.name if product else product_name} — {variant.name_suffix or ''}".strip(" —")
            packaging_unit = db.get(UnitOfMeasure, variant.packaging_unit_id)
            if packaging_unit:
                line_unit = packaging_unit.code
            if variant.price_override is not None:
                line_price = variant.price_override
            elif product and product.base_price is not None:
                line_price = product.base_price

        # Variable Bundle (Gastrotray): Sorten-Auswahl validieren
        selections = line_data.variable_bundle_selections
        if product and getattr(product, "is_variable_bundle", False):
            if not selections:
                raise HTTPException(
                    status_code=400,
                    detail=f"'{product.name}' ist ein variables Bundle — bitte Sorten auswählen",
                )
            total_slots = sum(int(s.get("quantity", 1) or 1) for s in selections)
            min_slots = product.variable_bundle_min_slots or 1
            max_slots = product.variable_bundle_max_slots or 99
            if total_slots < min_slots or total_slots > max_slots:
                raise HTTPException(
                    status_code=400,
                    detail=f"'{product.name}' braucht {min_slots}–{max_slots} Sorten, erhalten: {total_slots}",
                )
            # Validierung: alle product_ids müssen existieren
            for s in selections:
                child = db.get(Product, UUID(str(s["product_id"]))) if s.get("product_id") else None
                if not child:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Sorte mit ID {s.get('product_id')} nicht gefunden",
                    )
        elif selections:
            # variable_bundle_selections nur sinnvoll bei is_variable_bundle Produkten
            selections = None

        line = OrderLine(
            order_id=order.id,
            position=idx,
            product_id=line_data.product_id,
            product_variant_id=line_data.product_variant_id,
            beschreibung=product_name,
            quantity=line_data.quantity,
            unit=line_unit,
            unit_price=line_price,
            discount_percent=line_data.discount_percent,
            tax_rate=line_data.tax_rate or TaxRate.REDUZIERT,  # Lebensmittel: 7%
            requested_delivery_date=line_data.requested_delivery_date,
            variable_bundle_selections=selections,
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
    _trigger_forecast_update(str(order.id), "CREATE")

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
    order.updated_at = datetime.now(timezone.utc)

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
    _trigger_forecast_update(str(order.id), "UPDATE")

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
    order.updated_at = datetime.now(timezone.utc)

    _create_audit_log(
        db, order,
        user_id=UUID(user["id"]) if user else None,
        action="CONFIRM",
        old_values={"status": old_status},
        new_values={"status": order.status.value}
    )

    db.commit()

    # Forecast-Neuberechnung triggern
    _trigger_forecast_update(str(order.id), "CONFIRM")

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
    order.updated_at = datetime.now(timezone.utc)

    _create_audit_log(
        db, order,
        user_id=UUID(user["id"]) if user else None,
        action="STATUS_CHANGE",
        old_values={"status": old_status.value},
        new_values={"status": new_status.value},
        reason=status_update.reason
    )

    # Wenn Übergang auf GELIEFERT: Bestand IN DER SELBEN TRANSACTION abziehen.
    # Damit ist garantiert, dass Status + Inventory atomar passieren — entweder
    # beides oder nichts. Fehlschlag → 500 + Rollback, nichts wird persistiert.
    if new_status == OrderStatus.GELIEFERT:
        from app.services.order_fulfillment_service import deduct_inventory_for_order
        order_full = db.execute(
            select(Order)
            .options(joinedload(Order.lines))
            .where(Order.id == order_id)
        ).unique().scalar_one_or_none()
        if order_full:
            try:
                deduct_inventory_for_order(db, order_full, commit=False)
            except Exception as e:
                db.rollback()
                import logging; logging.getLogger(__name__).exception(
                    "Inventory-Deduction beim Status-Update fehlgeschlagen: %s", e
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Status-Übergang abgebrochen — Inventory-Abzug fehlgeschlagen: {e}",
                )

    db.commit()

    # Forecast bei Stornierung triggern
    if new_status == OrderStatus.STORNIERT:
        _trigger_forecast_update(str(order.id), "CANCEL")

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
    order.updated_at = datetime.now(timezone.utc)

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
    order.updated_at = datetime.now(timezone.utc)

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
    order.updated_at = datetime.now(timezone.utc)

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
        order.updated_at = datetime.now(timezone.utc)

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
