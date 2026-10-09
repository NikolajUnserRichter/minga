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


_P4B_SAMMELMENGE = (
    "Die Menge stammt aus den Lieferscheinen dieser Sammel- bzw. Monatsrechnung. "
    "Entwurf verwerfen, Menge in der Bestellung korrigieren, Lauf neu starten."
)


def _p4b_monatsentwurf(client, kunde):
    """Monatsrechnung März 2026 aus zwei Lieferungen à 10 × 2,50 €: eine
    Sammelposition mit zwei Quellen (invoice_line_sources), wie sie Gernot
    ab 01.11. für seine Monatskunden prüft. Die Lieferscheine legt das
    Ausliefern an (B.3)."""
    bestellungen = []
    for tag in (2, 9):
        bestellung = _p4b_bestellung(client, kunde, liefertag=_p4b_date(2026, 3, tag))
        _p4b_status(client, bestellung, "GELIEFERT", actual_delivery_date=f"2026-03-{tag:02d}")
        bestellungen.append(bestellung)
    r = client.post("/api/v1/invoices/monthly-proposals/run", params={"month": "2026-03"})
    assert r.status_code == 201, r.text
    rechnung = client.get(f"/api/v1/invoices/{r.json()['angelegt'][0]['invoice_id']}").json()
    return rechnung, bestellungen


def _p4b_netto_und_anlage(client, rechnung):
    """Nettosumme der Rechnung und Netto je Lieferschein, wie in der
    PDF-Anlage „Enthaltene Lieferscheine“ (netto_je_lieferschein)."""
    netto = client.get(f"/api/v1/invoices/{rechnung['id']}").json()["subtotal"]
    r = client.get(f"/api/v1/invoices/{rechnung['id']}/delivery-notes")
    assert r.status_code == 200, r.text
    return (_P4B_Decimal(str(netto)),
            [_P4B_Decimal(str(ls["betrag_netto"])) for ls in r.json()])


class TestP4BSammelpositionMenge:
    """G21 mit Sammel- und Monatsrechnung (B-E6): Die Menge einer
    Sammelposition steht je Lieferschein in invoice_line_sources, die Anlage
    „Enthaltene Lieferscheine“ rechnet daraus. Eine Mengenänderung nur an
    der Position ließ Rechnung (37,50 €) und Anlage (25,00 + 25,00 €)
    auseinanderlaufen."""

    def test_menge_einer_sammelposition_abgelehnt(self, client):
        kunde = _p4b_kunde(client, "LfA Förderbank Bayern", invoice_mode="MONATLICH")
        rechnung, _ = _p4b_monatsentwurf(client, kunde)
        zeile = rechnung["lines"][0]

        r = client.patch(f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}", json={"quantity": 15})

        assert r.status_code == 409, r.text
        assert r.json()["detail"] == _P4B_SAMMELMENGE
        assert _p4b_netto_und_anlage(client, rechnung) == (
            _P4B_Decimal("50.00"), [_P4B_Decimal("25.00"), _P4B_Decimal("25.00")])

    def test_preis_einer_sammelposition_aenderbar(self, client):
        """Die Anlage rechnet mit dem Einzelpreis der Position und bleibt
        stimmig. Eine unverändert mitgeschickte Menge ist keine Änderung."""
        kunde = _p4b_kunde(client, "LfA Förderbank Bayern", invoice_mode="MONATLICH")
        rechnung, _ = _p4b_monatsentwurf(client, kunde)
        zeile = rechnung["lines"][0]

        r = client.patch(f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}",
                         json={"quantity": 20, "unit_price": "3.00"})

        assert r.status_code == 200, r.text
        assert _p4b_netto_und_anlage(client, rechnung) == (
            _P4B_Decimal("60.00"), [_P4B_Decimal("30.00"), _P4B_Decimal("30.00")])

    def test_menge_bei_rechnung_aus_bestellung_aenderbar(self, client):
        """Wächter: Rechnung aus Bestellung hat keine invoice_line_sources;
        ihre Anlage rechnet aus den Positionen selbst."""
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde)
        _p4b_status(client, bestellung, "GELIEFERT")
        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")
        assert r.status_code == 201, r.text
        rechnung = client.get(f"/api/v1/invoices/{r.json()['id']}").json()

        r = client.patch(f"/api/v1/invoices/{rechnung['id']}/lines/{rechnung['lines'][0]['id']}",
                         json={"quantity": 8})

        assert r.status_code == 200, r.text
        assert _p4b_netto_und_anlage(client, rechnung) == (_P4B_Decimal("20.00"), [_P4B_Decimal("20.00")])

    def test_korrekturweg_aus_der_meldung(self, client):
        """Wächter: Der Weg aus der Meldung führt zum Ziel — Entwurf
        verwerfen, Menge in der Bestellung korrigieren, Lauf neu starten."""
        kunde = _p4b_kunde(client, "LfA Förderbank Bayern", invoice_mode="MONATLICH")
        rechnung, (erste, _) = _p4b_monatsentwurf(client, kunde)

        r = client.delete(f"/api/v1/invoices/{rechnung['id']}")
        assert r.status_code == 204, r.text
        zeile_id = client.get(f"/api/v1/sales/orders/{erste['id']}").json()["lines"][0]["id"]
        r = client.patch(f"/api/v1/sales/orders/{erste['id']}/lines/{zeile_id}", json={"quantity": 5})
        assert r.status_code == 200, r.text
        r = client.post("/api/v1/invoices/monthly-proposals/run", params={"month": "2026-03"})
        assert r.status_code == 201, r.text
        neu = client.get(f"/api/v1/invoices/{r.json()['angelegt'][0]['invoice_id']}").json()

        assert _p4b_netto_und_anlage(client, neu) == (
            _P4B_Decimal("37.50"), [_P4B_Decimal("12.50"), _P4B_Decimal("25.00")])


# ---------------------------------------- Abschnitt C: Dateiname mit Kundenname (C.1)
import pytest  # noqa: E402


class TestP4CDateiname:
    """Gernot 08.10. (B7): LS-20261008-001_Fruchthof-Nagel-GmbH.pdf — Nummer,
    Unterstrich, bereinigter Kundenname. Die Regel, ohne Datenbank."""

    def test_nummer_und_kunde(self):
        from app.services.beleg_dateiname import beleg_dateiname
        assert beleg_dateiname("LS-20261008-0001", kunde="Fruchthof Nagel GmbH") == (
            "LS-20261008-0001_Fruchthof-Nagel-GmbH.pdf")
        assert beleg_dateiname("RE-2026-00008", kunde="Großer Kern GmbH") == "RE-2026-00008_Grosser-Kern-GmbH.pdf"

    @pytest.mark.parametrize("name, teil", [
        # Kundennamen aus Produktion (minga, 09.10.2026)
        pytest.param("Ökoring Handels GmbH", "Oekoring-Handels-GmbH", id="umlaut-vorn"),
        pytest.param("Ferdinand Bierbichler GmbH & Co. KG", "Ferdinand-Bierbichler-GmbH-Co-KG", id="gmbh-co-kg"),
        pytest.param("SIMPE'L regional&unverpackt", "SIMPEL-regional-unverpackt", id="apostroph-und"),
        pytest.param("BODAN Großhandel für Naturkost GmbH", "BODAN-Grosshandel-fuer-Naturkost-GmbH", id="eszett"),
        pytest.param("Münchner Tafel e. V.", "Muenchner-Tafel-e-V", id="e-v"),
        pytest.param("Engelsberger Hofladen (R. u. D. Reichlmayr GbR)",
                     "Engelsberger-Hofladen-R-u-D-Reichlmayr-GbR", id="klammern"),
        pytest.param("Restaurant Eschenrieder Hof/Golfclub Sohyl Sediq",
                     "Restaurant-Eschenrieder-Hof-Golfclub-Sohyl-Sediq", id="schraegstrich"),
        pytest.param("Cafe Lido Gastronomiebetriebs GmbH & Co.KG", "Cafe-Lido-Gastronomiebetriebs-GmbH-Co-KG",
                     id="co-kg-ohne-leerzeichen"),
        # Akzente, zerlegte Umlaute (macOS), Leerraum, Anführungszeichen
        pytest.param("Café Crème", "Cafe-Creme", id="akzente"),
        pytest.param("Mu\u0308nchner Gru\u0308nkern", "Muenchner-Gruenkern", id="nfd"),
        pytest.param("  Hofladen\t\"Süd\"\n ", "Hofladen-Sued", id="leerraum"),
        pytest.param("ÄÖÜ äöü ß", "AeOeUe-aeoeue-ss", id="alle-umlaute"),
        # Akut als Apostroph (NFKD machte daraus ein Leerzeichen) und Buchstaben,
        # die NFKD nicht zerlegt (sie fielen sonst weg)
        pytest.param("SIMPE´L Hofladen", "SIMPEL-Hofladen", id="akut-als-apostroph"),
        pytest.param("Søren Ærø Œuvre", "Soeren-Aeroe-Oeuvre", id="nordisch"),
        pytest.param("Łódź Đurić", "Lodz-Duric", id="polnisch-kroatisch"),
    ])
    def test_bereinigung(self, name, teil):
        from app.services.beleg_dateiname import kundenteil
        assert kundenteil(name) == teil

    def test_laenge_an_der_wortgrenze(self):
        from app.services.beleg_dateiname import KUNDE_MAX_ZEICHEN, kundenteil
        assert KUNDE_MAX_ZEICHEN == 50
        lang = "Bayerische Landesanstalt für Landwirtschaft Institut für Ökologischen Landbau"
        assert kundenteil(lang) == "Bayerische-Landesanstalt-fuer-Landwirtschaft"
        # Wort endet genau an der Grenze: bleibt ganz
        assert kundenteil("A" * 50 + " GmbH") == "A" * 50
        # ein einziges langes Wort: harter Schnitt
        assert kundenteil("X" * 70) == "X" * 50
        # der Wortschnitt ließe weniger als die Hälfte übrig ("A"): harter Schnitt
        assert kundenteil("A " + "B" * 60) == "A-" + "B" * 48

    @pytest.mark.parametrize("kunde", [None, "", "   ", "!!!", "„“"], ids=["none", "leer", "leerzeichen", "zeichen", "anfuehrung"])
    def test_ohne_brauchbaren_namen_wie_bisher(self, kunde):
        from app.services.beleg_dateiname import beleg_dateiname
        assert beleg_dateiname("RE-2026-00002", kunde=kunde) == "RE-2026-00002.pdf"

    def test_entwurf_mit_kunde(self):
        from app.services.beleg_dateiname import beleg_dateiname
        assert beleg_dateiname("ENTWURF-AB12CD34EF56", kunde="Ökoring Handels GmbH") == (
            "Entwurf-AB12CD34EF56_Oekoring-Handels-GmbH.pdf")
        assert beleg_dateiname("RE-2026-00003", entwurf=True, kunde="Ökoring Handels GmbH") == (
            "Entwurf-RE-2026-00003_Oekoring-Handels-GmbH.pdf")

    def test_kopf_ascii_filename_gleich_filename_stern(self):
        """Nur A–Z, a–z, 0–9, '-', '_', '.': filename= und filename* tragen
        denselben Namen, und der Belegordner (O, sichererName) ändert nichts."""
        import re
        from app.services.beleg_dateiname import beleg_dateiname, content_disposition
        name = beleg_dateiname("AB-20261009-0001", kunde="Hamberger Großmarkt GmbH & Co. KG")
        assert name == "AB-20261009-0001_Hamberger-Grossmarkt-GmbH-Co-KG.pdf"
        assert re.fullmatch(r"[A-Za-z0-9._-]+", name)
        assert content_disposition(name) == f"attachment; filename=\"{name}\"; filename*=UTF-8''{name}"


# ---------------------------------------- Abschnitt C: Download und Mailanhang (C.2)

def _p4c_kunde(client, name="Fruchthof Nagel GmbH", **extra):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "HANDEL", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _p4c_bestellung(client, kunde, liefertag=None) -> str:
    from datetime import date
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"],
        "requested_delivery_date": (liefertag or date.today()).isoformat(),
        "lines": [{"product_name": "Erbsen-Schale", "quantity": 10, "unit": "STK",
                   "unit_price": 2.50, "tax_rate": "REDUZIERT"}],
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _p4c_rechnung(client, order_id, finalisieren=True) -> dict:
    r = client.post(f"/api/v1/invoices/from-order/{order_id}")
    assert r.status_code == 201, r.text
    if finalisieren:
        f = client.post(f"/api/v1/invoices/{r.json()['id']}/finalize")
        assert f.status_code == 200, f.text
        return f.json()
    return r.json()


def _p4c_kopf(name: str) -> str:
    return f"attachment; filename=\"{name}\"; filename*=UTF-8''{name}"


@pytest.fixture
def _p4c_mails(monkeypatch):
    """Beleg-Mails abfangen (belegversand.send_email), SMTP über die Umgebung 'konfiguriert'."""
    from app.services.email_service import VersandErgebnis
    monkeypatch.setenv("SMTP_HOST", "smtp.farm.example")
    monkeypatch.setenv("SMTP_USER", "versand@farm.example")
    gesendet = []

    def senden(**kw):
        gesendet.append(kw)
        return VersandErgebnis(message_id=f"<p4c{len(gesendet)}@test.example>")

    monkeypatch.setattr("app.services.belegversand.send_email", senden)
    return gesendet


class TestP4CDateinameDownloads:
    """Download (Content-Disposition) mit Kundennamen: AB, LS, PL, Rechnung, Sammelrechnung."""

    def test_ab_lieferschein_packliste(self, client):
        kunde = _p4c_kunde(client, "Ökoring Handels GmbH")
        order_id = _p4c_bestellung(client, kunde)
        ab = client.post(f"/api/v1/sales/orders/{order_id}/confirmations", json={}).json()
        ls = client.post(f"/api/v1/sales/orders/{order_id}/delivery-notes", json={}).json()

        r_ab = client.get(f"/api/v1/sales/confirmations/{ab['id']}/pdf")
        r_ls = client.get(f"/api/v1/sales/delivery-notes/{ls['id']}/pdf")
        r_pl = client.get(f"/api/v1/sales/delivery-notes/{ls['id']}/packing-list/pdf")

        assert r_ab.headers["content-disposition"] == _p4c_kopf(
            f"{ab['confirmation_number']}_Oekoring-Handels-GmbH.pdf")
        assert r_ls.headers["content-disposition"] == _p4c_kopf(
            f"{ls['delivery_note_number']}_Oekoring-Handels-GmbH.pdf")
        assert r_pl.headers["content-disposition"] == _p4c_kopf(
            f"{ls['packing_list']['packing_list_number']}_Oekoring-Handels-GmbH.pdf")

    def test_rechnung_nimmt_den_namen_vom_beleg(self, client):
        """Ausgestellt: der beim Festschreiben eingefrorene Empfängername (wie im
        PDF, GoBD) — eine spätere Umbenennung des Kunden ändert den Namen nicht.
        Entwurf: der aktuelle Kundenname."""
        kunde = _p4c_kunde(client)
        rechnung = _p4c_rechnung(client, _p4c_bestellung(client, kunde))
        entwurf = _p4c_rechnung(client, _p4c_bestellung(client, kunde), finalisieren=False)
        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"name": "Fruchthof Nagel KG"})
        assert r.status_code == 200, r.text

        r_re = client.get(f"/api/v1/invoices/{rechnung['id']}/pdf")
        r_ent = client.get(f"/api/v1/invoices/{entwurf['id']}/pdf")

        assert r_re.headers["content-disposition"] == _p4c_kopf(
            f"{rechnung['invoice_number']}_Fruchthof-Nagel-GmbH.pdf")
        platzhalter = entwurf["invoice_number"].removeprefix("ENTWURF-")
        assert r_ent.headers["content-disposition"] == _p4c_kopf(
            f"Entwurf-{platzhalter}_Fruchthof-Nagel-KG.pdf")

    def test_sammelrechnung(self, client):
        from datetime import date
        kunde = _p4c_kunde(client, "Hamberger Großmarkt GmbH")
        for _ in range(2):
            order_id = _p4c_bestellung(client, kunde)
            assert client.post(f"/api/v1/sales/orders/{order_id}/delivery-notes", json={}).status_code == 201
        heute = date.today().isoformat()
        r = client.post("/api/v1/invoices/batch-run/commit", json={
            "period_from": heute, "period_to": heute, "customer_ids": [kunde["id"]]})
        assert r.status_code == 201, r.text
        sammel = r.json()["rechnungen"][0]
        f = client.post(f"/api/v1/invoices/{sammel['id']}/finalize")
        assert f.status_code == 200, f.text

        r_pdf = client.get(f"/api/v1/invoices/{sammel['id']}/pdf")

        assert r_pdf.headers["content-disposition"] == _p4c_kopf(
            f"{f.json()['invoice_number']}_Hamberger-Grossmarkt-GmbH.pdf")


class TestP4CDateinameMail:
    """Mailanhang und Versandprotokoll heißen wie der Download."""

    def test_rechnung_mailen(self, client, _p4c_mails):
        kunde = _p4c_kunde(client, "Ökoring Handels GmbH")
        rechnung = _p4c_rechnung(client, _p4c_bestellung(client, kunde))

        r = client.post(f"/api/v1/invoices/{rechnung['id']}/send", json={"to": ["rechnung@oekoring.example"]})

        assert r.status_code == 200, r.text
        name = f"{rechnung['invoice_number']}_Oekoring-Handels-GmbH.pdf"
        assert _p4c_mails[0]["attachment_filename"] == name
        assert r.json()["attachment_filename"] == name

    def test_entwurf_mailen_heisst_wie_die_ausgestellte_rechnung(self, client, _p4c_mails):
        kunde = _p4c_kunde(client, "Ökoring Handels GmbH")
        entwurf = _p4c_rechnung(client, _p4c_bestellung(client, kunde), finalisieren=False)

        r = client.post(f"/api/v1/invoices/{entwurf['id']}/send", json={"to": ["rechnung@oekoring.example"]})

        assert r.status_code == 200, r.text
        assert r.json()["attachment_filename"] == f"{r.json()['document_number']}_Oekoring-Handels-GmbH.pdf"

    def test_ab_und_lieferschein_mailen_und_markieren(self, client, _p4c_mails):
        kunde = _p4c_kunde(client)
        order_id = _p4c_bestellung(client, kunde)
        ab = client.post(f"/api/v1/sales/orders/{order_id}/confirmations", json={}).json()
        ls = client.post(f"/api/v1/sales/orders/{order_id}/delivery-notes", json={}).json()

        r_ab = client.patch(f"/api/v1/sales/confirmations/{ab['id']}/send", json={"to": ["einkauf@fruchthof.example"]})
        r_ls = client.post(f"/api/v1/sales/delivery-notes/{ls['id']}/send", json={})  # ohne Mail: nur markiert

        assert r_ab.status_code == 200, r_ab.text
        assert r_ls.status_code == 200, r_ls.text
        assert _p4c_mails[0]["attachment_filename"] == f"{ab['confirmation_number']}_Fruchthof-Nagel-GmbH.pdf"
        assert r_ab.json()["dispatches"][0]["attachment_filename"] == (
            f"{ab['confirmation_number']}_Fruchthof-Nagel-GmbH.pdf")
        assert r_ls.json()["dispatches"][0]["status"] == "NUR_MARKIERT"
        assert r_ls.json()["dispatches"][0]["attachment_filename"] == (
            f"{ls['delivery_note_number']}_Fruchthof-Nagel-GmbH.pdf")

    def test_erneuter_versand_nach_der_umstellung_ohne_409(self, client, _p4c_mails):
        """Der Versandnachweis vergleicht die Prüfsumme des PDF-Inhalts, nicht
        den Dateinamen: Ein Beleg, der vor dem Deploy als „AB-….pdf“ hinausging,
        geht danach erneut hinaus — unter dem neuen Namen, mit derselben Prüfsumme."""
        from app.models.documents import DocumentDispatch
        from tests.conftest import TestingSessionLocal
        kunde = _p4c_kunde(client)
        order_id = _p4c_bestellung(client, kunde)
        ab = client.post(f"/api/v1/sales/orders/{order_id}/confirmations", json={}).json()
        ls = client.post(f"/api/v1/sales/orders/{order_id}/delivery-notes", json={}).json()
        assert client.patch(f"/api/v1/sales/confirmations/{ab['id']}/send",
                            json={"to": ["einkauf@fruchthof.example"]}).status_code == 200
        assert client.post(f"/api/v1/sales/delivery-notes/{ls['id']}/send",
                           json={"to": ["einkauf@fruchthof.example"]}).status_code == 200
        with TestingSessionLocal() as db:  # Stand vor dem Deploy: Name nur die Nummer
            for zeile in db.query(DocumentDispatch).all():
                zeile.attachment_filename = f"{zeile.document_number}.pdf"
            db.commit()

        r_ab = client.patch(f"/api/v1/sales/confirmations/{ab['id']}/send", json={"to": ["chef@fruchthof.example"]})
        r_ls = client.post(f"/api/v1/sales/delivery-notes/{ls['id']}/send", json={"to": ["chef@fruchthof.example"]})

        assert r_ab.status_code == 200, r_ab.text
        assert r_ls.status_code == 200, r_ls.text
        for antwort, nummer in ((r_ab, ab["confirmation_number"]), (r_ls, ls["delivery_note_number"])):
            namen = sorted(d["attachment_filename"] for d in antwort.json()["dispatches"])
            assert namen == sorted([f"{nummer}.pdf", f"{nummer}_Fruchthof-Nagel-GmbH.pdf"])
            assert len({d["attachment_sha256"] for d in antwort.json()["dispatches"]}) == 1
        assert len(_p4c_mails) == 4


# ---------------------------------------- Abschnitt C: Belegstatus (C.3)
_P4C_HEUTE = "2026-10-09"


def _p4c_heute(monkeypatch, tag=_P4C_HEUTE):
    """Stichtag des Belegstatus festlegen (der Endpunkt rechnet in Berlin)."""
    from datetime import date
    monkeypatch.setattr("app.api.v1.belegstatus.heute_berlin", lambda: date.fromisoformat(tag))


def _p4c_auftrag(client, kunde, liefertag, status="GELIEFERT", lieferschein=True, ls_status=None) -> str:
    """Bestellung mit Liefertag und Status (direkt gesetzt), auf Wunsch mit Lieferschein."""
    import uuid
    from datetime import date
    from app.models.documents import DeliveryNote
    from app.models.enums import DeliveryNoteStatus, OrderStatus
    from app.models.order import Order
    from tests.conftest import TestingSessionLocal
    order_id = _p4c_bestellung(client, kunde, date.fromisoformat(liefertag))
    if lieferschein:
        r = client.post(f"/api/v1/sales/orders/{order_id}/delivery-notes", json={})
        assert r.status_code == 201, r.text
    with TestingSessionLocal() as db:
        db.get(Order, uuid.UUID(order_id)).status = OrderStatus(status)
        if ls_status:
            for ls in db.query(DeliveryNote).filter(DeliveryNote.order_id == uuid.UUID(order_id)):
                ls.status = DeliveryNoteStatus(ls_status)
        db.commit()
    return order_id


def _p4c_status(client, **params) -> dict:
    r = client.get("/api/v1/belegstatus", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _p4c_zeile(liste, order_id) -> dict:
    treffer = [z for z in liste["items"] if z["order_id"] == order_id]
    assert len(treffer) == 1, liste
    return treffer[0]


class TestP4CBelegstatus:
    """Gernot 08.10. (B2): je Bestellung Lieferschein ✔/✘, Rechnung ✔/✘,
    versendet ✔/✘, bezahlt; Filter Zeitraum, Kunde, „unvollständig“
    (geliefert, aber ohne Rechnung bzw. Rechnung nicht versendet)."""

    def test_einzelkunde_geliefert_ohne_rechnung(self, client, monkeypatch):
        """X07: gelieferte Bestellungen von Einzelkunden ohne Rechnung — mit
        Lieferschein und ohne (Abo, BE-20261008-0002)."""
        _p4c_heute(monkeypatch)
        kunde = _p4c_kunde(client, "Naturkostinsel GmbH")
        mit_ls = _p4c_auftrag(client, kunde, "2026-10-08")
        ohne_ls = _p4c_auftrag(client, kunde, "2026-10-08", lieferschein=False)

        liste = _p4c_status(client, von="2026-10-01")

        assert (liste["total"], liste["unvollstaendig"], liste["heute"]) == (2, 2, _P4C_HEUTE)
        a, b = _p4c_zeile(liste, mit_ls), _p4c_zeile(liste, ohne_ls)
        assert [len(a["lieferscheine"]), len(b["lieferscheine"])] == [1, 0]
        assert a["lieferscheine"][0]["status"] == "ENTWURF"
        for z in (a, b):
            assert (z["customer_name"], z["abrechnung"], z["liefertag"]) == ("Naturkostinsel GmbH", "EINZELN", "2026-10-08")
            assert (z["geliefert"], z["rechnung"], z["extern_abgerechnet"]) == (True, None, False)
            assert (z["luecken"], z["unvollstaendig"], z["rechnung_faellig_ab"]) == (["OHNE_RECHNUNG"], True, "2026-10-08")

    def test_entwurf_nicht_versendet_versendet_bezahlt(self, client, monkeypatch, _p4c_mails):
        _p4c_heute(monkeypatch)
        kunde = _p4c_kunde(client)
        auftraege = [_p4c_auftrag(client, kunde, "2026-10-08") for _ in range(4)]
        entwurf = _p4c_rechnung(client, auftraege[0], finalisieren=False)
        offen = _p4c_rechnung(client, auftraege[1])
        versendet = _p4c_rechnung(client, auftraege[2])
        bezahlt = _p4c_rechnung(client, auftraege[3])
        for rechnung in (versendet, bezahlt):
            r = client.post(f"/api/v1/invoices/{rechnung['id']}/send", json={"to": ["rechnung@fruchthof.example"]})
            assert r.status_code == 200, r.text
        r = client.post(f"/api/v1/invoices/{bezahlt['id']}/payments",
                        json={"payment_date": _P4C_HEUTE, "amount": str(bezahlt["total"])})
        assert r.status_code in (200, 201), r.text

        liste = _p4c_status(client)

        z = [_p4c_zeile(liste, o) for o in auftraege]
        assert [x["luecken"] for x in z] == [["RECHNUNG_ENTWURF"], ["NICHT_VERSENDET"], [], []]
        assert [x["rechnung"]["id"] for x in z] == [entwurf["id"], offen["id"], versendet["id"], bezahlt["id"]]
        assert [x["rechnung"]["nummer"] for x in z[1:]] == [
            offen["invoice_number"], versendet["invoice_number"], bezahlt["invoice_number"]]
        assert z[0]["rechnung"]["nummer"].startswith("ENTWURF-")
        assert [x["rechnung"]["status"] for x in z] == ["ENTWURF", "OFFEN", "OFFEN", "BEZAHLT"]
        assert [x["rechnung"]["versendet_am"] is not None for x in z] == [False, False, True, True]
        assert [x["rechnung"]["bezahlt"] for x in z] == [False, False, False, True]
        assert [x["rechnung"]["sammelrechnung"] for x in z] == [False] * 4
        assert liste["unvollstaendig"] == 2

    def test_eintrag_im_versandprotokoll_zaehlt_als_versendet(self, client, monkeypatch):
        """Ein Eintrag im Versandprotokoll (auch „ohne Mail markiert“) zählt
        wie sent_at — sent_at setzt nur ein Mailversand (Paket 3, Q2)."""
        import uuid
        from datetime import datetime
        from app.models.documents import DocumentDispatch
        from app.models.enums import DispatchDocType, DispatchStatus
        from tests.conftest import TestingSessionLocal
        _p4c_heute(monkeypatch)
        kunde = _p4c_kunde(client)
        order_id = _p4c_auftrag(client, kunde, "2026-10-08")
        rechnung = _p4c_rechnung(client, order_id)
        with TestingSessionLocal() as db:
            db.add(DocumentDispatch(
                doc_type=DispatchDocType.RE, document_number=rechnung["invoice_number"],
                invoice_id=uuid.UUID(rechnung["id"]), order_id=uuid.UUID(order_id),
                status=DispatchStatus.NUR_MARKIERT, to_addrs=[], cc_addrs=[],
                sent_at=datetime(2026, 10, 8, 15, 0)))
            db.commit()

        z = _p4c_zeile(_p4c_status(client), order_id)

        assert (z["rechnung"]["versendet_am"], z["luecken"]) == ("2026-10-08T15:00:00", [])

    def test_festgeschriebene_rechnung_geht_dem_entwurf_vor(self, client, monkeypatch):
        """Zwei Rechnungen zu einer Bestellung (z. B. ein vergessener Entwurf):
        angezeigt wird die festgeschriebene."""
        import uuid
        from app.models.invoice import Invoice
        from tests.conftest import TestingSessionLocal
        _p4c_heute(monkeypatch)
        kunde = _p4c_kunde(client)
        order_id = _p4c_auftrag(client, kunde, "2026-10-08")
        fest = _p4c_rechnung(client, order_id)
        entwurf = _p4c_rechnung(client, _p4c_auftrag(client, kunde, "2026-10-08"), finalisieren=False)
        with TestingSessionLocal() as db:
            db.get(Invoice, uuid.UUID(entwurf["id"])).order_id = uuid.UUID(order_id)
            db.commit()

        z = _p4c_zeile(_p4c_status(client), order_id)

        assert (z["rechnung"]["id"], z["luecken"]) == (fest["id"], ["NICHT_VERSENDET"])

    def test_monatskunde_erst_ab_dem_folgemonat(self, client, monkeypatch):
        """Monatskunden rechnet der Monatslauf am 1. des Folgemonats ab —
        vorher ist die fehlende Rechnung keine Lücke."""
        kunde = _p4c_kunde(client, "Ökoring Handels GmbH", invoice_mode="MONATLICH")
        order_id = _p4c_auftrag(client, kunde, "2026-10-08")

        _p4c_heute(monkeypatch, "2026-10-31")
        vorher = _p4c_zeile(_p4c_status(client), order_id)
        _p4c_heute(monkeypatch, "2026-11-01")
        nachher = _p4c_zeile(_p4c_status(client), order_id)

        assert (vorher["abrechnung"], vorher["rechnung_faellig_ab"]) == ("MONATLICH", "2026-11-01")
        assert (vorher["luecken"], vorher["unvollstaendig"]) == ([], False)
        assert (nachher["luecken"], nachher["unvollstaendig"]) == (["OHNE_RECHNUNG"], True)

    def test_sammelrechnung_ueber_den_lieferschein(self, client, monkeypatch):
        _p4c_heute(monkeypatch)
        kunde = _p4c_kunde(client, "Hamberger Großmarkt GmbH")
        auftraege = [_p4c_auftrag(client, kunde, "2026-10-08", ls_status="GELIEFERT") for _ in range(2)]
        r = client.post("/api/v1/invoices/batch-run/commit", json={
            "period_from": "2026-10-01", "period_to": "2026-10-09", "customer_ids": [kunde["id"]]})
        assert r.status_code == 201, r.text
        sammel = r.json()["rechnungen"][0]
        assert client.post(f"/api/v1/invoices/{sammel['id']}/finalize").status_code == 200

        liste = _p4c_status(client)

        for order_id in auftraege:
            z = _p4c_zeile(liste, order_id)
            assert (z["rechnung"]["id"], z["rechnung"]["sammelrechnung"]) == (sammel["id"], True)
            assert z["lieferscheine"][0]["status"] == "GELIEFERT"
            assert z["luecken"] == ["NICHT_VERSENDET"]

    def test_fakturiert_ohne_rechnung_ist_extern_abgerechnet(self, client, monkeypatch):
        """Altbestand (574 Bestellungen in Produktion): FAKTURIERT, über DATEV
        abgerechnet, ohne Rechnung im System — keine Lücke. Wurde die
        NovaERP-Rechnung storniert und nicht neu ausgestellt, fehlt sie: Der
        Storno setzt FAKTURIERT nicht zurück, „extern“ wäre dann falsch.
        Die Rechnungen entstehen vor der Kennzeichnung FAKTURIERT — danach
        lehnt der Server neue Rechnungen ab (Paket 4, B-E1)."""
        import uuid
        from app.models.enums import OrderStatus
        from app.models.order import Order
        from tests.conftest import TestingSessionLocal
        _p4c_heute(monkeypatch)
        kunde = _p4c_kunde(client)
        extern = _p4c_auftrag(client, kunde, "2026-08-14", status="FAKTURIERT", lieferschein=False)
        im_system = _p4c_auftrag(client, kunde, "2026-10-08")
        _p4c_rechnung(client, im_system)
        storniert = _p4c_auftrag(client, kunde, "2026-10-08")
        r = client.post(f"/api/v1/invoices/{_p4c_rechnung(client, storniert)['id']}/cancel",
                        json={"reason": "Preisfehler", "reason_code": "PREISFEHLER"})
        assert r.status_code == 200, r.text
        with TestingSessionLocal() as db:  # wie der Status-Endpunkt: GELIEFERT → FAKTURIERT
            for order_id in (im_system, storniert):
                db.get(Order, uuid.UUID(order_id)).status = OrderStatus.FAKTURIERT
            db.commit()

        liste = _p4c_status(client)

        e, i, s = _p4c_zeile(liste, extern), _p4c_zeile(liste, im_system), _p4c_zeile(liste, storniert)
        assert (e["extern_abgerechnet"], e["rechnung"], e["luecken"], e["geliefert"]) == (True, None, [], True)
        assert (i["extern_abgerechnet"], i["luecken"]) == (False, ["NICHT_VERSENDET"])
        assert (s["extern_abgerechnet"], s["rechnung"], s["luecken"]) == (False, None, ["OHNE_RECHNUNG"])

    def test_wann_eine_bestellung_als_geliefert_gilt(self, client, monkeypatch):
        """GELIEFERT/FAKTURIERT, ein quittierter Lieferschein, oder BESTAETIGT/
        IN_PRODUKTION mit Liefertag vor heute (Spec A1: gelieferte Bestellungen
        bleiben oft auf BESTAETIGT). ENTWURF ohne Quittung nie; storniert fehlt."""
        _p4c_heute(monkeypatch)
        kunde = _p4c_kunde(client)
        faelle = {
            "bestaetigt_gestern": (_p4c_auftrag(client, kunde, "2026-10-08", status="BESTAETIGT"), True),
            "bestaetigt_heute": (_p4c_auftrag(client, kunde, "2026-10-09", status="BESTAETIGT"), False),
            "in_produktion_vorgestern": (_p4c_auftrag(client, kunde, "2026-10-07", status="IN_PRODUKTION"), True),
            "entwurf_alt": (_p4c_auftrag(client, kunde, "2026-09-14", status="ENTWURF", lieferschein=False), False),
            "entwurf_quittiert": (_p4c_auftrag(client, kunde, "2026-10-09", status="ENTWURF", ls_status="GELIEFERT"), True),
            "geliefert_morgen": (_p4c_auftrag(client, kunde, "2026-10-10", status="GELIEFERT"), True),
        }
        storniert = _p4c_auftrag(client, kunde, "2026-10-08", status="STORNIERT")

        liste = _p4c_status(client)

        ist = {name: _p4c_zeile(liste, oid)["geliefert"] for name, (oid, _) in faelle.items()}
        assert ist == {name: soll for name, (_, soll) in faelle.items()}
        assert storniert not in [z["order_id"] for z in liste["items"]]
        luecken = {name: _p4c_zeile(liste, oid)["luecken"] for name, (oid, _) in faelle.items()}
        assert luecken == {
            "bestaetigt_gestern": ["OHNE_RECHNUNG"], "bestaetigt_heute": [],
            "in_produktion_vorgestern": ["OHNE_RECHNUNG"], "entwurf_alt": [],
            "entwurf_quittiert": ["OHNE_RECHNUNG"],
            "geliefert_morgen": [],  # fällig erst ab dem Liefertag
        }

    def test_filter_reihenfolge_und_seiten(self, client, monkeypatch):
        _p4c_heute(monkeypatch)
        nagel = _p4c_kunde(client)
        kern = _p4c_kunde(client, "Großer Kern GmbH")
        n1 = _p4c_auftrag(client, nagel, "2026-10-08")                          # unvollständig
        n2 = _p4c_auftrag(client, nagel, "2026-10-12", status="BESTAETIGT")     # Zukunft
        k1 = _p4c_auftrag(client, kern, "2026-09-30")                           # unvollständig
        k2 = _p4c_auftrag(client, kern, "2026-10-05")                           # unvollständig

        alle = _p4c_status(client)
        assert [z["order_id"] for z in alle["items"]] == [n2, n1, k2, k1]   # Liefertag absteigend
        assert (alle["total"], alle["unvollstaendig"]) == (4, 3)

        oktober = _p4c_status(client, von="2026-10-01", bis="2026-10-09")
        assert [z["order_id"] for z in oktober["items"]] == [n1, k2]
        assert _p4c_status(client, kunde_id=kern["id"])["total"] == 2

        nur = _p4c_status(client, nur_unvollstaendig="true")
        assert [z["order_id"] for z in nur["items"]] == [n1, k2, k1]
        assert (nur["total"], nur["unvollstaendig"]) == (3, 3)

        seite2 = _p4c_status(client, nur_unvollstaendig="true", page=2, page_size=2)
        assert [z["order_id"] for z in seite2["items"]] == [k1]
        assert (seite2["total"], seite2["unvollstaendig"]) == (3, 3)

    def test_von_nach_bis_wird_abgelehnt(self, client):
        r = client.get("/api/v1/belegstatus", params={"von": "2026-10-09", "bis": "2026-10-01"})
        assert r.status_code == 422, r.text
        assert r.json()["detail"] == "„von“ liegt nach „bis“"

    @pytest.mark.parametrize("rollen, code", [
        (["accounting"], 200), (["sales"], 200), (["admin"], 200),
        (["production_planner"], 403), (["production_staff"], 403),
    ], ids=["buchhaltung", "vertrieb", "admin", "planung", "halle"])
    def test_rechte_wie_die_rechnungen(self, client, rollen, code):
        """Wie /invoices (main.py: _deps_geld): Admin, Vertrieb, Buchhaltung."""
        from app.api.deps import get_current_user
        from app.main import app

        async def benutzer():
            return {"id": "123e4567-e89b-12d3-a456-426614174099", "username": "p4c",
                    "email": "p4c@example.com", "roles": rollen}
        app.dependency_overrides[get_current_user] = benutzer

        assert client.get("/api/v1/belegstatus").status_code == code


class TestP4CBelegstatusAnzeige:
    """Anzeige der Spalten (frontend/src/services/belegstatus.ts): die
    Node-Prüfung läuft im Vollauf mit (wie die Node-Tests aus Paket 3 und O)."""

    def test_node_pruefung(self):
        import os
        import subprocess
        from pathlib import Path
        r = subprocess.run(
            ["node", "tests/unit/belegstatus.check.ts"],
            cwd=Path(__file__).resolve().parents[2] / "frontend",
            env={**os.environ, "TZ": "UTC"}, capture_output=True, text=True, timeout=60,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert r.stdout.strip() == "belegstatus.check: 29 Fälle ok"


# =============================================================================
# Abschnitt D — Rechte der Rolle Produktion bei Kunden-Stammdaten (G41, B8)
# Präfixe: Klassen TestP4D…, Helfer _p4d_…, Konstanten _P4D_…
# =============================================================================
import pytest

from app.api.deps import get_current_user
from app.main import app

_P4D_USER_ID = "123e4567-e89b-12d3-a456-426614174000"
# Rollen außer der Halle (app.core.rollen.ROLLEN_OHNE_HALLE) bzw. kaufmännisch
# (KAUFMAENNISCHE_ROLLEN) — als eigene Listen, damit ein Test eine geänderte
# Matrix bemerkt.
_P4D_OHNE_HALLE = ["admin", "sales", "accounting", "production_planner"]
_P4D_KAUFMAENNISCH = ["admin", "sales", "accounting"]


def _p4d_als(*rollen):
    """Login mit genau diesen Rollen (Muster tests/test_rollen.py::_als).
    Das client-Fixture setzt das Login beim nächsten Test neu."""
    async def override():
        return {"id": _P4D_USER_ID, "username": "p4d", "email": "p4d@example.com",
                "roles": list(rollen)}
    app.dependency_overrides[get_current_user] = override


def _p4d_verwaltung():
    """Zurück auf das Standard-Login des client-Fixtures (conftest.py)."""
    _p4d_als("admin", "production_planner")


def _p4d_kunde(client, **felder):
    """Kunde, angelegt von der Verwaltung (darf auch Konditionen setzen)."""
    _p4d_verwaltung()
    r = client.post("/api/v1/sales/customers", json={
        "name": "Großer Kern", "typ": "GASTRO", "email": "kueche@grosser-kern.de",
        "liefertage": [1, 3], "confirmation_emails": ["ab@grosser-kern.de"], **felder})
    assert r.status_code == 201, r.text
    return r.json()


def _p4d_adresse(client, kunde, **felder):
    _p4d_verwaltung()
    r = client.post(f"/api/v1/sales/customers/{kunde['id']}/addresses", json={
        "address_type": "SHIPPING", "is_default": True, "strasse": "Lieferhof",
        "hausnummer": "3", "plz": "80331", "ort": "München", **felder})
    assert r.status_code == 201, r.text
    return r.json()


def _p4d_kontakt(client, kunde):
    _p4d_verwaltung()
    r = client.post(f"/api/v1/sales/customers/{kunde['id']}/contacts",
                    json={"name": "Anna Koch", "email": "anna@grosser-kern.de"})
    assert r.status_code == 201, r.text
    return r.json()


def _p4d_kunde_db(kunde_id):
    from uuid import UUID
    from app.models.customer import Customer
    from tests.conftest import TestingSessionLocal
    with TestingSessionLocal() as db:
        k = db.get(Customer, UUID(kunde_id))
        return {"aktiv": k.aktiv, "discount_percent": k.discount_percent,
                "payment_terms": k.payment_terms.value, "telefon": k.telefon}


class TestP4DStammdatenLoeschen:
    """G41 (Gernot, 08.10. B8): Mitarbeiter löschen keine Stammdaten. Adressen und
    Ansprechpartner löschen nur Rollen ohne die Halle (wie Sonderpreise, T5 R2);
    Anlegen und Ändern bleiben der Halle erlaubt (Gernot, 03.09.)."""

    def test_halle_loescht_keine_adresse(self, client):
        kunde = _p4d_kunde(client)
        adresse = _p4d_adresse(client, kunde)
        _p4d_als("production_staff")

        r = client.delete(f"/api/v1/sales/customers/{kunde['id']}/addresses/{adresse['id']}")

        assert r.status_code == 403, r.text
        _p4d_verwaltung()
        ids = [a["id"] for a in client.get(f"/api/v1/sales/customers/{kunde['id']}/addresses").json()]
        assert adresse["id"] in ids

    def test_halle_loescht_keinen_ansprechpartner(self, client):
        kunde = _p4d_kunde(client)
        kontakt = _p4d_kontakt(client, kunde)
        _p4d_als("production_staff")

        r = client.delete(f"/api/v1/sales/customers/{kunde['id']}/contacts/{kontakt['id']}")

        assert r.status_code == 403, r.text
        _p4d_verwaltung()
        ids = [c["id"] for c in client.get(f"/api/v1/sales/customers/{kunde['id']}/contacts").json()]
        assert kontakt["id"] in ids

    @pytest.mark.parametrize("rolle", _P4D_OHNE_HALLE)
    def test_rollen_ohne_halle_loeschen_adresse_und_ansprechpartner(self, client, rolle):
        kunde = _p4d_kunde(client)
        adresse = _p4d_adresse(client, kunde)
        kontakt = _p4d_kontakt(client, kunde)
        _p4d_als(rolle)

        assert client.delete(
            f"/api/v1/sales/customers/{kunde['id']}/addresses/{adresse['id']}").status_code == 204
        assert client.delete(
            f"/api/v1/sales/customers/{kunde['id']}/contacts/{kontakt['id']}").status_code == 204

    def test_halle_legt_adresse_und_ansprechpartner_weiter_an_und_aendert_sie(self, client):
        """Gernot, 03.09.: bei Ausfall der Betriebsleitung erfassen die Mitarbeiter."""
        kunde = _p4d_kunde(client)
        _p4d_als("production_staff")

        r = client.post(f"/api/v1/sales/customers/{kunde['id']}/addresses", json={
            "address_type": "SHIPPING", "strasse": "Hof", "plz": "80331", "ort": "München"})
        assert r.status_code == 201, r.text
        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}/addresses/{r.json()['id']}",
                         json={"lieferhinweise": "Tor 2"})
        assert r.status_code == 200, r.text
        r = client.post(f"/api/v1/sales/customers/{kunde['id']}/contacts", json={"name": "Ben"})
        assert r.status_code == 201, r.text
        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}/contacts/{r.json()['id']}",
                         json={"telefon": "089 1"})
        assert r.status_code == 200, r.text


class TestP4DKundeAktivSchalter:
    """Deaktivieren ist die weiche Form des Löschens: DELETE /customers deaktiviert
    einen Kunden mit Belegen und ist nur kaufmännisch (Q4-Liste). Derselbe Schritt
    über PATCH aktiv bzw. sein Gegenstück /reactivate folgt derselben Regel."""

    def test_halle_deaktiviert_keinen_kunden(self, client):
        kunde = _p4d_kunde(client)
        _p4d_als("production_staff")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"aktiv": False})

        assert r.status_code == 403, r.text
        assert r.json()["detail"].startswith(
            "Kunden deaktivieren und reaktivieren nur Verwaltung, Vertrieb und Buchhaltung: Aktiv.")
        assert _p4d_kunde_db(kunde["id"])["aktiv"] is True

    def test_planung_deaktiviert_keinen_kunden(self, client):
        kunde = _p4d_kunde(client)
        _p4d_als("production_planner")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"aktiv": False})

        assert r.status_code == 403, r.text
        assert _p4d_kunde_db(kunde["id"])["aktiv"] is True

    def test_halle_reaktiviert_keinen_kunden(self, client):
        kunde = _p4d_kunde(client)
        assert client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"aktiv": False}).status_code == 200
        _p4d_als("production_staff")

        assert client.post(f"/api/v1/sales/customers/{kunde['id']}/reactivate").status_code == 403
        assert client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"aktiv": True}).status_code == 403
        assert _p4d_kunde_db(kunde["id"])["aktiv"] is False

    @pytest.mark.parametrize("rolle", _P4D_KAUFMAENNISCH)
    def test_kaufmaennische_rollen_deaktivieren_und_reaktivieren(self, client, rolle):
        kunde = _p4d_kunde(client)
        _p4d_als(rolle)

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"aktiv": False})
        assert r.status_code == 200, r.text
        r = client.post(f"/api/v1/sales/customers/{kunde['id']}/reactivate")
        assert r.status_code == 200, r.text
        assert _p4d_kunde_db(kunde["id"])["aktiv"] is True

    def test_unveraendertes_aktiv_bleibt_fuer_die_halle_erlaubt(self, client):
        """Ein Formular schickt aktiv immer mit; ohne Änderung ist das kein Deaktivieren."""
        kunde = _p4d_kunde(client)
        _p4d_als("production_staff")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}",
                         json={"aktiv": True, "telefon": "089 123"})

        assert r.status_code == 200, r.text
        assert _p4d_kunde_db(kunde["id"])["telefon"] == "089 123"


from decimal import Decimal

# Konditionen eines Kunden in Antworten (app.core.rollen.KUNDENANTWORT_KONDITIONEN):
# die Felder aus KUNDENFELDER_KAUFMAENNISCH plus die nur lesbaren Ableitungen.
_P4D_KONDITIONSFELDER = {
    "payment_terms", "credit_limit", "price_list_id", "discount_percent", "skonto_percent",
    "skonto_days", "packaging_fee_amount", "packaging_fee_percent", "datev_account",
    "pfand_abrechnung", "invoice_mode",
    "price_list_name", "payment_days", "pfand_monatlich_ab", "zahlungsart",
}


def _p4d_preisliste():
    from app.models.product import PriceList
    from tests.conftest import TestingSessionLocal
    with TestingSessionLocal() as db:
        liste = PriceList(name="Gastro 2026", code="GASTRO26")
        db.add(liste)
        db.commit()
        return str(liste.id)


def _p4d_kunde_mit_konditionen(client, **felder):
    konditionen = {
        "payment_terms": "NET_30", "discount_percent": "5", "skonto_percent": "2",
        "skonto_days": 10, "credit_limit": "5000", "packaging_fee_amount": "4.5",
        "packaging_fee_percent": "1", "datev_account": "10077",
        "pfand_abrechnung": "MONATLICH", "invoice_mode": "MONATLICH",
        "price_list_id": _p4d_preisliste(),
    }
    return _p4d_kunde(client, **{**konditionen, **felder})


def _p4d_produkt(client, sku="KRESSE-50", preis="2.50"):
    from app.models.unit import UnitOfMeasure, UnitCategory
    from tests.conftest import TestingSessionLocal
    with TestingSessionLocal() as db:
        unit = db.query(UnitOfMeasure).filter_by(code="STK").first()
        if unit is None:
            unit = UnitOfMeasure(code="STK", name="Stück", symbol="Stk",
                                 category=UnitCategory.COUNT, is_base_unit=True)
            db.add(unit)
            db.commit()
        unit_id = str(unit.id)
    _p4d_verwaltung()
    r = client.post("/api/v1/products", json={
        "sku": sku, "name": "Kresse 50 g", "base_price": preis,
        "category": "MICROGREEN", "base_unit_id": unit_id})
    assert r.status_code == 201, r.text
    return r.json()


def _p4d_bestellung(client, kunde, produkt, preis="2.50"):
    from datetime import date, timedelta
    return client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"],
        "requested_delivery_date": (date.today() + timedelta(days=3)).isoformat(),
        "lines": [{"product_id": produkt["id"], "product_name": produkt["name"],
                   "quantity": 3, "unit": "STK", "unit_price": preis}],
    })


class TestP4DKonditionenAusgeblendet:
    """Gernot, 09.10. („Rolle Produktion ohne Rechnungen/Konditionen“: „Danke!“):
    Kundenantworten an die Halle tragen keine Konditionen — weder Liste noch
    Detail noch die Antwort auf eine Änderung. Reaktivieren darf sie nicht (P4-D.1)."""

    def test_konditionsliste_deckt_den_feldschutz_ab(self):
        from app.core.rollen import KUNDENANTWORT_KONDITIONEN, KUNDENFELDER_KAUFMAENNISCH
        assert set(KUNDENFELDER_KAUFMAENNISCH) <= set(KUNDENANTWORT_KONDITIONEN)
        assert set(KUNDENANTWORT_KONDITIONEN) == _P4D_KONDITIONSFELDER

    def test_halle_sieht_in_liste_und_detail_keine_konditionen(self, client):
        kunde = _p4d_kunde_mit_konditionen(client)
        _p4d_als("production_staff")

        liste = client.get("/api/v1/sales/customers", params={"search": "Großer Kern"})
        detail = client.get(f"/api/v1/sales/customers/{kunde['id']}")

        assert liste.status_code == 200, liste.text
        assert detail.status_code == 200, detail.text
        for antwort in (liste.json()["items"][0], detail.json()):
            assert {f: antwort[f] for f in _P4D_KONDITIONSFELDER} == dict.fromkeys(_P4D_KONDITIONSFELDER)
            # Was die Halle für Bestellung und Belegversand braucht, bleibt.
            assert antwort["id"] == kunde["id"]
            assert antwort["name"] == "Großer Kern"
            assert antwort["customer_number"] == kunde["customer_number"]
            assert antwort["email"] == "kueche@grosser-kern.de"
            assert antwort["confirmation_emails"] == ["ab@grosser-kern.de"]
            assert antwort["liefertage"] == [1, 3]
            assert antwort["aktiv"] is True

    def test_halle_bekommt_beim_speichern_keine_konditionen_zurueck(self, client):
        kunde = _p4d_kunde_mit_konditionen(client)
        _p4d_als("production_staff")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"telefon": "089 777"})

        assert r.status_code == 200, r.text
        assert {f: r.json()[f] for f in _P4D_KONDITIONSFELDER} == dict.fromkeys(_P4D_KONDITIONSFELDER)
        gespeichert = _p4d_kunde_db(kunde["id"])
        assert gespeichert["telefon"] == "089 777"
        assert str(gespeichert["discount_percent"]) == "5.00"
        assert gespeichert["payment_terms"] == "NET_30"

    def test_halle_neuanlage_zeigt_nur_standardkonditionen_danach_keine(self, client):
        """Die Halle legt nur mit Standardkonditionen an (Paket 3, kundenfeldschutz);
        die Antwort darauf verrät nichts und bleibt wie bisher (Paket-3-Test
        test_halle_legt_kunden_mit_standardkonditionen_an). Danach liest sie den
        Kunden ohne Konditionen."""
        _p4d_als("production_staff")

        r = client.post("/api/v1/sales/customers", json={"name": "Fruchthof Nagel", "typ": "HANDEL"})

        assert r.status_code == 201, r.text
        k = r.json()
        assert (k["payment_terms"], k["discount_percent"], k["pfand_abrechnung"], k["invoice_mode"],
                k["credit_limit"], k["price_list_id"]) == ("NET_14", "0.00", "JE_LIEFERUNG", "EINZELN", None, None)
        detail = client.get(f"/api/v1/sales/customers/{k['id']}").json()
        assert {f: detail[f] for f in _P4D_KONDITIONSFELDER} == dict.fromkeys(_P4D_KONDITIONSFELDER)

    @pytest.mark.parametrize("rolle", _P4D_OHNE_HALLE)
    def test_rollen_ohne_halle_sehen_die_konditionen(self, client, rolle):
        kunde = _p4d_kunde_mit_konditionen(client)
        _p4d_als(rolle)

        k = client.get(f"/api/v1/sales/customers/{kunde['id']}").json()

        assert (k["payment_terms"], k["discount_percent"], k["credit_limit"], k["datev_account"]) == (
            "NET_30", "5.00", "5000.00", "10077")
        assert (k["payment_days"], k["pfand_abrechnung"], k["invoice_mode"]) == (30, "MONATLICH", "MONATLICH")
        assert k["price_list_id"] == kunde["price_list_id"] is not None
        assert k["pfand_monatlich_ab"] is not None

    def test_halle_mit_zusaetzlicher_vertriebsrolle_sieht_die_konditionen(self, client):
        kunde = _p4d_kunde_mit_konditionen(client)
        _p4d_als("production_staff", "sales")

        assert client.get(f"/api/v1/sales/customers/{kunde['id']}").json()["discount_percent"] == "5.00"

    def test_halle_speichert_das_formular_ohne_konditionen(self, client):
        """Kundenformular der Halle (P4-D.3, Customers.tsx mit ohneKonditionen):
        dieselben Felder wie das Formular, ohne Konditionen — gespeichert wird,
        die Konditionen bleiben. Schickt ein Client stattdessen die Vorgaben des
        Formulars (aus null wird NET_14 und 0), lehnt der Server ab (E-D3)."""
        kunde = _p4d_kunde_mit_konditionen(client)
        _p4d_als("production_staff")
        k = client.get(f"/api/v1/sales/customers/{kunde['id']}").json()
        formular = {
            "name": k["name"], "typ": k["typ"], "customer_number": k["customer_number"] or "",
            "email": k["email"] or "", "telefon": "089 555", "adresse": k["adresse"] or "",
            "ust_id": k["ust_id"] or "", "liefertage": k["liefertage"],
            "show_prices_on_delivery_note": k["show_prices_on_delivery_note"],
            "confirmation_emails": k["confirmation_emails"],
            "delivery_note_emails": k["delivery_note_emails"],
            "invoice_emails": k["invoice_emails"], "aktiv": k["aktiv"],
        }

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json=formular)

        assert r.status_code == 200, r.text
        gespeichert = _p4d_kunde_db(kunde["id"])
        assert (gespeichert["telefon"], gespeichert["payment_terms"], str(gespeichert["discount_percent"])) == (
            "089 555", "NET_30", "5.00")
        vorgaben = client.patch(f"/api/v1/sales/customers/{kunde['id']}",
                                json={**formular, "payment_terms": "NET_14", "discount_percent": 0})
        assert vorgaben.status_code == 403, vorgaben.text


class TestP4DSonderpreiseUndBestellung:
    """Sonderpreise sind Konditionen: die Liste je Kunde liest die Halle nicht mehr.
    Den einen gültigen Preis je Produkt für das Bestellformular liest sie weiter
    (Paket 3, test_halle_liest_sonderpreis_fuers_bestellformular) — Bestellungen
    und AB tragen Preise (Gernot, 08.10. B8)."""

    def _sonderpreis(self, client, kunde, produkt):
        _p4d_verwaltung()
        r = client.post(f"/api/v1/sales/customers/{kunde['id']}/prices",
                        json={"product_id": produkt["id"], "unit_price": "1.99"})
        assert r.status_code == 201, r.text

    def test_halle_liest_keine_sonderpreisliste(self, client):
        kunde = _p4d_kunde(client)
        produkt = _p4d_produkt(client)
        self._sonderpreis(client, kunde, produkt)
        _p4d_als("production_staff")

        r = client.get(f"/api/v1/sales/customers/{kunde['id']}/prices")

        assert r.status_code == 403, r.text
        r = client.get(f"/api/v1/sales/customers/{kunde['id']}/effective-price/{produkt['id']}")
        assert r.status_code == 200, r.text
        assert Decimal(r.json()["unit_price"]) == Decimal("1.99")

    @pytest.mark.parametrize("rolle", _P4D_OHNE_HALLE)
    def test_rollen_ohne_halle_lesen_die_sonderpreisliste(self, client, rolle):
        kunde = _p4d_kunde(client)
        produkt = _p4d_produkt(client)
        self._sonderpreis(client, kunde, produkt)
        _p4d_als(rolle)

        r = client.get(f"/api/v1/sales/customers/{kunde['id']}/prices")

        assert r.status_code == 200, r.text
        assert [Decimal(p["unit_price"]) for p in r.json()] == [Decimal("1.99")]

    def test_halle_legt_bestellung_mit_lieferadresse_an(self, client):
        """Ablauf des Bestellformulars (CreateOrderModal): Kundenliste, gültiger
        Preis, Speichern. Die Lieferadresse setzt der Server aus dem Kundenstamm."""
        kunde = _p4d_kunde_mit_konditionen(client, credit_limit=None)
        _p4d_adresse(client, kunde)
        produkt = _p4d_produkt(client)
        _p4d_als("production_staff")

        ids = [k["id"] for k in client.get("/api/v1/sales/customers").json()["items"]]
        preis = client.get(f"/api/v1/sales/customers/{kunde['id']}/effective-price/{produkt['id']}")
        r = _p4d_bestellung(client, kunde, produkt, preis.json()["unit_price"])

        assert kunde["id"] in ids
        assert r.status_code == 201, r.text
        assert r.json()["delivery_address"]["strasse"] == "Lieferhof"
        assert r.json()["customer_name"] == "Großer Kern"

    def test_kreditlimit_meldung_ohne_betraege_fuer_die_halle(self, client):
        kunde = _p4d_kunde(client, credit_limit="1")
        produkt = _p4d_produkt(client)
        _p4d_als("production_staff")

        r = _p4d_bestellung(client, kunde, produkt)

        assert r.status_code == 400, r.text
        assert r.json()["detail"] == (
            "Kreditlimit des Kunden überschritten. Bitte Verwaltung, Vertrieb oder Buchhaltung fragen.")
        _p4d_verwaltung()
        r = _p4d_bestellung(client, kunde, produkt)
        assert r.status_code == 400, r.text
        assert r.json()["detail"].startswith("Kreditlimit überschritten: Limit 1.00 EUR")


class TestP4DHalleOhneGeldUndKonditionen:
    """Wachhund (G41: kein Rechnungswesen, kein DATEV; G60: keine Konditionen):
    jede Route der Geldseite und jede Konditionsroute antwortet der Halle mit 403
    — auch Routen, die später dazukommen (z. B. GET /invoices/datev-export/einstellungen
    aus dem Nachtrag 09.10.)."""

    # /api/v1/belegstatus: Belegstatus aus Paket 4, C.3 (_deps_geld wie /invoices)
    _PRAEFIXE = ("/api/v1/invoices", "/api/v1/price-lists", "/api/v1/sepa", "/api/v1/analytics", "/api/v1/belegstatus")
    _EINZELN = {
        "/api/v1/sales/customers/export/datev",
        "/api/v1/sales/customers/{customer_id}/prices",
        "/api/v1/sales/customer-prices/{price_id}",
        "/api/v1/products/{product_id}/price",
    }

    def test_jede_geld_und_konditionsroute_sperrt_die_halle(self, client):
        import re
        from fastapi.routing import APIRoute
        _p4d_als("production_staff")
        geprueft, offen = [], []
        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue
            if not (route.path.startswith(self._PRAEFIXE) or route.path in self._EINZELN):
                continue
            pfad = re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-0000000000ff", route.path)
            for methode in sorted(route.methods - {"HEAD", "OPTIONS"}):
                geprueft.append(f"{methode} {route.path}")
                code = client.request(methode, pfad, json={}).status_code
                if code != 403:
                    offen.append(f"{methode} {route.path} -> {code}")

        assert offen == []
        assert len(geprueft) >= 50, geprueft

    def test_produktdetail_zeigt_der_halle_keine_preislistenpositionen(self, client):
        produkt = _p4d_produkt(client)
        _p4d_als("production_staff")

        r = client.get(f"/api/v1/products/{produkt['id']}")

        assert r.status_code == 200, r.text
        assert r.json()["prices"] is None


_P4FIX_FUSS = (
    "Testbank - Bankverbindung auf jeder Seite\n"
    "Geschäftsführung: Erika Muster - HRB 123456\n"
    "USt-ID DE123456789 - Steuer-Nr. 123/456/789"
)


def _p4fix1_belege(client, anzahl, bundles=False):
    from datetime import date
    for art in ("RECHNUNG", "LIEFERSCHEIN", "AUFTRAGSBESTAETIGUNG", "MAHNUNG", "VERPACKUNGSLISTE"):
        antwort = client.patch(f"/api/v1/document-templates/{art}", json={"texts": {
            "header_text": "Testfarm GmbH - Feldweg 1 - 80000 München",
            "footer_text": _P4FIX_FUSS,
        }})
        assert antwort.status_code == 200, antwort.text
    kunde = _p4c_kunde(client, "PDF Testkunde", skonto_percent=2, skonto_days=10)
    positionen = []
    mix = None
    if bundles:
        sorten = [_p4a_produkt(client, name, f"FIX1-{index}") for index, name in enumerate(
            ("BIO Erbsensprossen", "BIO Sonnenblumen", "BIO Radieschen", "BIO Brokkoli", "BIO Rucola", "BIO Rotkohl"))]
        mix = _p4a_mix(client, [(sorte, 1) for sorte in sorten], sku="FIX1-MIX")
    for index in range(anzahl):
        position = {"product_name": "BIO Sonnenblume Microgreens frisch geschnitten in der Mehrwegschale 100 Gramm",
                    "quantity": 4, "unit": "STK", "unit_price": 2.5, "tax_rate": "REDUZIERT"}
        if mix and index < 2:
            position.update(product_id=mix["id"], product_name=mix["name"])
        positionen.append(position)
    antwort = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"], "requested_delivery_date": date.today().isoformat(),
        "lines": positionen,
    })
    assert antwort.status_code == 201, antwort.text
    order = antwort.json()
    rechnung = _p4c_rechnung(client, order["id"])
    antwort = client.post(f"/api/v1/sales/orders/{order['id']}/delivery-notes", json={})
    assert antwort.status_code == 201, antwort.text
    return rechnung, antwort.json()


@pytest.mark.usefixtures("_p4a_ohne_celery")
class TestP4Fix1PDFSeiten:
    @pytest.mark.parametrize("art", ["rechnung", "lieferschein"])
    @pytest.mark.parametrize("anzahl,bundles", [(3, True), (12, False)])
    def test_seiten_fuss_folgekopf_und_summen(self, client, tmp_path, art, anzahl, bundles):
        import subprocess
        rechnung, lieferschein = _p4fix1_belege(client, anzahl, bundles)
        if art == "rechnung":
            pfad = f"/api/v1/invoices/{rechnung['id']}/pdf"
            nummer = rechnung["invoice_number"]
        else:
            pfad = f"/api/v1/sales/delivery-notes/{lieferschein['id']}/pdf"
            nummer = lieferschein["delivery_note_number"]
        antwort = client.get(pfad)
        assert antwort.status_code == 200, antwort.text
        datei = tmp_path / f"{art}-{anzahl}.pdf"
        datei.write_bytes(antwort.content)
        text = subprocess.run(["pdftotext", "-layout", str(datei), "-"],
                              check=True, capture_output=True, text=True).stdout
        seiten = text.rstrip("\f").split("\f")
        if bundles:
            assert len(seiten) == 1
            assert "BIO Erbsensprossen," in seiten[0]
            assert "Seite 1 von" not in seiten[0]
        else:
            assert len(seiten) >= 2
            assert nummer in seiten[1]
            assert "Beschreibung" in seiten[1]
            for index, text in enumerate(seiten, 1):
                assert f"Seite {index} von {len(seiten)}" in text
        for text in seiten:
            for zeile in _P4FIX_FUSS.splitlines():
                assert zeile in text
        assert Decimal(str(rechnung["subtotal"])) == Decimal(anzahl * 10)
        assert Decimal(str(rechnung["total"])) == Decimal(anzahl * 10) * Decimal("1.07")
        if art == "rechnung":
            assert f"{anzahl * 10:.2f} €" in " ".join(seiten)


@pytest.mark.usefixtures("_p4a_ohne_celery")
class TestP4Fix2Festschreibung:
    def test_fakturierter_positionsbezug_sperrt_ohne_nummernverbrauch(self, client):
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde)
        _p4b_status(client, bestellung, "GELIEFERT")
        position = {"description": "Erbsen", "quantity": 10, "unit": "STK", "unit_price": "2.50",
                    "order_item_id": bestellung["lines"][0]["id"]}
        antwort = client.post("/api/v1/invoices", json={
            "customer_id": kunde["id"], "invoice_date": _p4b_date.today().isoformat(), "lines": [position]})
        assert antwort.status_code == 201, antwort.text
        entwurf = antwort.json()
        assert entwurf["order_id"] is None
        antwort = client.post("/api/v1/sales/orders/bulk-status", json={
            "order_ids": [bestellung["id"]], "status": "FAKTURIERT"})
        assert antwort.status_code == 200, antwort.text
        antwort = client.post(f"/api/v1/invoices/{entwurf['id']}/finalize")
        assert antwort.status_code == 409, antwort.text
        assert antwort.json()["detail"] == _p4b_meldung(bestellung) + " Diesen Entwurf verwerfen."
        nachher = client.get(f"/api/v1/invoices/{entwurf['id']}").json()
        assert (nachher["status"], nachher["invoice_number"]) == ("ENTWURF", entwurf["invoice_number"])
        position.pop("order_item_id")
        neu = client.post("/api/v1/invoices", json={
            "customer_id": kunde["id"], "invoice_date": _p4b_date.today().isoformat(), "lines": [position]}).json()
        fertig = client.post(f"/api/v1/invoices/{neu['id']}/finalize")
        assert fertig.status_code == 200, fertig.text
        assert fertig.json()["invoice_number"].endswith("-00001")


def _p4fix_entwurf(client, **position):
    kunde = _p4b_kunde(client)
    antwort = client.post("/api/v1/invoices", json={
        "customer_id": kunde["id"], "invoice_date": _p4b_date.today().isoformat(),
        "lines": [{"description": "Testposition", "quantity": "1", "unit": "STK",
                   "unit_price": "2.5", **position}],
    })
    assert antwort.status_code == 201, antwort.text
    return client.get(f"/api/v1/invoices/{antwort.json()['id']}").json()


class TestP4Fix3Positionsgrenzen:
    @pytest.mark.parametrize("weg", ["rechnung", "anlegen", "aendern"])
    @pytest.mark.parametrize("werte,feld", [
        ({"quantity": "1000000000000"}, "Menge"),
        ({"quantity": "1.0005"}, "Menge"),
        ({"unit_price": "1.00005"}, "Einzelpreis"),
        ({"quantity": "1000000000000000", "unit_price": "1000000000"}, "Menge"),
        ({"quantity": "10000000"}, "Menge"),
        ({"unit_price": "1000000"}, "Einzelpreis"),
        ({"quantity": "0"}, "Menge"),
        ({"quantity": "-1"}, "Menge"),
        ({"unit_price": "-0.0001"}, "Einzelpreis"),
    ])
    def test_unzulaessige_werte_werden_deutsch_abgelehnt(self, client, weg, werte, feld):
        entwurf = _p4fix_entwurf(client)
        position = {"description": "Grenztest", "quantity": "1", "unit": "STK", "unit_price": "1", **werte}
        if weg == "rechnung":
            antwort = client.post("/api/v1/invoices", json={
                "customer_id": entwurf["customer_id"], "invoice_date": _p4b_date.today().isoformat(),
                "lines": [position]})
        elif weg == "anlegen":
            antwort = client.post(f"/api/v1/invoices/{entwurf['id']}/lines", json=position)
        else:
            antwort = client.patch(f"/api/v1/invoices/{entwurf['id']}/lines/{entwurf['lines'][0]['id']}", json=werte)
        assert antwort.status_code == 422, antwort.text
        assert feld in antwort.json()["detail"][0]["msg"]
        assert "Nachkommastellen" in antwort.json()["detail"][0]["msg"]
        nachher = client.get(f"/api/v1/invoices/{entwurf['id']}").json()
        assert len(nachher["lines"]) == 1
        assert Decimal(nachher["lines"][0]["quantity"]) == 1
        assert Decimal(nachher["lines"][0]["unit_price"]) == Decimal("2.5")

    @pytest.mark.parametrize("werte", [
        {"quantity": "9999999.999", "unit_price": "999999.9999"},
        {"quantity": "0.001", "unit_price": "0"},
    ])
    def test_grenzwerte_zulaessig(self, client, werte):
        entwurf = _p4fix_entwurf(client, **werte)
        position = entwurf["lines"][0]
        for feld, wert in werte.items():
            assert Decimal(position[feld]) == Decimal(wert)
        antwort = client.patch(f"/api/v1/invoices/{entwurf['id']}/lines/{position['id']}", json=werte)
        assert antwort.status_code == 200, antwort.text

    def test_interne_stornozeilen_bleiben_negativ(self, client):
        entwurf = _p4fix_entwurf(client)
        assert client.post(f"/api/v1/invoices/{entwurf['id']}/finalize").status_code == 200
        antwort = client.post(f"/api/v1/invoices/{entwurf['id']}/cancel", json={
            "reason": "Synthetischer Grenztest", "create_credit_note": True})
        assert antwort.status_code == 200, antwort.text
        storno = client.get(f"/api/v1/invoices/{antwort.json()['credit_note']['id']}").json()
        assert Decimal(storno["lines"][0]["quantity"]) == -1
