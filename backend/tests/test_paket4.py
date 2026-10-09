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


def _p4a_status(client, order, status, **extra):
    """Derselbe Aufruf wie die Knöpfe im Tagesplan (salesApi.updateOrderStatus)."""
    return client.post(f"/api/v1/sales/orders/{order['id']}/status",
                       json={"status": status, **extra})


def _p4a_lesen(client, order):
    r = client.get(f"/api/v1/sales/orders/{order['id']}")
    assert r.status_code == 200, r.text
    return r.json()


def _p4a_positionen_loeschen(order):
    """Entwurf ohne Positionen. Die Schnittstelle legt keinen an (400), Altbestand
    und Importe kennen ihn — darum direkt in der DB."""
    from sqlalchemy import delete
    from app.models.order import OrderLine
    with TestingSessionLocal() as db:
        db.execute(delete(OrderLine).where(OrderLine.order_id == uuid.UUID(order["id"])))
        db.commit()


def _p4a_audit(client, order):
    """(Aktion, alter Status, neuer Status, Grund) je Statuseintrag, sortiert."""
    r = client.get(f"/api/v1/sales/orders/{order['id']}/audit-log")
    assert r.status_code == 200, r.text
    return sorted(
        (e["action"], (e["old_values"] or {}).get("status"),
         (e["new_values"] or {}).get("status"), e["reason"])
        for e in r.json() if (e["new_values"] or {}).get("status")
    )


@pytest.mark.usefixtures("_p4a_ohne_celery")
class TestP4AEntwurfPacken:
    """A.3 (G10): „Gepackt“ und „Ausgeliefert“ im Tagesplan bestätigen einen
    Entwurf im selben Schritt — über die eine Statusregel (order_status_service),
    mit eigenem Audit-Eintrag CONFIRM, nur bis zum Liefertag. Ohne das
    Kennzeichen bleibt alles wie in Paket 2."""

    def test_gepackt_bestaetigt_den_entwurf(self, client):
        morgen = _p4a_heute() + timedelta(days=1)
        o = _p4a_bestellung(client, morgen)

        r = _p4a_status(client, o, "IN_PRODUKTION", reason="Im Tagesplan als gepackt markiert",
                        entwurf_bestaetigen=True)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "IN_PRODUKTION"
        assert r.json()["confirmed_delivery_date"] == morgen.isoformat()
        assert _p4a_audit(client, o) == [
            ("CONFIRM", "ENTWURF", "BESTAETIGT", "Beim Packen im Tagesplan bestätigt"),
            ("STATUS_CHANGE", "BESTAETIGT", "IN_PRODUKTION", "Im Tagesplan als gepackt markiert"),
        ]

    def test_ausgeliefert_bestaetigt_den_entwurf(self, client):
        heute = _p4a_heute()
        o = _p4a_bestellung(client, heute)

        r = _p4a_status(client, o, "GELIEFERT", entwurf_bestaetigen=True)
        assert r.status_code == 200, r.text
        assert (r.json()["status"], r.json()["actual_delivery_date"]) == ("GELIEFERT", heute.isoformat())
        assert _p4a_audit(client, o) == [
            ("CONFIRM", "ENTWURF", "BESTAETIGT", "Beim Ausliefern im Tagesplan bestätigt"),
            ("STATUS_CHANGE", "BESTAETIGT", "GELIEFERT", None),
        ]

    def test_gepackter_entwurf_verlaesst_den_sortenbedarf(self, client):
        """Gernot (A4): gepackt → sofort raus aus dem Sortenbedarf, auch als Entwurf."""
        heute = _p4a_heute()
        morgen = heute + timedelta(days=1)
        _p4a_bestellung(client, morgen, [("Erbsen-Schale", 3)])
        gepackt = _p4a_bestellung(client, morgen, [("Erbsen-Schale", 5)])
        assert _p4a_sortenbedarf(client, heute) == {"Erbsen-Schale": 8}

        r = _p4a_status(client, gepackt, "IN_PRODUKTION", entwurf_bestaetigen=True)
        assert r.status_code == 200, r.text
        assert _p4a_sortenbedarf(client, heute) == {"Erbsen-Schale": 3}

    def test_entwurf_ohne_positionen_wird_nicht_gepackt(self, client):
        morgen = _p4a_heute() + timedelta(days=1)
        o = _p4a_bestellung(client, morgen)
        _p4a_positionen_loeschen(o)

        r = _p4a_status(client, o, "IN_PRODUKTION", entwurf_bestaetigen=True)
        assert r.status_code == 400
        assert r.json()["detail"] == "Bestellung ohne Positionen kann nicht bestätigt werden"
        assert _p4a_lesen(client, o)["status"] == "ENTWURF"

    def test_scheitert_das_liefern_bleibt_der_entwurf(self, client):
        """Bestätigung und Statuswechsel in einer Transaktion: alles oder nichts."""
        heute = _p4a_heute()
        morgen = heute + timedelta(days=1)
        o = _p4a_bestellung(client, heute)

        r = _p4a_status(client, o, "GELIEFERT", entwurf_bestaetigen=True,
                        actual_delivery_date=morgen.isoformat())
        assert r.status_code == 400
        assert r.json()["detail"] == f"Lieferdatum {morgen:%d.%m.%Y} liegt in der Zukunft"
        best = _p4a_lesen(client, o)
        assert (best["status"], best["confirmed_delivery_date"]) == ("ENTWURF", None)
        assert _p4a_audit(client, o) == []

    def test_vergangener_entwurf_wird_im_tagesplan_nicht_bestaetigt(self, client):
        """Prod 09.10.2026: 7 Entwürfe mit Liefertag vor heute, u. a. die falsch
        erfasste Bierbichler-Bestellung (G80) und vier LfA-Abo-Lieferungen. Ein
        Klick im Tagesplan eines vergangenen Tages darf sie weder bestätigen
        noch liefern: aus Geliefert führt kein Weg zurück."""
        gestern = _p4a_heute() - timedelta(days=1)
        o = _p4a_bestellung(client, gestern)
        meldung = (f"Entwurf mit Liefertag {gestern:%d.%m.%Y} liegt in der Vergangenheit "
                   "— erst in der Bestellliste bestätigen oder stornieren")

        # Wie der Tagesplan an einem vergangenen Tag: Lieferdatum = dieser Tag
        r = _p4a_status(client, o, "GELIEFERT", entwurf_bestaetigen=True,
                        actual_delivery_date=gestern.isoformat())
        assert (r.status_code, r.json()["detail"]) == (400, meldung)
        r = _p4a_status(client, o, "IN_PRODUKTION", entwurf_bestaetigen=True)
        assert (r.status_code, r.json()["detail"]) == (400, meldung)
        best = _p4a_lesen(client, o)
        assert (best["status"], best["confirmed_delivery_date"]) == ("ENTWURF", None)
        assert _p4a_audit(client, o) == []

    def test_ohne_kennzeichen_gilt_die_regel_aus_paket_2(self, client):
        """Charakterisierung: Bestellliste, Sammelaktion und Fremd-Clients
        schicken das Kennzeichen nicht — ENTWURF → Gepackt bleibt verboten."""
        o = _p4a_bestellung(client, _p4a_heute() + timedelta(days=1))

        r = _p4a_status(client, o, "IN_PRODUKTION")
        assert r.status_code == 400
        assert r.json()["detail"] == "Statuswechsel nicht möglich: Entwurf → Gepackt"
        assert _p4a_lesen(client, o)["status"] == "ENTWURF"

    def test_bestaetigte_bestellung_wird_nicht_nochmal_bestaetigt(self, client):
        """Charakterisierung: das Kennzeichen wirkt nur auf Entwürfe."""
        o = _p4a_bestellung(client, _p4a_heute() + timedelta(days=1), bestaetigen=True)

        r = _p4a_status(client, o, "IN_PRODUKTION", entwurf_bestaetigen=True)
        assert r.status_code == 200, r.text
        assert [a for a, *_ in _p4a_audit(client, o)] == ["CONFIRM", "STATUS_CHANGE"]

    def test_bestaetigen_ueber_confirm_unveraendert(self, client):
        """Charakterisierung: POST /confirm läuft jetzt über dieselbe Funktion
        (order_status_service.bestaetigen) — Antworten wie bisher."""
        morgen = _p4a_heute() + timedelta(days=1)
        o = _p4a_bestellung(client, morgen)

        r = client.post(f"/api/v1/sales/orders/{o['id']}/confirm")
        assert r.status_code == 200, r.text
        assert (r.json()["status"], r.json()["confirmed_delivery_date"]) == ("BESTAETIGT", morgen.isoformat())
        assert _p4a_audit(client, o) == [("CONFIRM", "ENTWURF", "BESTAETIGT", None)]

        r = client.post(f"/api/v1/sales/orders/{o['id']}/confirm")
        assert r.status_code == 400
        assert r.json()["detail"] == "Bestellung hat Status Bestätigt, kann nicht bestätigt werden"

        leer = _p4a_bestellung(client, morgen)
        _p4a_positionen_loeschen(leer)
        r = client.post(f"/api/v1/sales/orders/{leer['id']}/confirm")
        assert r.status_code == 400
        assert r.json()["detail"] == "Bestellung ohne Positionen kann nicht bestätigt werden"


def _p4a_tagesplan(client, tag):
    r = client.get("/api/v1/production/day-plan", params={"target_date": tag.isoformat()})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.usefixtures("_p4a_ohne_celery")
class TestP4ATagesplanKnoepfe:
    """A.4 (G10): Der Tagesplan erfährt vom Server, welche Knöpfe eine Zeile
    bekommt (gepackt_moeglich, ausgeliefert_moeglich) — dieselbe Regel wie
    setze_status_im_tagesplan. `packbar` bleibt wie in Paket 2."""

    def test_knoepfe_je_status(self, client):
        heute = _p4a_heute()
        # Same-Day: Pack- und Liefertag heute, die Zeile steht in beiden Karten
        entwurf = _p4a_bestellung(client, heute)
        bestaetigt = _p4a_bestellung(client, heute, bestaetigen=True)
        gepackt = _p4a_bestellung(client, heute, bestaetigen=True)
        geliefert = _p4a_bestellung(client, heute, bestaetigen=True)
        assert _p4a_status(client, gepackt, "IN_PRODUKTION").status_code == 200
        assert _p4a_status(client, geliefert, "GELIEFERT").status_code == 200

        plan = _p4a_tagesplan(client, heute)
        verpacken = {z["order_number"]: z for z in plan["verpacken"]}
        ausliefern = {z["order_number"]: z for z in plan["ausliefern"]}

        assert sorted(verpacken) == sorted([entwurf["order_number"], bestaetigt["order_number"]])
        for o in (entwurf, bestaetigt):
            assert verpacken[o["order_number"]]["gepackt_moeglich"] is True
        assert verpacken[entwurf["order_number"]]["packbar"] is False

        knoepfe = {
            nr: (z["gepackt_moeglich"], z["ausgeliefert_moeglich"]) for nr, z in ausliefern.items()
        }
        assert knoepfe == {
            entwurf["order_number"]: (True, True),
            bestaetigt["order_number"]: (True, True),
            gepackt["order_number"]: (False, True),
            geliefert["order_number"]: (False, False),
        }

    def test_erledigte_bekommen_keinen_knopf(self, client):
        heute = _p4a_heute()
        gepackt = _p4a_bestellung(client, heute + timedelta(days=1))
        assert _p4a_status(client, gepackt, "IN_PRODUKTION", entwurf_bestaetigen=True).status_code == 200

        zeile = _p4a_tagesplan(client, heute)["verpacken_erledigt"][0]
        assert (zeile["order_number"], zeile["gepackt_moeglich"]) == (gepackt["order_number"], False)

    def test_vergangener_entwurf_bekommt_keinen_knopf(self, client):
        """Tagesplan eines vergangenen Tages (Prod 09.10.2026: 7 Entwürfe mit
        Liefertag vor heute): ein Entwurf bekommt weder „Gepackt“ noch
        „Ausgeliefert“. Eine bestätigte Bestellung desselben Tages behält
        beide Knöpfe, ihre Lieferung lässt sich nachtragen (Paket 2)."""
        gestern = _p4a_heute() - timedelta(days=1)
        # Packtag = Liefertag (Same-Day-Regel beim Anlegen): beide stehen in
        # Verpacken und Ausliefern von gestern
        entwurf = _p4a_bestellung(client, gestern)
        bestaetigt = _p4a_bestellung(client, gestern, bestaetigen=True)

        plan = _p4a_tagesplan(client, gestern)
        knoepfe = {
            karte: {z["order_number"]: (z["gepackt_moeglich"], z["ausgeliefert_moeglich"]) for z in plan[karte]}
            for karte in ("verpacken", "ausliefern")
        }
        erwartet = {entwurf["order_number"]: (False, False), bestaetigt["order_number"]: (True, True)}
        assert knoepfe == {"verpacken": erwartet, "ausliefern": erwartet}


# ============================================================
# B — Abrechnung: Doppelabrechnung, Lieferschein beim Ausliefern,
#     Rechnungsdatum beim Festschreiben
# ============================================================

import uuid as _p4b_uuid
from datetime import date as _p4b_date, timedelta as _p4b_timedelta

from tests.conftest import TestingSessionLocal as _P4B_Session


def _p4b_kunde(client, name="Dorint Hotels Betriebs GmbH", **extra):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "GASTRO", **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _p4b_bestellung(client, kunde, liefertag=None, menge=10, preis="2.50"):
    """Bestätigte Bestellung mit einer Freitextposition (10 × 2,50 € zu 7 %)."""
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"],
        "requested_delivery_date": (liefertag or _p4b_date.today()).isoformat(),
        "lines": [{"product_name": "Erbsen-Schale", "quantity": menge, "unit": "STK",
                   "unit_price": preis, "tax_rate": "REDUZIERT"}],
    })
    assert r.status_code == 201, r.text
    bestellung = r.json()
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/confirm")
    assert r.status_code == 200, r.text
    return r.json()


def _p4b_status(client, bestellung, status, **extra):
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/status", json={"status": status, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _p4b_fakturiert(client, kunde):
    """Bestellung, die außerhalb von NovaERP abgerechnet ist (wie die 574
    DATEV-Bestellungen in minga): geliefert, dann FAKTURIERT."""
    bestellung = _p4b_bestellung(client, kunde)
    _p4b_status(client, bestellung, "GELIEFERT")
    return _p4b_status(client, bestellung, "FAKTURIERT")


def _p4b_rechnungen(kunde):
    from app.models.invoice import Invoice
    with _P4B_Session() as db:
        return db.query(Invoice).filter(Invoice.customer_id == _p4b_uuid.UUID(kunde["id"])).count()


def _p4b_meldung(bestellung):
    return (
        f"Bestellung {bestellung['order_number']} ist als „Fakturiert“ gekennzeichnet: "
        "Sie ist außerhalb von NovaERP abgerechnet (z. B. über DATEV). "
        "Eine Rechnung hier würde sie doppelt berechnen."
    )


class TestP4BFakturiert:
    """G66: FAKTURIERT heißt abgerechnet — auch ohne Rechnung in NovaERP.
    Kein Weg legt dafür eine Rechnung an oder schreibt sie fest."""

    def test_rechnung_aus_bestellung_gesperrt(self, client):
        kunde = _p4b_kunde(client)
        bestellung = _p4b_fakturiert(client, kunde)

        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")

        assert r.status_code == 409, r.text
        assert r.json()["detail"] == _p4b_meldung(bestellung)
        assert _p4b_rechnungen(kunde) == 0

    def test_rechnung_von_hand_mit_bestellbezug_gesperrt(self, client):
        kunde = _p4b_kunde(client)
        bestellung = _p4b_fakturiert(client, kunde)

        r = client.post("/api/v1/invoices", json={
            "customer_id": kunde["id"], "order_id": bestellung["id"],
            "invoice_date": _p4b_date.today().isoformat(),
            "lines": [{"description": "Erbsen-Schale", "quantity": 10, "unit": "STK",
                       "unit_price": "2.50", "tax_rate": "REDUZIERT"}],
        })

        assert r.status_code == 409, r.text
        assert r.json()["detail"] == _p4b_meldung(bestellung)
        assert _p4b_rechnungen(kunde) == 0

    def test_position_aus_fakturierter_bestellung_gesperrt(self, client):
        """Eine Bestellposition (order_item_id) holt die Bestellung über einen
        anderen Entwurf herein — derselbe Schutz."""
        kunde = _p4b_kunde(client)
        bestellung = _p4b_fakturiert(client, kunde)
        zeile_id = client.get(f"/api/v1/sales/orders/{bestellung['id']}").json()["lines"][0]["id"]
        r = client.post("/api/v1/invoices", json={
            "customer_id": kunde["id"], "invoice_date": _p4b_date.today().isoformat()})
        assert r.status_code == 201, r.text
        entwurf = r.json()

        r = client.post(f"/api/v1/invoices/{entwurf['id']}/lines", json={
            "description": "Erbsen-Schale", "quantity": 10, "unit": "STK",
            "unit_price": "2.50", "tax_rate": "REDUZIERT", "order_item_id": zeile_id})

        assert r.status_code == 409, r.text
        assert r.json()["detail"] == _p4b_meldung(bestellung)
        assert client.get(f"/api/v1/invoices/{entwurf['id']}").json()["lines"] == []

    def test_entwurf_einer_spaeter_fakturierten_bestellung_nicht_festschreibbar(self, client):
        """Altfall: Der Entwurf entstand, bevor die Bestellung als abgerechnet
        gekennzeichnet wurde. Er bekommt keine Nummer."""
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde)
        _p4b_status(client, bestellung, "GELIEFERT")
        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")
        assert r.status_code == 201, r.text
        entwurf = r.json()
        _p4b_status(client, bestellung, "FAKTURIERT")

        r = client.post(f"/api/v1/invoices/{entwurf['id']}/finalize")

        assert r.status_code == 409, r.text
        assert r.json()["detail"] == _p4b_meldung(bestellung) + " Diesen Entwurf verwerfen."
        nachher = client.get(f"/api/v1/invoices/{entwurf['id']}").json()
        assert nachher["status"] == "ENTWURF"
        assert nachher["invoice_number"].startswith("ENTWURF-")

    def test_gelieferte_bestellung_bleibt_abrechenbar(self, client):
        """Wächter: nur FAKTURIERT sperrt."""
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde)
        _p4b_status(client, bestellung, "GELIEFERT")

        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")

        assert r.status_code == 201, r.text

    def test_sammellauf_laesst_fakturierte_aus(self, client):
        """Wächter (Spec-Nachtrag 08.10.): Sammel- und Monatslauf schlossen
        FAKTURIERT schon vorher aus."""
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde, liefertag=_p4b_date.today())
        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes", json={})
        assert r.status_code == 201, r.text
        _p4b_status(client, bestellung, "GELIEFERT")
        _p4b_status(client, bestellung, "FAKTURIERT")
        heute = _p4b_date.today()

        r = client.post("/api/v1/invoices/batch-run/preview", json={
            "period_from": (heute - _p4b_timedelta(days=31)).isoformat(),
            "period_to": heute.isoformat()})

        assert r.status_code == 200, r.text
        assert r.json()["kunden"] == []


from decimal import Decimal as _P4B_Decimal


def _p4b_altentwurf(kunde, nummer, datum, ziel_tage):
    """Entwurf, wie ihn der Code vor Paket 3 anlegte: echte RE-Nummer schon
    beim Anlegen (Bestand wie RE-2026-00003). Direkt per ORM — über die API
    entsteht so ein Entwurf nicht mehr."""
    from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus, TaxRate
    with _P4B_Session() as db:
        rechnung = Invoice(
            invoice_number=nummer, customer_id=_p4b_uuid.UUID(kunde["id"]),
            invoice_date=datum, due_date=datum + _p4b_timedelta(days=ziel_tage),
            status=InvoiceStatus.ENTWURF,
        )
        db.add(rechnung)
        db.flush()
        db.add(InvoiceLine(
            invoice_id=rechnung.id, position=1, description="Erbsen-Schale",
            quantity=_P4B_Decimal("10"), unit="STK", unit_price=_P4B_Decimal("2.50"),
            tax_rate=TaxRate.REDUZIERT, line_total=_P4B_Decimal("25.00"),
        ))
        db.commit()
        return str(rechnung.id)


def _p4b_heute_festsetzen(monkeypatch, tag):
    monkeypatch.setattr("app.services.invoice_service._heute_berlin", lambda: tag)


def _p4b_festschreiben(client, rechnung_id):
    r = client.post(f"/api/v1/invoices/{rechnung_id}/finalize")
    assert r.status_code == 200, r.text
    return r.json()


class TestP4BAusstellungsdatum:
    """G64: Rechnungsdatum ist der Tag des Festschreibens (Europe/Berlin),
    auch bei einem Altentwurf mit RE-Nummer. Das Zahlungsziel in Tagen bleibt."""

    def test_altentwurf_mit_nummer_bekommt_den_tag_der_ausstellung(self, client, monkeypatch):
        """Wie RE-2026-00003: angelegt 07.10., festgeschrieben 09.10."""
        kunde = _p4b_kunde(client, "Ökoring Handels GmbH")
        alt_id = _p4b_altentwurf(kunde, "RE-2026-00003", _p4b_date(2026, 10, 7), 14)
        _p4b_heute_festsetzen(monkeypatch, _p4b_date(2026, 10, 9))

        rechnung = _p4b_festschreiben(client, alt_id)

        assert rechnung["invoice_number"] == "RE-2026-00003"
        assert rechnung["invoice_date"] == "2026-10-09"
        assert rechnung["due_date"] == "2026-10-23"

    def test_zahlungsziel_in_tagen_bleibt(self, client, monkeypatch):
        kunde = _p4b_kunde(client, "Ökoring Handels GmbH")
        alt_id = _p4b_altentwurf(kunde, "RE-2026-00004", _p4b_date(2026, 9, 1), 30)
        _p4b_heute_festsetzen(monkeypatch, _p4b_date(2026, 10, 9))

        rechnung = _p4b_festschreiben(client, alt_id)

        assert (rechnung["invoice_date"], rechnung["due_date"]) == ("2026-10-09", "2026-11-08")

    def test_neuer_entwurf_wie_bisher(self, client, monkeypatch):
        """Wächter: Entwurf mit Platzhalter — Nummer und Datum beim Festschreiben."""
        kunde = _p4b_kunde(client, "Ökoring Handels GmbH")
        r = client.post("/api/v1/invoices", json={
            "customer_id": kunde["id"], "invoice_date": "2026-10-01", "due_date": "2026-10-15",
            "lines": [{"description": "Erbsen-Schale", "quantity": 10, "unit": "STK",
                       "unit_price": "2.50", "tax_rate": "REDUZIERT"}],
        })
        assert r.status_code == 201, r.text
        _p4b_heute_festsetzen(monkeypatch, _p4b_date(2026, 10, 9))

        rechnung = _p4b_festschreiben(client, r.json()["id"])

        assert rechnung["invoice_number"] == "RE-2026-00001"
        assert (rechnung["invoice_date"], rechnung["due_date"]) == ("2026-10-09", "2026-10-23")


def _p4b_lieferscheine(client, bestellung):
    r = client.get(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes")
    assert r.status_code == 200, r.text
    return r.json()


def _p4b_monat(client, monat):
    r = client.get("/api/v1/invoices/monthly-proposals", params={"month": monat})
    assert r.status_code == 200, r.text
    return r.json()


class TestP4BLieferscheinBeimAusliefern:
    """G31/X07: Jede gelieferte Bestellung hat einen Lieferschein. Monats- und
    Sammellauf rechnen über Lieferscheine ab (Paket 3); ohne Lieferschein
    fehlte eine im Tagesplan ausgelieferte Bestellung still."""

    def test_ausliefern_legt_den_lieferschein_an(self, client):
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde)

        geliefert = _p4b_status(client, bestellung, "GELIEFERT")

        scheine = _p4b_lieferscheine(client, bestellung)
        assert len(scheine) == 1
        ls = scheine[0]
        assert ls["delivery_note_number"].startswith("LS-")
        assert ls["status"] == "ENTWURF"
        assert ls["notes"] is None
        assert ls["actual_delivery_date"] == geliefert["actual_delivery_date"]
        assert [(p["product_name"], _P4B_Decimal(str(p["quantity"])))
                for p in ls["packing_list"]["items"]] == [("Erbsen-Schale", _P4B_Decimal("10"))]

    def test_nachgetragener_liefertag(self, client):
        """Tagesplan eines vergangenen Tages: der Lieferschein trägt dessen Datum."""
        kunde = _p4b_kunde(client)
        tag = _p4b_date.today() - _p4b_timedelta(days=3)
        bestellung = _p4b_bestellung(client, kunde, liefertag=tag)

        _p4b_status(client, bestellung, "GELIEFERT", actual_delivery_date=tag.isoformat())

        assert [ls["actual_delivery_date"] for ls in _p4b_lieferscheine(client, bestellung)] == [tag.isoformat()]

    def test_vorhandener_lieferschein_bleibt_der_einzige(self, client):
        """Wächter: Packliste aus dem Tagesplan legte ihn schon an."""
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde)
        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes", json={})
        assert r.status_code == 201, r.text

        _p4b_status(client, bestellung, "GELIEFERT")

        assert [ls["id"] for ls in _p4b_lieferscheine(client, bestellung)] == [r.json()["id"]]

    def test_sammelaktion_legt_je_bestellung_einen_an(self, client):
        kunde = _p4b_kunde(client)
        erste, zweite = _p4b_bestellung(client, kunde), _p4b_bestellung(client, kunde)

        r = client.post("/api/v1/sales/orders/bulk-status",
                        json={"order_ids": [erste["id"], zweite["id"]], "status": "GELIEFERT"})

        assert r.status_code == 200, r.text
        assert [len(_p4b_lieferscheine(client, b)) for b in (erste, zweite)] == [1, 1]
        nummern = {_p4b_lieferscheine(client, b)[0]["delivery_note_number"] for b in (erste, zweite)}
        assert len(nummern) == 2

    def test_quittieren_legt_keinen_zweiten_an(self, client):
        """Wächter: Quittieren setzt die Bestellung auf Geliefert — über denselben Weg."""
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde)
        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes", json={})
        assert r.status_code == 201, r.text

        r = client.patch(f"/api/v1/sales/delivery-notes/{r.json()['id']}/mark-delivered",
                         json={"signed_by": "Küche"})

        assert r.status_code == 200, r.text
        assert [ls["status"] for ls in _p4b_lieferscheine(client, bestellung)] == ["GELIEFERT"]

    def test_monatslauf_nimmt_die_ausgelieferte_bestellung_auf(self, client):
        """Monatskunde, im Tagesplan „Ausgeliefert“, ohne Packliste. (Die
        Abo-Entwürfe von KD-10022 erreichen „Ausgeliefert“ erst mit
        Paket-4-Abschnitt A, G10; hier eine bestätigte Bestellung.)"""
        kunde = _p4b_kunde(client, "LfA Förderbank Bayern", invoice_mode="MONATLICH")
        bestellung = _p4b_bestellung(client, kunde, liefertag=_p4b_date(2026, 3, 2))
        _p4b_status(client, bestellung, "GELIEFERT", actual_delivery_date="2026-03-02")

        stand = _p4b_monat(client, "2026-03")
        assert [h["art"] for h in stand["hinweise"] if h["customer_id"] == kunde["id"]] == ["NICHT_QUITTIERT"]
        assert [(v["customer_id"], v["anzahl_lieferscheine"]) for v in stand["vorgeschlagen"]] == [(kunde["id"], 1)]

        r = client.post("/api/v1/invoices/monthly-proposals/run", params={"month": "2026-03"})

        assert r.status_code == 201, r.text
        assert [(a["customer_id"], a["art"]) for a in r.json()["angelegt"]] == [(kunde["id"], "WARE")]
        rechnung = client.get(f"/api/v1/invoices/{r.json()['angelegt'][0]['invoice_id']}").json()
        assert _P4B_Decimal(str(rechnung["subtotal"])) == _P4B_Decimal("25.00")

    def test_einzelkunde_erscheint_im_monatsdialog(self, client):
        """X07: Eine künftig ausgelieferte Bestellung eines Einzelkunden wird
        im Monatsdialog sichtbar (Hinweis EINZELABRECHNUNG mit Lieferschein).
        Der Altfall BE-20261008-0002 (GELIEFERT vor B, ohne Lieferschein)
        bleibt hier unsichtbar — ihn zeigt erst der Belegstatus (Abschnitt C)."""
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde, liefertag=_p4b_date(2026, 3, 4))
        _p4b_status(client, bestellung, "GELIEFERT", actual_delivery_date="2026-03-04")
        ls = _p4b_lieferscheine(client, bestellung)[0]

        hinweise = [h for h in _p4b_monat(client, "2026-03")["hinweise"] if h["customer_id"] == kunde["id"]]

        assert [(h["art"], h["belege"]) for h in hinweise] == [("EINZELABRECHNUNG", [ls["delivery_note_number"]])]

    def test_rechnung_aus_bestellung_belegt_den_lieferschein(self, client):
        """Kein zweiter Weg zur Doppelabrechnung: Der Lieferschein hängt an der
        Rechnung, der Sammellauf sieht die Bestellung nicht mehr."""
        from app.models.documents import DeliveryNote
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde)
        _p4b_status(client, bestellung, "GELIEFERT")

        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")

        assert r.status_code == 201, r.text
        ls_id = _p4b_uuid.UUID(_p4b_lieferscheine(client, bestellung)[0]["id"])
        with _P4B_Session() as db:
            assert str(db.get(DeliveryNote, ls_id).invoice_id) == r.json()["id"]
        heute = _p4b_date.today()
        r = client.post("/api/v1/invoices/batch-run/preview", json={
            "period_from": (heute - _p4b_timedelta(days=31)).isoformat(), "period_to": heute.isoformat()})
        assert r.json()["kunden"] == []
