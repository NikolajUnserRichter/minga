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


# ------------------------------------------------ Task 2: Migration

def _b6_mandant(tmp_path, monkeypatch, slug="b6alt"):
    """Mandanten-DB wie in Produktion (WAL, foreign_keys=ON) in tmp_path."""
    from app import tenancy
    monkeypatch.setattr(tenancy, "TENANTS_DIR", tmp_path)
    tenancy.registry.dispose_all()
    tenancy.provision_tenant(slug, seed_defaults=False)
    return tenancy.registry.get_engine(slug)


def _b6_bestand_vor_b6(engine):
    """Stand vor B6: drei Abos nur mit Kopf (Produkt, Variante, Sorte; eins
    inaktiv) und ein Schema ohne subscription_items."""
    from sqlalchemy.orm import Session
    from app.models.customer import Customer, CustomerType, Subscription, SubscriptionInterval
    from app.models.product import Product, ProductVariant
    from app.models.seed import Seed
    from app.models.unit import UnitOfMeasure, UnitCategory
    with Session(engine) as db:
        stk = UnitOfMeasure(code="STK", name="Stück", category=UnitCategory.COUNT)
        kiste = UnitOfMeasure(code="KISTE_12", name="Kiste", category=UnitCategory.COUNT)
        kunde = Customer(name="Gastro Süd", typ=CustomerType.GASTRO)
        db.add_all([stk, kiste, kunde])
        db.flush()
        tray = Product(sku="MG-14001", name="Gastrotray", category="MICROGREEN",
                       base_unit_id=stk.id, base_price=Decimal("18.00"))
        db.add(tray)
        db.flush()
        variante = ProductVariant(parent_product_id=tray.id, packaging_unit_id=kiste.id,
                                  name_suffix="12er Mehrwegkiste")
        sorte = Seed(name="Gartenkresse", keimdauer_tage=3, wachstumsdauer_tage=3,
                     erntefenster_min_tage=6, erntefenster_optimal_tage=7,
                     erntefenster_max_tage=8, ertrag_gramm_pro_tray=350)
        db.add_all([variante, sorte])
        db.flush()
        gemeinsam = dict(kunde_id=kunde.id, intervall=SubscriptionInterval.WOECHENTLICH,
                         liefertage=[1, 4], gueltig_von=_B6_MO)
        abos = [
            Subscription(product_id=tray.id, menge=Decimal("3"), einheit="STUECK", **gemeinsam),
            Subscription(product_id=tray.id, product_variant_id=variante.id,
                         menge=Decimal("1"), einheit="KISTE_12", **gemeinsam),
            Subscription(seed_id=sorte.id, menge=Decimal("150"), einheit="G",
                         aktiv=False, **gemeinsam),
        ]
        db.add_all(abos)
        db.commit()
        erwartet = {
            str(a.id): [(1, a.product_id, a.product_variant_id, a.seed_id, a.menge, a.einheit)]
            for a in abos
        }
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE subscription_items")
    return erwartet


def _b6_positionen_je_abo(engine):
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.models.customer import Subscription
    with Session(engine) as db:
        return {
            str(sub.id): [(p.position, p.product_id, p.product_variant_id, p.seed_id, p.menge, p.einheit)
                          for p in sub.positionen]
            for sub in db.execute(select(Subscription)).scalars().all()
        }


def _b6_start(engine):
    """Was init_all_existing_tenants und der Demo-Reset beim Start tun."""
    from app import tenancy
    from app.database import Base
    Base.metadata.create_all(bind=engine)
    tenancy._auto_migrate(engine)


class TestB6Migration:
    """Bestands-Abos verlustfrei: der Kopf wird Position 1, einmal."""

    def test_bestands_abos_bekommen_ihren_kopf_als_position_1(self, tmp_path, monkeypatch):
        from app import tenancy
        engine = _b6_mandant(tmp_path, monkeypatch)
        try:
            erwartet = _b6_bestand_vor_b6(engine)

            _b6_start(engine)

            assert _b6_positionen_je_abo(engine) == erwartet
        finally:
            tenancy.registry.dispose_all()

    def test_zweiter_start_legt_nichts_doppelt_an(self, tmp_path, monkeypatch):
        from app import tenancy
        engine = _b6_mandant(tmp_path, monkeypatch)
        try:
            erwartet = _b6_bestand_vor_b6(engine)

            _b6_start(engine)
            _b6_start(engine)

            assert _b6_positionen_je_abo(engine) == erwartet
        finally:
            tenancy.registry.dispose_all()

    def test_abo_mit_positionen_bleibt_unberuehrt(self, tmp_path, monkeypatch):
        """Nachgetragen wird nur bei Abos ohne Position; ein Abo mit zwei
        Positionen behält beide, auch wenn sein Kopf anders aussieht."""
        from sqlalchemy.orm import Session
        from app import tenancy
        from app.models.customer import Subscription, SubscriptionItem
        engine = _b6_mandant(tmp_path, monkeypatch)
        try:
            erwartet = _b6_bestand_vor_b6(engine)
            _b6_start(engine)
            abo_id = next(iter(erwartet))
            with Session(engine) as db:
                sub = db.get(Subscription, uuid.UUID(abo_id))
                sub.positionen.append(SubscriptionItem(
                    position=2, product_id=sub.product_id, menge=Decimal("5"), einheit="SCHALE"))
                db.commit()

            _b6_start(engine)

            positionen = _b6_positionen_je_abo(engine)[abo_id]
            assert [(p[0], p[4], p[5]) for p in positionen] == [
                (1, Decimal("3.00"), "STUECK"), (2, Decimal("5.00"), "SCHALE")]
        finally:
            tenancy.registry.dispose_all()

    def test_demo_reset_traegt_positionen_nach(self, tmp_path, monkeypatch):
        """Der Golden Seed (demo.seed.db) bleibt auf dem Stand vor B6; der
        Reset um 03:30 ruft create_all und _auto_migrate."""
        from app import tenancy
        from app.services.demo_reset_service import reset_demo_from_seed, snapshot_demo_seed
        engine = _b6_mandant(tmp_path, monkeypatch, slug="demo")
        try:
            erwartet = _b6_bestand_vor_b6(engine)
            snapshot_demo_seed("demo")

            ergebnis = reset_demo_from_seed("demo")

            assert ergebnis["migriert"] is True
            assert _b6_positionen_je_abo(tenancy.registry.get_engine("demo")) == erwartet
        finally:
            tenancy.registry.dispose_all()


# ------------------------------------------------ Task 3: Abo-Lauf

def _b6_zeilen(bestellung):
    return [(l["position"], l["beschreibung"], l["quantity"], l["unit"], l["unit_price"],
             l["tax_rate"], l["line_net"]) for l in bestellung["lines"]]


class TestB6AboLauf:
    """Eine Bestellung je Abo und Liefertag, mit allen Positionen."""

    def _drei_positionen(self, client, kunde):
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kresse = _b6_produkt(client, "Kresse Schale", "B6-KRESSE", "3.00")
        kiste = _b6_variante(client, kresse, preis="30.00")
        pfand = _b6_pfandkiste(client)
        r = client.post(f"/api/v1/sales/customers/{kunde['id']}/prices", json={
            "product_id": snack["id"], "unit_price": "4.20", "valid_from": "2026-09-01",
        })
        assert r.status_code in (200, 201), r.text
        return [
            {"product_id": snack["id"], "menge": 2},
            {"product_id": kresse["id"], "product_variant_id": kiste["id"], "menge": 1},
            {"product_id": pfand["id"], "menge": 1},
        ]

    def test_eine_bestellung_mit_allen_positionen(self, client):
        kunde = _b6_kunde(client)
        abo_id = _b6_abo_db(kunde["id"], self._drei_positionen(client, kunde))

        ergebnis = _b6_lauf(_B6_DO)

        assert ergebnis["erstellt"] == 1
        [bestellung] = _b6_bestellungen(abo_id)
        assert bestellung["requested_delivery_date"] == _B6_DO
        # Sonderpreis vor Variantenpreis vor Basispreis, Satz aus dem Produktstamm,
        # Einheit der Variante (wie create_order und Paket 2, A5)
        assert _b6_zeilen(bestellung) == [
            (1, "BIO Snackbox | Amaranth", Decimal("2.000"), "STUECK", Decimal("4.20"), "REDUZIERT", Decimal("8.40")),
            (2, "Kresse Schale — 12er Mehrwegkiste", Decimal("1.000"), "KISTE_12", Decimal("30.00"), "REDUZIERT", Decimal("30.00")),
            (3, "IFCO-Kiste", Decimal("1.000"), "STUECK", Decimal("4.00"), "STANDARD", Decimal("4.00")),
        ]
        assert bestellung["total_net"] == Decimal("42.40")

    def test_zweiter_lauf_am_selben_tag_legt_nichts_doppelt_an(self, client):
        kunde = _b6_kunde(client)
        abo_id = _b6_abo_db(kunde["id"], self._drei_positionen(client, kunde))

        _b6_lauf(_B6_DO)
        zweiter = _b6_lauf(_B6_DO)

        assert (zweiter["erstellt"], zweiter["bereits_vorhanden"]) == (0, 1)
        [bestellung] = _b6_bestellungen(abo_id)
        assert len(bestellung["lines"]) == 3

    def test_lauf_liest_die_positionen_nicht_den_kopf(self, client):
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kresse = _b6_produkt(client, "Kresse Schale", "B6-KRESSE", "3.00")
        abo_id = _b6_abo_db(kunde["id"], [{"product_id": kresse["id"], "menge": 2}],
                            product_id=uuid.UUID(snack["id"]), menge=Decimal("9"))

        _b6_anlegen(abo_id)

        [bestellung] = _b6_bestellungen(abo_id)
        assert [(l["product_id"], l["quantity"]) for l in bestellung["lines"]] == [
            (kresse["id"], Decimal("2.000"))]

    def test_abo_ohne_position_liefert_seinen_kopf(self, client):
        """Rückfall, falls das Nachtragen beim Start scheiterte (_auto_migrate
        loggt nur): Das Abo liefert weiter sein Kopfprodukt statt nichts."""
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        abo_id = _b6_abo_db(kunde["id"], [], product_id=uuid.UUID(snack["id"]),
                            menge=Decimal("2"), einheit="STUECK")

        _b6_anlegen(abo_id)

        [bestellung] = _b6_bestellungen(abo_id)
        assert _b6_zeilen(bestellung) == [
            (1, "BIO Snackbox | Amaranth", Decimal("2.000"), "STUECK", Decimal("4.50"), "REDUZIERT", Decimal("9.00"))]

    def test_eine_kaputte_position_ueberspringt_das_ganze_abo(self, client):
        """Alles oder nichts: keine Teillieferung ohne Hinweis. Die Meldung nennt die Position."""
        from app.tasks.subscription_tasks import AboUebersprungen
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kresse = _b6_produkt(client, "Kresse Schale", "B6-KRESSE", "3.00")
        abo_id = _b6_abo_db(kunde["id"], [
            {"product_id": snack["id"], "menge": 2},
            {"product_id": kresse["id"], "menge": 1},
        ])
        r = client.delete(f"/api/v1/products/{kresse['id']}")  # Soft-Delete: is_active = False
        assert r.status_code == 204, r.text

        with pytest.raises(AboUebersprungen, match="^Position 2: Produkt Kresse Schale ist deaktiviert$"):
            _b6_anlegen(abo_id)
        assert _b6_bestellungen() == []

    def test_lauf_meldet_das_kaputte_abo_und_beliefert_die_anderen(self, client):
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kresse = _b6_produkt(client, "Kresse Schale", "B6-KRESSE", "3.00")
        gut = _b6_abo_db(kunde["id"], [{"product_id": snack["id"], "menge": 2},
                                       {"product_id": snack["id"], "menge": 1, "einheit": "SCHALE"}])
        kaputt = _b6_abo_db(kunde["id"], [{"product_id": snack["id"], "menge": 2},
                                          {"menge": 1}])

        ergebnis = _b6_lauf(_B6_DO)

        assert ergebnis["erstellt"] == 1
        assert ergebnis["uebersprungen"] == [{
            "abo_id": kaputt, "kunde": "Café Kleinberger",
            "grund": "Position 2: Abo hat weder Produkt noch Sorte",
        }]
        assert len(_b6_bestellungen(gut)[0]["lines"]) == 2
        assert _b6_bestellungen(kaputt) == []


class TestB6Pfand:
    """Pfand aus dem Abo folgt der Pfandabrechnung des Kunden über die normalen
    Wege: Die Abo-Bestellung trägt die Pfandposition wie jede Bestellung, die
    Rechnung lässt sie bei IFCO-Clearing weg (invoice_service.ist_clearing_pfand),
    das Leergutkonto (MONATLICH) bucht beim Übergang nach GELIEFERT. Der Lauf
    selbst kennt pfand_abrechnung nicht."""

    def _rechnungszeilen(self, client, kunde):
        from sqlalchemy import select
        from app.models.invoice import InvoiceLine
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        pfand = _b6_pfandkiste(client)
        abo_id = _b6_abo_db(kunde["id"], [{"product_id": snack["id"], "menge": 2},
                                          {"product_id": pfand["id"], "menge": 2}])
        _b6_lauf(_B6_DO)
        [bestellung] = _b6_bestellungen(abo_id)
        assert [l["beschreibung"] for l in bestellung["lines"]] == [
            "BIO Snackbox | Amaranth", "IFCO-Kiste"]

        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")
        assert r.status_code == 201, r.text
        with TestingSessionLocal() as db:
            return [
                (l.description, l.is_deposit, l.tax_rate.value)
                for l in db.execute(select(InvoiceLine).where(
                    InvoiceLine.invoice_id == uuid.UUID(r.json()["id"]))).scalars().all()
            ]

    def test_ifco_clearing_pfand_steht_nicht_auf_der_rechnung(self, client):
        kunde = _b6_kunde(client, pfand_abrechnung="KEINE")
        assert self._rechnungszeilen(client, kunde) == [
            ("BIO Snackbox | Amaranth", False, "REDUZIERT")]

    def test_pfand_je_lieferung_steht_auf_der_rechnung(self, client):
        kunde = _b6_kunde(client, pfand_abrechnung="JE_LIEFERUNG")
        assert sorted(self._rechnungszeilen(client, kunde)) == [
            ("BIO Snackbox | Amaranth", False, "REDUZIERT"), ("IFCO-Kiste", True, "STANDARD")]
