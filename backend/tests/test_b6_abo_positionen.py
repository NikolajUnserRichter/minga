"""B6 — Abos mit mehreren Produkten (Gernot, Feedback 08.10.2026).

Bis B6 trug ein Abo genau ein Produkt (Kopffelder product_id,
product_variant_id, seed_id, menge, einheit). Seit B6 trägt es Positionen in
der Tabelle subscription_items: Produkt bzw. Verpackungsvariante, Menge,
Einheit, kein Preis. Der Abo-Lauf legt je Abo und Liefertag EINE Bestellung
mit allen Positionen an. Bestands-Abos bekommen ihre Kopfdaten als Position 1
(tenancy._auto_migrate, idempotent). Der Kopf spiegelt Position 1.

Alle Helfer tragen das Präfix _b6_.
"""
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from tests.conftest import TestingSessionLocal

_B6_MO = date(2026, 10, 5)   # Montag
_B6_DO = date(2026, 10, 8)   # Donnerstag


@pytest.fixture(autouse=True)
def _b6_ohne_prognose_anstoss(monkeypatch):
    """Bestellungen stoßen per Celery eine Prognose an; ohne Redis hängt das."""
    monkeypatch.setattr("app.api.v1.sales._trigger_forecast_update", lambda *a, **k: None)


# ---------------------------------------------------------------- Helfer

def _b6_einheit(code="STK", name="Stück"):
    from app.models.unit import UnitOfMeasure, UnitCategory
    with TestingSessionLocal() as db:
        unit = db.query(UnitOfMeasure).filter_by(code=code).first()
        if unit is None:
            unit = UnitOfMeasure(code=code, name=name, category=UnitCategory.COUNT)
            db.add(unit)
            db.commit()
        return str(unit.id)


def _b6_produkt(client, name, sku, preis, **extra):
    r = client.post("/api/v1/products", json={
        "name": name, "sku": sku, "base_price": str(preis),
        "category": "MICROGREEN", "base_unit_id": _b6_einheit(), **extra,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _b6_pfandkiste(client):
    return _b6_produkt(client, "IFCO-Kiste", "B6-IFCO", "4.00",
                       category="PFAND", is_deposit=True, tax_rate="STANDARD")


def _b6_variante(client, produkt, code="KISTE_12", suffix="12er Mehrwegkiste", preis="48.00"):
    r = client.post(f"/api/v1/products/{produkt['id']}/variants", json={
        "packaging_unit_id": _b6_einheit(code, suffix),
        "name_suffix": suffix, "price_override": preis, "items_per_pack": 12,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _b6_kunde(client, name="Café Kleinberger", **extra):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "GASTRO", **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _b6_uuid(wert):
    return uuid.UUID(wert) if wert else None


def _b6_abo_db(kunde_id, positionen, **kopf):
    """Abo direkt in der DB anlegen, mit Positionen in der angegebenen
    Reihenfolge (Tasks 1-3 laufen vor der API aus Task 4). Ohne Angabe
    spiegelt der Kopf die erste Position."""
    from app.models.customer import Subscription, SubscriptionItem, SubscriptionInterval
    erste = positionen[0] if positionen else {}
    werte = {
        "intervall": SubscriptionInterval.WOECHENTLICH, "liefertage": [3],
        "gueltig_von": _B6_MO,
        "product_id": _b6_uuid(erste.get("product_id")),
        "product_variant_id": _b6_uuid(erste.get("product_variant_id")),
        "seed_id": _b6_uuid(erste.get("seed_id")),
        "menge": Decimal(str(erste.get("menge", 1))),
        "einheit": erste.get("einheit", "STUECK"),
    }
    werte.update(kopf)
    with TestingSessionLocal() as db:
        sub = Subscription(kunde_id=uuid.UUID(kunde_id), **werte)
        for nr, pos in enumerate(positionen, start=1):
            sub.positionen.append(SubscriptionItem(
                position=pos.get("position", nr),
                product_id=_b6_uuid(pos.get("product_id")),
                product_variant_id=_b6_uuid(pos.get("product_variant_id")),
                seed_id=_b6_uuid(pos.get("seed_id")),
                menge=Decimal(str(pos["menge"])),
                einheit=pos.get("einheit", "STUECK"),
            ))
        db.add(sub)
        db.commit()
        return str(sub.id)


def _b6_positionen(abo_id):
    """(position, bezeichnung, menge, einheit) je Position aus der DB."""
    from app.models.customer import Subscription
    with TestingSessionLocal() as db:
        sub = db.get(Subscription, uuid.UUID(abo_id))
        return [(p.position, p.bezeichnung, p.menge, p.einheit) for p in sub.positionen]


def _b6_bestellungen(abo_id=None):
    """Bestellungen (optional nur die eines Abos) mit ihren Positionen."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.order import Order
    with TestingSessionLocal() as db:
        q = select(Order).options(selectinload(Order.lines)).order_by(Order.order_number)
        if abo_id:
            q = q.where(Order.notes.contains(f"Abo {abo_id}"))
        return [
            {
                "id": str(o.id),
                "requested_delivery_date": o.requested_delivery_date,
                "total_net": o.total_net, "total_gross": o.total_gross,
                "lines": [
                    {
                        "position": l.position,
                        "product_id": str(l.product_id) if l.product_id else None,
                        "product_variant_id": str(l.product_variant_id) if l.product_variant_id else None,
                        "beschreibung": l.beschreibung, "unit": l.unit,
                        "quantity": l.quantity, "unit_price": l.unit_price,
                        "tax_rate": l.tax_rate.value, "line_net": l.line_net,
                    }
                    for l in sorted(o.lines, key=lambda l: l.position)
                ],
            }
            for o in db.execute(q).scalars().all()
        ]


def _b6_anlegen(abo_id, heute=_B6_DO):
    """Abo-Bestellung anlegen wie der Lauf, ohne Fälligkeitsprüfung."""
    from app.models.customer import Subscription
    from app.tasks.subscription_tasks import _create_order_from_subscription
    with TestingSessionLocal() as db:
        sub = db.get(Subscription, uuid.UUID(abo_id))
        _create_order_from_subscription(db, sub, heute)
        db.commit()


def _b6_lauf(heute=_B6_DO):
    """Der echte Lauf (Scheduler 05:00) gegen die Test-DB."""
    from app.tasks.subscription_tasks import process_daily_subscriptions
    with patch("app.tasks.subscription_tasks.SessionLocal", TestingSessionLocal):
        return process_daily_subscriptions(heute=heute)


# ------------------------------------------------ Task 1: Modell

class TestB6Modell:
    """Positionen in eigener Tabelle, sortiert, mit Anzeigenamen; sie hängen am Abo."""

    def test_positionen_kommen_nach_positionsnummer(self, client):
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kresse = _b6_produkt(client, "Kresse Schale", "B6-KRESSE", "3.00")
        abo_id = _b6_abo_db(kunde["id"], [
            {"product_id": kresse["id"], "menge": 3, "position": 2},
            {"product_id": snack["id"], "menge": 2, "position": 1},
        ])

        assert _b6_positionen(abo_id) == [
            (1, "BIO Snackbox | Amaranth", Decimal("2.00"), "STUECK"),
            (2, "Kresse Schale", Decimal("3.00"), "STUECK"),
        ]

    def test_bezeichnung_aus_variante_und_sorte(self, client):
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kiste = _b6_variante(client, snack)
        sorte = client.post("/api/v1/seeds", json={
            "name": "Gartenkresse", "keimdauer_tage": 3, "wachstumsdauer_tage": 3,
            "erntefenster_min_tage": 6, "erntefenster_optimal_tage": 7,
            "erntefenster_max_tage": 8, "ertrag_gramm_pro_tray": 350,
        }).json()
        abo_id = _b6_abo_db(kunde["id"], [
            # Variante ohne product_id: Name über das Elternprodukt
            {"product_variant_id": kiste["id"], "menge": 1, "einheit": "KISTE_12"},
            {"seed_id": sorte["id"], "menge": 100, "einheit": "G"},
            {"menge": 1},
        ])

        assert [b for _, b, _, _ in _b6_positionen(abo_id)] == [
            "BIO Snackbox | Amaranth — 12er Mehrwegkiste", "Gartenkresse", None,
        ]

    def test_kopf_spiegelt_die_erste_position(self, client):
        from app.models.customer import Subscription
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kresse = _b6_produkt(client, "Kresse Schale", "B6-KRESSE", "3.00")
        abo_id = _b6_abo_db(
            kunde["id"],
            [{"product_id": kresse["id"], "menge": 3, "einheit": "SCHALE"},
             {"product_id": snack["id"], "menge": 2}],
            product_id=uuid.UUID(snack["id"]), menge=Decimal("9"), einheit="STUECK",
        )
        with TestingSessionLocal() as db:
            sub = db.get(Subscription, uuid.UUID(abo_id))
            sub.kopf_aus_erster_position()
            db.commit()
            assert (str(sub.product_id), sub.menge, sub.einheit) == (
                kresse["id"], Decimal("3.00"), "SCHALE")

    def test_abo_loeschen_loescht_seine_positionen(self, client):
        from sqlalchemy import func, select
        from app.models.customer import Subscription, SubscriptionItem
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        abo_id = _b6_abo_db(kunde["id"], [{"product_id": snack["id"], "menge": 2}] * 2)
        with TestingSessionLocal() as db:
            db.delete(db.get(Subscription, uuid.UUID(abo_id)))
            db.commit()
            assert db.execute(select(func.count()).select_from(SubscriptionItem)).scalar() == 0

    def test_kunde_ohne_belege_loeschen_nimmt_abo_und_positionen_mit(self, client):
        """DELETE /customers löscht Kunden ohne Bestellungen und Rechnungen hart
        (Paket 3, Q5.1); das Abo hängt per ORM-Kaskade daran."""
        from sqlalchemy import func, select
        from app.models.customer import SubscriptionItem
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        _b6_abo_db(kunde["id"], [{"product_id": snack["id"], "menge": 2}])

        r = client.delete(f"/api/v1/sales/customers/{kunde['id']}")

        assert r.status_code == 204, r.text
        with TestingSessionLocal() as db:
            assert db.execute(select(func.count()).select_from(SubscriptionItem)).scalar() == 0
