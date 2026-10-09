"""Leergutkonto (Paket 3, Q6) — alle Regeln an einer Stelle.

Kunden mit pfand_abrechnung = MONATLICH bekommen Pfandkisten nicht auf der
Lieferrechnung berechnet. Ab dem Stichtag (Customer.pfand_monatlich_ab)
gilt:

- Lieferung: Beim Übergang nach GELIEFERT bucht deduct_inventory_for_order
  je Pfandposition eine AUSGABE (buche_ausgaben) — in derselben Transaktion
  wie der Bestandsabzug.
- Rückgabe: als Stückzahl erfasst (RUECKNAHME), ohne Geldbetrag.
- Monatsabrechnung: ein Leergutbeleg je Kunde mit "ausgegeben" und
  "zurückgenommen" je Pfandartikel. Gelieferte Bestellungen ohne Ausgabe
  (Statuswege ohne GELIEFERT) bucht erst das Anlegen der Belege nach, nie die
  Vorschau.

Doppelabrechnungsschutz beim Wechsel der Abrechnungsart, in beide Richtungen:
- Eine Pfandposition, die schon auf einer gültigen Rechnung steht, bekommt
  keine Ausgabe (pfandzeile_fakturiert).
- Eine Pfandposition mit Ausgabe kommt nie mehr auf eine Lieferrechnung,
  gleich wie der Kunde heute steht (invoice_service.ist_clearing_pfand).
- Was vor dem Stichtag geliefert wurde, bleibt in der alten Abrechnungsart.

Steuerlich offen (Steuerberater): Einordnung der Kiste, Saldierung, Beleg bei
Saldo 0, Bezeichnung des Minderungsbelegs.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer import Customer, PfandAbrechnung
from app.models.documents import DeliveryNote
from app.models.enums import InvoiceStatus, InvoiceType, OrderStatus
from app.models.invoice import Invoice, InvoiceLine, InvoiceLineSource
from app.models.leergut import LeergutArt, LeergutBewegung
from app.models.order import Order, OrderLine
from app.models.product import Product
from app.services.steuersatz import produkt_der_position

#: Invoice.beleg_art des monatlichen Leergutbelegs
BELEG_ART_LEERGUT = "LEERGUT"
SYSTEM_LIEFERUNG = "System (Lieferung)"
SYSTEM_MONATSABRECHNUNG = "System (Monatsabrechnung)"

#: Bestellungen, deren Pfand der Monatslauf nachbucht, wenn die Lieferung
#: keine Ausgabe gebucht hat (z. B. weil die Bestellung nie GELIEFERT wurde).
_NACHZUG_STATUS = (
    OrderStatus.BESTAETIGT, OrderStatus.IN_PRODUKTION,
    OrderStatus.GELIEFERT, OrderStatus.FAKTURIERT,
)


class LeergutFehler(ValueError):
    """Fachlich unzulässig — die API antwortet mit 400."""


def heute_berlin() -> date:
    """Kalendertag in München — der Server läuft in UTC."""
    return datetime.now(ZoneInfo("Europe/Berlin")).date()


def ist_pfandartikel(produkt: Optional[Product]) -> bool:
    return produkt is not None and bool(produkt.is_deposit)


def pfandwert(produkt: Product) -> Decimal:
    """Pfandwert je Stück: deposit_value, ersatzweise base_price — für Ausgabe
    und Rücknahme dieselbe Quelle, nie der (Kunden-)Preis der Bestellzeile."""
    wert = produkt.deposit_value if produkt.deposit_value is not None else produkt.base_price
    return Decimal(str(wert or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def konto(db: Session, kunde: Customer) -> dict:
    """Kistensaldo je Pfandartikel (alle Bewegungen) und die Bewegungen."""
    bewegungen = db.execute(
        select(LeergutBewegung)
        .where(LeergutBewegung.customer_id == kunde.id)
        .order_by(LeergutBewegung.leistungsdatum.desc(), LeergutBewegung.erfasst_am.desc())
    ).scalars().all()
    salden: dict = {}
    for b in bewegungen:
        s = salden.setdefault(b.product_id, {
            "product_id": b.product_id, "artikel": b.product.name,
            "stueck": 0, "wert": Decimal("0.00"),
            "offen_stueck": 0, "offen_wert": Decimal("0.00"),
        })
        s["stueck"] += b.stueck_mit_vorzeichen
        s["wert"] += b.stueck_mit_vorzeichen * b.einzelwert
        if b.abrechenbar:
            s["offen_stueck"] += b.stueck_mit_vorzeichen
            s["offen_wert"] += b.stueck_mit_vorzeichen * b.einzelwert
    return {
        "customer_id": kunde.id,
        "customer_name": kunde.name,
        "pfand_abrechnung": kunde.pfand_abrechnung,
        "pfand_monatlich_ab": kunde.pfand_monatlich_ab,
        "salden": sorted(salden.values(), key=lambda s: s["artikel"]),
        "bewegungen": bewegungen,
    }


def kunden_mit_konto(db: Session) -> list[dict]:
    """Aktive Kunden mit Leergutkonto und ihr Kistensaldo — für die Auswahl in der Halle."""
    kunden = db.execute(
        select(Customer).where(Customer.aktiv.is_(True)).order_by(Customer.name)
    ).scalars().all()
    stueck: dict = {}
    for b in db.execute(select(LeergutBewegung)).scalars():
        stueck[b.customer_id] = stueck.get(b.customer_id, 0) + b.stueck_mit_vorzeichen
    return [
        {"customer_id": k.id, "name": k.name, "pfand_abrechnung": k.pfand_abrechnung,
         "stueck_beim_kunden": stueck.get(k.id, 0)}
        for k in kunden
        if k.pfand_abrechnung == PfandAbrechnung.MONATLICH or k.id in stueck
    ]
