from datetime import date
from celery import shared_task
from sqlalchemy import select
from app.database import SessionLocal
from app.models.customer import Subscription, SubscriptionInterval
from app.models.order import Order, OrderLine, OrderStatus, TaxRate
from app.models.product import Product, PriceList, PriceListItem
from app.api.v1.sales import router
from typing import List

def _is_subscription_due_today(sub: Subscription) -> bool:
    """Prüft ob Abo heute fällig ist."""
    today = date.today()
    
    # Basis-Prüfung Gültigkeit
    if not sub.ist_aktiv:
        return False
        
    # Check Liefertage (0=Montag, 6=Sonntag)
    # Wenn liefertage festgelegt sind, muss heute einer davon sein
    if sub.liefertage:
        if today.weekday() not in sub.liefertage:
            return False
            
    # Check Intervall
    # Vereinfachte Logik: Wir prüfen Startdatum gegen Intervall
    # In Produktion: Last Order Date prüfen
    delta = (today - sub.gueltig_von).days
    
    if delta < 0:
        return False
        
    if sub.intervall == SubscriptionInterval.TAEGLICH:
        return True
    elif sub.intervall == SubscriptionInterval.WOECHENTLICH:
        return delta % 7 == 0
    elif sub.intervall == SubscriptionInterval.ZWEIWOECHENTLICH:
        return delta % 14 == 0
    elif sub.intervall == SubscriptionInterval.MONATLICH:
        # Gleicher Tag des Monats
        return today.day == sub.gueltig_von.day
        
    return False

@shared_task
def process_daily_subscriptions():
    """Täglicher Task: Erstellt Entwurfs-Bestellungen aus aktiven Abos."""
    db = SessionLocal()
    try:
        # Aktive Abos laden
        subs = db.execute(
            select(Subscription).where(Subscription.aktiv == True)
        ).scalars().all()
        
        created_count = 0
        
        for sub in subs:
            if _is_subscription_due_today(sub):
                # Bestellung erstellen
                _create_order_from_subscription(db, sub)
                created_count += 1
                
        db.commit()
        return f"{created_count} orders created from subscriptions"
    finally:
        db.close()

def _create_order_from_subscription(db, sub: Subscription):
    """Erstellt eine Order aus einem Abo."""
    customer = sub.kunde
    
    # Order Header
    from app.api.v1.sales import _generate_order_number, _calculate_order_totals, _calculate_line_amounts
    
    order_number = _generate_order_number(db)
    
    # Adressen
    billing_addr = None
    if customer.billing_address:
         billing_addr = {
            "name": customer.billing_address.name or customer.name,
            "strasse": customer.billing_address.strasse,
            "hausnummer": customer.billing_address.hausnummer,
            "plz": customer.billing_address.plz,
            "ort": customer.billing_address.ort,
            "land": customer.billing_address.land
        }
    else:
        # Fallback minimal
        billing_addr = {"name": customer.name, "strasse": "TBD", "plz": "00000", "ort": "TBD"}
        
    delivery_addr = None
    if customer.shipping_address:
        delivery_addr = {
            "name": customer.shipping_address.name or customer.name,
            "strasse": customer.shipping_address.strasse,
            "hausnummer": customer.shipping_address.hausnummer,
            "plz": customer.shipping_address.plz,
            "ort": customer.shipping_address.ort,
            "land": customer.shipping_address.land
        }
    
    order = Order(
        order_number=order_number,
        customer_id=sub.kunde_id,
        billing_address=billing_addr,
        delivery_address=delivery_addr,
        requested_delivery_date=date.today(),
        status=OrderStatus.ENTWURF,
        currency="EUR",
        notes=f"Automatisch erstellt aus Abo {sub.id}",
        internal_notes="Subscription Run"
    )
    db.add(order)
    db.flush()
    
    # Order Line (Single Item Subscription Model assumed)
    # Holen des Preises - vereinfacht 0 oder aus Product/PriceList
    unit_price = 0
    product = db.execute(select(Product).where(Product.seed_id == sub.seed_id)).scalars().first()
    
    if product:
        # 1. Price from Customer Price List
        if customer.price_list_id:
            price_item = db.execute(
                select(PriceListItem)
                .where(
                    PriceListItem.price_list_id == customer.price_list_id,
                    PriceListItem.product_id == product.id
                )
            ).scalars().first()
            if price_item:
                unit_price = float(price_item.price)
        
        # 2. Price from Base Price (if no list price found)
        if unit_price == 0 and product.base_price:
             unit_price = float(product.base_price)
             
    # Erstelle Line
    line = OrderLine(
        order_id=order.id,
        position=1,
        seed_id=sub.seed_id, 
        beschreibung=f"Abo-Lieferung: {sub.seed.name if sub.seed else 'Unknown'}",
        quantity=sub.menge,
        unit=sub.einheit,
        unit_price=unit_price,
        tax_rate=product.tax_rate if product else TaxRate.REDUZIERT,
        requested_delivery_date=date.today()
    )
    _calculate_line_amounts(line)
    db.add(line)
    
    _calculate_order_totals(order)
