from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from celery import shared_task
from sqlalchemy import select
from app.database import SessionLocal
from app.models.customer import Subscription, SubscriptionInterval
from app.models.order import Order, OrderLine, OrderStatus, TaxRate
from app.models.product import Product, PriceList, PriceListItem
from app.api.v1.sales import router
from typing import List

def _montag(tag: date) -> date:
    return tag - timedelta(days=tag.weekday())


def _stichtag(jahr: int, monat: int, tag: int) -> date:
    """Tag `tag` im Monat, auf das Monatsende gekappt (31. -> 30.09.)."""
    return date(jahr, monat, min(tag, monthrange(jahr, monat)[1]))


def ist_faellig(sub, heute: date) -> bool:
    """Ist das Abo an `heute` zu liefern?

    Liefertage (0 = Montag ... 6 = Sonntag) sind die Wochentage, an denen
    geliefert wird. Das Intervall sagt, in welchen Wochen bzw. Monaten:

    - TAEGLICH: jeden Tag; mit Liefertagen nur an diesen.
    - WOECHENTLICH: jede Woche an jedem Liefertag. Ohne Liefertage am
      Wochentag von gueltig_von.
    - ZWEIWOECHENTLICH: jede zweite Kalenderwoche an jedem Liefertag. Woche 0
      ist die Woche der ersten Lieferung ab gueltig_von. Ohne Liefertage alle
      14 Tage ab gueltig_von.
    - MONATLICH: Stichtag ist der Tag des Monats von gueltig_von, auf das
      Monatsende gekappt. Ohne Liefertage wird am Stichtag geliefert, mit
      Liefertagen am ersten Liefertag ab dem Stichtag (je Liefertag einmal
      in den sieben Tagen ab Stichtag).

    Bis Oktober 2026 galt zusätzlich (heute - gueltig_von) % 7 == 0 bzw. % 14.
    Ein Abo lieferte damit nur am Wochentag von gueltig_von: bei Mo + Do nur
    montags, und nie, wenn gueltig_von auf keinen Liefertag fiel.
    """
    if not sub.aktiv:
        return False
    if heute < sub.gueltig_von:
        return False
    if sub.gueltig_bis and heute > sub.gueltig_bis:
        return False

    liefertage = {int(t) for t in (sub.liefertage or [])}
    if liefertage and heute.weekday() not in liefertage:
        return False

    if sub.intervall == SubscriptionInterval.TAEGLICH:
        return True
    if sub.intervall == SubscriptionInterval.WOECHENTLICH:
        return bool(liefertage) or heute.weekday() == sub.gueltig_von.weekday()
    if sub.intervall == SubscriptionInterval.ZWEIWOECHENTLICH:
        if not liefertage:
            return (heute - sub.gueltig_von).days % 14 == 0
        erste_lieferung = min(
            sub.gueltig_von + timedelta(days=(t - sub.gueltig_von.weekday()) % 7)
            for t in liefertage
        )
        wochen = (_montag(heute) - _montag(erste_lieferung)).days // 7
        return wochen % 2 == 0
    if sub.intervall == SubscriptionInterval.MONATLICH:
        if not liefertage:
            return heute == _stichtag(heute.year, heute.month, sub.gueltig_von.day)
        vormonat = heute.replace(day=1) - timedelta(days=1)
        return any(
            0 <= (heute - _stichtag(jahr, monat, sub.gueltig_von.day)).days < 7
            for jahr, monat in ((heute.year, heute.month), (vormonat.year, vormonat.month))
        )
    return False


def _is_subscription_due_today(sub: Subscription) -> bool:
    """Prüft ob Abo heute fällig ist (alter Name, ruft ist_faellig)."""
    return ist_faellig(sub, date.today())

@shared_task
def process_daily_subscriptions(heute: Optional[date] = None):
    """Täglicher Task: Erstellt Entwurfs-Bestellungen aus aktiven Abos."""
    heute = heute or date.today()
    db = SessionLocal()
    try:
        # Aktive Abos laden
        subs = db.execute(
            select(Subscription).where(Subscription.aktiv == True)
        ).scalars().all()

        created_count = 0

        for sub in subs:
            if ist_faellig(sub, heute):
                _create_order_from_subscription(db, sub, heute)
                created_count += 1

        db.commit()
        return f"{created_count} orders created from subscriptions"
    finally:
        db.close()

def _create_order_from_subscription(db, sub: Subscription, heute: Optional[date] = None):
    """Erstellt eine Order aus einem Abo für den Liefertag `heute`."""
    heute = heute or date.today()
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
            # ohne adresszusatz fehlt die Zustellinfo auf allen Abo-Belegen
            "adresszusatz": customer.billing_address.adresszusatz,
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
            "adresszusatz": customer.shipping_address.adresszusatz,
            "plz": customer.shipping_address.plz,
            "ort": customer.shipping_address.ort,
            "land": customer.shipping_address.land
        }
    
    order = Order(
        order_number=order_number,
        customer_id=sub.kunde_id,
        billing_address=billing_addr,
        delivery_address=delivery_addr,
        requested_delivery_date=heute,
        # Abos liefern am Lauftag — ohne festgeschriebenen Packtag läge der
        # Standard-Packtag (Vortag) in der Vergangenheit und die Ware stünde
        # in keinem Tagesplan mehr.
        packing_date=Order.resolve_packing_date(heute, None),
        status=OrderStatus.ENTWURF,
        currency="EUR",
        notes=f"Automatisch erstellt aus Abo {sub.id}",
        internal_notes="Subscription Run"
    )
    db.add(order)
    db.flush()
    
    # Order Line (Single Item Subscription Model assumed)
    # Holen des Preises - vereinfacht 0 oder aus Product/PriceList.
    # Durchgehend Decimal: sub.menge ist Numeric, und Decimal * float wirft.
    unit_price = Decimal("0")
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
                unit_price = Decimal(str(price_item.price))

        # 2. Price from Base Price (if no list price found)
        if unit_price == 0 and product.base_price:
             unit_price = Decimal(str(product.base_price))

    # Erstelle Line
    line = OrderLine(
        position=1,
        seed_id=sub.seed_id, 
        beschreibung=f"Abo-Lieferung: {sub.seed.name if sub.seed else 'Unknown'}",
        quantity=sub.menge,
        unit=sub.einheit,
        unit_price=unit_price,
        tax_rate=product.tax_rate if product else TaxRate.REDUZIERT,
        requested_delivery_date=heute
    )
    _calculate_line_amounts(line)
    # Über die Beziehung anhängen: order.lines ist bei einer frisch erzeugten
    # Order eine leere Liste, die kein Lazy-Load mehr nachlädt — mit db.add()
    # allein summierte _calculate_order_totals über nichts und die Abo-
    # Bestellung blieb bei 0,00 €.
    order.lines.append(line)

    _calculate_order_totals(order)
