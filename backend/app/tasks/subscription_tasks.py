import logging
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from celery import shared_task
from sqlalchemy import select
from app.database import SessionLocal
from app.models.customer import Subscription, SubscriptionInterval
from app.models.order import Order, OrderLine, OrderStatus, TaxRate
from app.models.product import Product, ProductVariant
from app.models.unit import UnitOfMeasure
from app.services.pricing_service import resolve_unit_price
from app.services.steuersatz import steuersatz_der_position
from app.services.order_status_service import heute_berlin
from app.api.v1.sales import router
from typing import List

logger = logging.getLogger(__name__)


class AboUebersprungen(Exception):
    """Das Abo wird nicht beliefert; die Meldung nennt den Grund."""

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

def _abo_produkt(db, sub) -> tuple[Product, Optional[ProductVariant]]:
    """Produkt und Verpackungsvariante, die das Abo liefert.

    Vorrang: product_id, dann die Variante (über ihr Elternprodukt), dann das
    Legacy-Feld seed_id, dort nur, wenn genau ein aktives Produkt an der
    Sorte hängt. Ein deaktiviertes Produkt und ein variables Bundle werden
    nicht geliefert. Bis Oktober 2026 suchte der Lauf nur über seed_id. Bei
    Produkt-Abos (seed_id leer) entstand daraus WHERE products.seed_id IS NULL,
    also Preis und Steuersatz irgendeines Produkts ohne Sorte
    ("Abo-Lieferung: Unknown", LfA Förderbank Bayern ab 14.09.2026).
    """
    variante = None
    if sub.product_variant_id:
        variante = db.get(ProductVariant, sub.product_variant_id)
        if variante is None:
            raise AboUebersprungen(f"Verpackungsvariante {sub.product_variant_id} existiert nicht")

    if sub.product_id:
        produkt = db.get(Product, sub.product_id)
        if produkt is None:
            raise AboUebersprungen(f"Produkt {sub.product_id} existiert nicht")
    elif variante is not None:
        produkt = variante.parent_product
    elif sub.seed_id:
        treffer = db.execute(
            select(Product).where(Product.seed_id == sub.seed_id, Product.is_active == True)
        ).scalars().all()
        if len(treffer) != 1:
            raise AboUebersprungen(
                f"Sorte {sub.seed_id}: {len(treffer)} aktive Produkte, das Abo braucht genau eines"
            )
        produkt = treffer[0]
    else:
        raise AboUebersprungen("Abo hat weder Produkt noch Sorte")

    if variante is not None and variante.parent_product_id != produkt.id:
        raise AboUebersprungen("Verpackungsvariante gehört nicht zum Abo-Produkt")
    # "is False": nur ein ausdrücklich deaktiviertes Produkt (DELETE /products/{id}).
    if produkt.is_active is False:
        raise AboUebersprungen(f"Produkt {produkt.name} ist deaktiviert")
    if produkt.is_variable_bundle:
        # create_order verlangt dafür eine Sortenauswahl (variable_bundle_selections),
        # ohne sie fällt die Position aus dem Packplan. Ein Abo hat keine.
        raise AboUebersprungen(
            f"{produkt.name} ist ein variables Bundle und braucht eine Sortenauswahl"
        )
    return produkt, variante


def abo_position(db, sub, heute: date) -> OrderLine:
    """Bestellposition einer Abo-Lieferung an `heute`.

    Preis wie in create_order (sales.py, Positionsschleife): Sonderpreis des
    Kunden (resolve_unit_price, Stichtag = Liefertag) vor Variantenpreis vor
    Basispreis. Steuersatz aus dem Produktstamm. Einheit der Variante, sonst
    die des Abos. Wirft AboUebersprungen, bevor etwas angelegt ist.
    """
    from app.api.v1.sales import _calculate_line_amounts

    produkt, variante = _abo_produkt(db, sub)

    preis, ist_sonderpreis = resolve_unit_price(
        db, customer_id=sub.kunde_id, product_id=produkt.id,
        default=produkt.base_price, on_date=heute,
    )
    name = produkt.name
    einheit = sub.einheit
    if variante is not None:
        name = f"{produkt.name} — {variante.name_suffix or ''}".strip(" —")
        verpackung = db.get(UnitOfMeasure, variante.packaging_unit_id)
        if verpackung is not None:
            einheit = verpackung.code
        if not ist_sonderpreis:
            if variante.price_override is not None:
                preis = variante.price_override
            elif produkt.base_price is not None:
                preis = produkt.base_price

    if not preis:
        logger.warning("[abo] Abo %s: %s hat keinen Preis, Position mit 0,00 EUR", sub.id, produkt.name)

    line = OrderLine(
        position=1,
        product_id=produkt.id,
        product_variant_id=variante.id if variante is not None else None,
        seed_id=sub.seed_id,
        beschreibung=name,
        # Durchgehend Decimal: Decimal * float wirft.
        quantity=Decimal(str(sub.menge)),
        unit=einheit,
        unit_price=Decimal(str(preis or 0)),
        tax_rate=steuersatz_der_position(
            db, produkt.id, variante.id if variante is not None else None, None
        ),
        requested_delivery_date=heute,
    )
    _calculate_line_amounts(line)
    return line


def liefertag_heute() -> date:
    """Heutiger Kalendertag in München.

    Der Container läuft in UTC. Zwischen 00:00 und 02:00 Uhr Berliner Zeit
    wäre date.today() noch der Vortag, und ein Klick auf "Heute verarbeiten"
    legte die Bestellungen des Vortags an. Dieselbe Rechnung wie das
    Lieferdatum beim Statuswechsel: order_status_service.heute_berlin().
    """
    return heute_berlin()


def _abo_bestellung_vorhanden(db, sub, heute: date) -> bool:
    """Gibt es zu diesem Abo und Liefertag schon eine Bestellung?

    Zählt in jedem Status, auch STORNIERT: Wer die Abo-Bestellung eines Tages
    storniert, will sie nicht beim nächsten Klick auf "Heute verarbeiten"
    zurückhaben. Erkennungsmerkmal ist der Text, den
    _create_order_from_subscription in Order.notes schreibt, dazu Kunde und
    Liefertag. Ohne eigene Spalte ist das nicht fest: Notiz und Liefertag
    sind in der Oberfläche änderbar (EditOrderModal, OrderUpdate), Entwürfe
    lassen sich löschen (DELETE /sales/orders/{id}). Wer eins davon tut,
    bekommt die Abo-Bestellung beim nächsten Lauf desselben Tages zurück.
    """
    return db.execute(
        select(Order.id).where(
            Order.customer_id == sub.kunde_id,
            Order.requested_delivery_date == heute,
            Order.notes.contains(f"Abo {sub.id}"),
        ).limit(1)
    ).first() is not None


def abo_lauf(db, heute: date) -> dict:
    """Legt in der Mandanten-DB von `db` die an `heute` fälligen Abo-Bestellungen an.

    Zwei Aufrufer, jeder mit der Session des richtigen Mandanten:
    process_daily_subscriptions (Scheduler 05:00, SessionLocal unter der
    ContextVar des Mandanten) und der Knopf "Heute verarbeiten"
    (sales.process_today_subscriptions, Session der Anfrage). Committet.
    """
    # Aktive Abos laden
    subs = db.execute(
        select(Subscription).where(Subscription.aktiv == True)
    ).scalars().all()

    erstellt = 0
    bereits_vorhanden = 0
    uebersprungen = []
    for sub in subs:
        if not ist_faellig(sub, heute):
            continue
        # 05:00-Lauf und Knopf "Heute verarbeiten" treffen denselben Tag.
        if _abo_bestellung_vorhanden(db, sub, heute):
            bereits_vorhanden += 1
            continue
        try:
            _create_order_from_subscription(db, sub, heute)
            erstellt += 1
        except AboUebersprungen as grund:
            kunde = sub.kunde.name if sub.kunde else str(sub.kunde_id)
            logger.warning("[abo] Abo %s (%s) übersprungen: %s", sub.id, kunde, grund)
            uebersprungen.append({"abo_id": str(sub.id), "kunde": kunde, "grund": str(grund)})

    db.commit()
    # Dict statt Text: _safe_wrap (scheduler_service.py) liest "status",
    # der Knopf "Heute verarbeiten" die Zahlen.
    return {
        "status": "ok",
        "erstellt": erstellt,
        "bereits_vorhanden": bereits_vorhanden,
        "uebersprungen": uebersprungen,
    }


@shared_task
def process_daily_subscriptions(heute: Optional[date] = None):
    """Täglicher Task (Scheduler 05:00): Entwurfs-Bestellungen aus aktiven Abos.

    SessionLocal() löst über die ContextVar auf, die scheduler_service._safe_wrap
    je Mandant setzt. Ohne sie, etwa aus einer Anfrage heraus, fiele es auf
    DEFAULT_TENANT_SLUG zurück. Darum ruft der Knopf "Heute verarbeiten"
    abo_lauf mit der Session der Anfrage und nicht diesen Task.
    """
    db = SessionLocal()
    try:
        return abo_lauf(db, heute or liefertag_heute())
    finally:
        db.close()

def _create_order_from_subscription(db, sub: Subscription, heute: Optional[date] = None) -> Order:
    """Erstellt eine Order aus einem Abo für den Liefertag `heute`.

    Wirft AboUebersprungen, ohne etwas anzulegen, wenn kein eindeutiges
    Produkt feststeht.
    """
    from app.api.v1.sales import _generate_order_number, _calculate_order_totals

    heute = heute or date.today()
    # Zuerst die Position: steht kein Produkt fest, entsteht auch kein Kopf.
    line = abo_position(db, sub, heute)

    customer = sub.kunde
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

    # Über die Beziehung anhängen: order.lines ist bei einer frisch erzeugten
    # Order eine leere Liste, die kein Lazy-Load mehr nachlädt — mit db.add()
    # allein summierte _calculate_order_totals über nichts und die Abo-
    # Bestellung blieb bei 0,00 €.
    order.lines.append(line)

    _calculate_order_totals(order)
    return order
