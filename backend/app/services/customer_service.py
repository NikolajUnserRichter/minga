"""
Kunden-Service — gemeinsame Logik für alle Wege, auf denen Kunden entstehen.
"""
from sqlalchemy import select

from app.models.customer import Customer

CUSTOMER_NUMBER_PREFIX = "KD-"
CUSTOMER_NUMBER_START = 10000


def next_customer_number(db) -> str:
    """Nächste freie Kundennummer im Format KD-NNNNN.

    Jeder Kunde braucht eine Nummer: der Lieferschein lässt die Zeile
    "Kundennummer" sonst komplett weg, die Rechnung zeigt "-". Über die
    Maske angelegte Kunden bekamen eine, über Excel importierte nicht —
    deshalb liegt die Vergabe hier statt im Endpunkt.

    Sortiert wird numerisch, nicht alphabetisch: sonst stünde KD-9999 hinter
    KD-10001, sobald die Nummern fünfstellig werden.
    """
    nummern = db.execute(
        select(Customer.customer_number)
        .where(Customer.customer_number.like(f"{CUSTOMER_NUMBER_PREFIX}%"))
    ).scalars().all()

    hoechste = CUSTOMER_NUMBER_START
    for nummer in nummern:
        try:
            hoechste = max(hoechste, int(str(nummer).rsplit("-", 1)[-1]))
        except (ValueError, IndexError):
            continue

    return f"{CUSTOMER_NUMBER_PREFIX}{hoechste + 1:05d}"
