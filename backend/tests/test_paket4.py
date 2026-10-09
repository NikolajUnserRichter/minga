"""Paket 4 — Gernots Rückmeldungen vom 08. und 09.10.2026 (Abgleich aller Wünsche).

Gemeinsame Testdatei aller Abschnitte. Klassen und Helfer tragen ein
Abschnitts-Präfix (TestP4A…/_p4a_ für Abschnitt A, TestP4B…/_p4b_ usw.):
ein gleichnamiger Helfer würde still ersetzt. Jeder Abschnitt bringt seine
Importe selbst mit. Keine autouse-Fixture.
"""


# ============================================================
# Abschnitt A — Tagesplan: Mix-Auflösung (G11, G74, G13) und
# „Gepackt“/„Ausgeliefert“ auch für Entwürfe (G10)
# ============================================================
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from tests.conftest import TestingSessionLocal


@pytest.fixture()
def _p4a_ohne_celery():
    """Anlegen und Bestätigen stoßen per Celery ein Forecast-Update an; ohne
    Redis wartet jeder Aufruf auf Wiederholungen. Für Abschnitt A ohne Belang
    (wie _a4_ohne_celery in test_gernot_261008_paket2.py)."""
    with patch("app.tasks.forecast_tasks.update_forecast_from_order.delay"):
        yield


def _p4a_heute():
    """Kalendertag des Servers (Europe/Berlin), wie Packtag und Lieferdatum."""
    from app.services.order_status_service import heute_berlin
    return heute_berlin()


def _p4a_basiseinheit():
    """Basiseinheit 'G' — die Produktanlage verlangt sie, es gibt keinen
    API-Weg dorthin (wie base_unit in test_gernot_260817.py)."""
    from app.models.unit import UnitCategory, UnitOfMeasure
    with TestingSessionLocal() as db:
        if not db.query(UnitOfMeasure).filter_by(code="G").first():
            db.add(UnitOfMeasure(code="G", name="Gramm", symbol="g",
                                 category=UnitCategory.WEIGHT, is_base_unit=True))
            db.commit()


def _p4a_produkt(client, name, sku, kategorie="MICROGREEN"):
    _p4a_basiseinheit()
    r = client.post("/api/v1/products", json={
        "sku": sku, "name": name, "category": kategorie, "base_price": 3.0,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _p4a_mix(client, sorten, name="BIO Genussmix (VPE 6)", sku="P4A-MIX"):
    """Mix wie Gernot ihn am 09.10. angelegt hat: Kategorie BUNDLE, Formular
    offen, Komponenten über die Stückliste. sorten: [(Produkt, Anteil)].
    Zurück kommt der Stand beim Öffnen des Formulars (is_bundle false)."""
    mix = _p4a_produkt(client, name, sku, kategorie="BUNDLE")
    for sorte, anteil in sorten:
        r = client.post(f"/api/v1/products/{mix['id']}/bundle-components", json={
            "child_product_id": sorte["id"], "quantity": anteil,
        })
        assert r.status_code == 201, r.text
    return mix


def _p4a_speichern(client, offen, *, altes_formular=False, **aenderung):
    """PATCH wie „Speichern“ im Produktformular (Products.tsx, handleSubmit).

    `offen` ist der Stand beim Öffnen. Das alte Formular (bis Paket 4) schickte
    is_bundle aus diesem Stand mit, das neue schickt es nicht mehr."""
    daten = {
        "name": offen["name"], "category": offen["category"],
        "base_price": offen["base_price"], "tax_rate": offen["tax_rate"],
        "is_variable_bundle": offen["is_variable_bundle"],
        "variable_bundle_min_slots": 1, "variable_bundle_max_slots": 8,
        "is_active": True, "is_sellable": True,
    }
    if altes_formular:
        daten["is_bundle"] = offen["is_bundle"]
    daten.update(aenderung)
    r = client.patch(f"/api/v1/products/{offen['id']}", json=daten)
    assert r.status_code == 200, r.text
    return r.json()


def _p4a_kennzeichen_wie_in_prod(produkt):
    """Stand der 24 Mixe in Produktion (09.10.2026): Stückliste da, is_bundle 0."""
    from app.models.product import Product
    with TestingSessionLocal() as db:
        db.get(Product, uuid.UUID(produkt["id"])).is_bundle = False
        db.commit()


def _p4a_kunde(client, name=None):
    r = client.post("/api/v1/sales/customers", json={
        "name": name or f"Packkunde {uuid.uuid4().hex[:6]}", "typ": "GASTRO",
    })
    assert r.status_code == 201, r.text
    return r.json()


def _p4a_bestellung(client, liefertag, positionen=(("Erbsen-Schale", 5),), *, bestaetigen=False):
    """Bestellung wie aus Gernots Formular: ENTWURF.

    positionen: (Produkt-JSON oder freier Name, Menge); leer = ohne Position."""
    lines = []
    for ware, menge in positionen:
        zeile = {"quantity": menge, "unit": "STK", "unit_price": 3.0, "tax_rate": "REDUZIERT"}
        if isinstance(ware, dict):
            zeile.update(product_id=ware["id"], product_name=ware["name"])
        else:
            zeile.update(product_name=ware)
        lines.append(zeile)
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": _p4a_kunde(client)["id"],
        "requested_delivery_date": liefertag.isoformat(),
        "lines": lines,
    })
    assert r.status_code == 201, r.text
    order = r.json()
    if bestaetigen:
        r = client.post(f"/api/v1/sales/orders/{order['id']}/confirm")
        assert r.status_code == 200, r.text
        order = r.json()
    return order


def _p4a_sortenbedarf(client, packtag):
    """Sortenbedarf im Tagesplan: {Sorte: Menge} (packaging-plan, komponenten)."""
    r = client.get("/api/v1/production/packaging-plan",
                   params={"target_date": packtag.isoformat()})
    assert r.status_code == 200, r.text
    return {k["product_name"]: k["total_quantity"] for k in r.json()["komponenten"]}


def _p4a_abo_lieferung(kunde, produkt, menge, liefertag):
    """Abo mit einer Position anlegen und die Lieferung erzeugen wie der
    Abo-Lauf (subscription_tasks._create_order_from_subscription, B6)."""
    from app.models.customer import Subscription, SubscriptionInterval, SubscriptionItem
    from app.tasks.subscription_tasks import _create_order_from_subscription
    with TestingSessionLocal() as db:
        sub = Subscription(
            kunde_id=uuid.UUID(kunde["id"]), product_id=uuid.UUID(produkt["id"]),
            menge=Decimal(str(menge)), einheit="STUECK",
            intervall=SubscriptionInterval.WOECHENTLICH,
            liefertage=[liefertag.weekday()], gueltig_von=liefertag,
        )
        sub.positionen.append(SubscriptionItem(
            position=1, product_id=uuid.UUID(produkt["id"]),
            menge=Decimal(str(menge)), einheit="STUECK",
        ))
        db.add(sub)
        db.flush()
        order = _create_order_from_subscription(db, sub, liefertag)
        db.commit()
        return order.order_number


@pytest.mark.usefixtures("_p4a_ohne_celery")
class TestP4AStueckliste:
    """A.1 (G11, G74, G13): Ein Artikel mit Stückliste ist ein festes Bundle.

    Prod 09.10.2026: 25 Artikel mit Stückliste, 24 davon is_bundle=0. Das
    Formular schickte beim Speichern is_bundle=false aus dem Stand vom Öffnen
    und setzte das Kennzeichen zurück, das add_bundle_component gesetzt hatte.
    Der Tagesplan löst nur Bundles auf und zeigte den Mix ungeteilt."""

    def test_altes_formular_setzt_kennzeichen_nicht_zurueck(self, client):
        erbse = _p4a_produkt(client, "BIO Snackbox | Erbse", "P4A-ERB")
        offen = _p4a_mix(client, [(erbse, 1)])

        gespeichert = _p4a_speichern(client, offen, altes_formular=True)
        assert gespeichert["is_bundle"] is True

    def test_speichern_heilt_den_prod_zustand(self, client):
        """Einer der 24 Mixe nach dem Deploy: einmal speichern genügt."""
        erbse = _p4a_produkt(client, "BIO Snackbox | Erbse", "P4A-ERB")
        offen = _p4a_mix(client, [(erbse, 1)])
        _p4a_kennzeichen_wie_in_prod(offen)

        gespeichert = _p4a_speichern(client, offen)
        assert gespeichert["is_bundle"] is True

    def test_sortenbedarf_loest_gespeicherten_mix_auf(self, client):
        """Gernot (B1): „BIO Genussmix (VPE 6): 10“ → Einzelsorten in Stück."""
        heute = _p4a_heute()
        erbse = _p4a_produkt(client, "BIO Snackbox | Erbse", "P4A-ERB")
        radieschen = _p4a_produkt(client, "BIO Snackbox | Radieschen", "P4A-RAD")
        offen = _p4a_mix(client, [(erbse, 1), (radieschen, 1)])
        _p4a_speichern(client, offen, altes_formular=True)
        _p4a_bestellung(client, heute + timedelta(days=1), [(offen, 10)])

        assert _p4a_sortenbedarf(client, heute) == {
            "BIO Snackbox | Erbse": 10, "BIO Snackbox | Radieschen": 10,
        }

    def test_abo_lieferung_eines_mixes_wird_aufgeloest(self, client):
        """G13: Die Abo-Lieferung trägt das Abo-Produkt; ist es ein Mix, stehen
        im Sortenbedarf seine Sorten."""
        heute = _p4a_heute()
        erbse = _p4a_produkt(client, "BIO Snackbox | Erbse", "P4A-ERB")
        offen = _p4a_mix(client, [(erbse, 3)], name="BIO Microgreens Mix KKER (VPE 12)", sku="P4A-KKER")
        _p4a_speichern(client, offen, altes_formular=True)
        _p4a_abo_lieferung(_p4a_kunde(client, "Dorint Testhotel"), offen, 4, heute)

        assert _p4a_sortenbedarf(client, heute) == {"BIO Snackbox | Erbse": 12}

    def test_variabel_ist_kein_festes_bundle(self, client):
        """Umschalten auf „Variabel (Gastrotray)“: die Bestellung wählt die
        Sorten, eine alte Stückliste gilt nicht mehr."""
        erbse = _p4a_produkt(client, "BIO Snackbox | Erbse", "P4A-ERB")
        offen = _p4a_mix(client, [(erbse, 1)], name="BIO Gastrotray (1-8 Sorten)", sku="P4A-TRAY")

        gespeichert = _p4a_speichern(client, offen, is_variable_bundle=True)
        assert (gespeichert["is_variable_bundle"], gespeichert["is_bundle"]) == (True, False)

    def test_ohne_stueckliste_bleibt_einzelartikel(self, client):
        """Charakterisierung: „BIO Kiste | Erbse (VPE 6)“ ohne Stückliste bleibt,
        was er ist, und steht als Artikel im Sortenbedarf."""
        heute = _p4a_heute()
        offen = _p4a_produkt(client, "BIO Kiste | Erbse (VPE 6)", "P4A-KISTE", kategorie="BUNDLE")

        gespeichert = _p4a_speichern(client, offen, altes_formular=True)
        assert gespeichert["is_bundle"] is False
        _p4a_bestellung(client, heute + timedelta(days=1), [(offen, 2)])
        assert _p4a_sortenbedarf(client, heute) == {"BIO Kiste | Erbse (VPE 6)": 2}
