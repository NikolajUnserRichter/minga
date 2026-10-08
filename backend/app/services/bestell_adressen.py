"""Adress-Schnappschuss einer Bestellung aus den Kundenadressen.

Dieselbe Regel wie `create_order` (sales.py, Abschnitt „Adressen vom Kunden
übernehmen"): Standard-Rechnungs- und -Lieferadresse des Kunden, inklusive
Adresszusatz. Der trägt die Zustellinfo („Werk 2 - Tor 210") und wäre ohne
Schnappschuss auf jedem später erzeugten Beleg weg.

Heute nutzt nur der Bestell-Import diese Funktion. `create_order` behält
vorerst seinen eigenen Block, weil Paket 1 und P1 parallel in sales.py
arbeiten; der Test `test_adressen_wie_bei_create_order` hält beide Wege
gleich.
"""
from typing import Optional

from app.models.customer import Customer, CustomerAddress


def _schnappschuss(customer: Customer, adresse: Optional[CustomerAddress]) -> Optional[dict]:
    if adresse is None:
        return None
    return {
        "name": adresse.name or customer.name,
        "strasse": adresse.strasse,
        "hausnummer": adresse.hausnummer,
        "adresszusatz": adresse.adresszusatz,
        "plz": adresse.plz,
        "ort": adresse.ort,
        "land": adresse.land,
    }


def adressen_vom_kunden(customer: Customer) -> tuple[Optional[dict], Optional[dict]]:
    """(Rechnungsadresse, Lieferadresse) als JSON-Schnappschuss; None ohne passende Adresse."""
    return (
        _schnappschuss(customer, customer.billing_address),
        _schnappschuss(customer, customer.shipping_address),
    )
