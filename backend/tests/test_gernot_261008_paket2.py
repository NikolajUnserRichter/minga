"""Gernot-Feedback vom 07./08.10.2026 — Paket 2: Tagesplan und Status.

A1: "Ausgeliefert" wurde nicht angezeigt. Drei Wege nach GELIEFERT mit drei
    verschiedenen Regeln (Status-Endpunkt ohne Lieferdatum, Lieferschein-
    Quittieren ohne Übergangsregel und Audit-Log, Sammel-Endpunkt ohne
    alles); der Tagesplan zeigte rohe Enum-Werte und GELIEFERT gar nicht.
A4: Gepackte Bestellungen zählten weiter in "Verpacken" und im Sortenbedarf
    (Block "P2 / A4", Helfer _a4_).
A2: Die Spalte "Kunde" der Rechnungsliste blieb leer (Block "P3 / A2",
    Helfer _a2_).
A5: Abo-Bestellungen ohne Produkt, Preis und Satz; mehrere Liefertage
    wirkten nicht (Block "P4", Helfer _p4_).
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.conftest import TestingSessionLocal

TEST_USER_ID = "123e4567-e89b-12d3-a456-426614174000"  # aus conftest.client


@pytest.fixture(autouse=True)
def _ohne_prognose_anstoss(monkeypatch):
    """Bestätigen und Stornieren stoßen per Celery eine Prognose an. Ohne Redis
    hängt jeder Aufruf in Verbindungsversuchen — für diese Tests ohne Belang."""
    monkeypatch.setattr("app.api.v1.sales._trigger_forecast_update", lambda *a, **k: None)


# ---------------------------------------------------------------- Helfer

def _heute():
    """Liefertag laut Server (Europe/Berlin). date.today() wäre auf einem
    UTC-Rechner zwischen 22 und 24 Uhr UTC noch der Vortag."""
    from app.services.order_status_service import heute_berlin
    return heute_berlin()


def _kunde(client, name="Ökoring"):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "HANDEL"})
    assert r.status_code == 201, r.text
    return r.json()


def _bestellung(client, kunde, liefertag=None, lines=None):
    """Bestellung im Status ENTWURF."""
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"],
        "requested_delivery_date": (liefertag or date.today()).isoformat(),
        "lines": lines or [{"product_name": "Erbsen-Schale", "quantity": 2, "unit": "STK",
                            "unit_price": 3.0, "tax_rate": "REDUZIERT"}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _bestaetigt(client, kunde, liefertag=None, lines=None):
    o = _bestellung(client, kunde, liefertag, lines)
    r = client.post(f"/api/v1/sales/orders/{o['id']}/confirm")
    assert r.status_code == 200, r.text
    return r.json()


def _gepackt(client, kunde, liefertag=None, lines=None):
    o = _bestaetigt(client, kunde, liefertag, lines)
    r = _status(client, o, "IN_PRODUKTION")
    assert r.status_code == 200, r.text
    return r.json()


def _status(client, order, status, **extra):
    return client.post(f"/api/v1/sales/orders/{order['id']}/status",
                       json={"status": status, **extra})


def _lesen(client, order):
    r = client.get(f"/api/v1/sales/orders/{order['id']}")
    assert r.status_code == 200, r.text
    return r.json()


def _audit(client, order):
    r = client.get(f"/api/v1/sales/orders/{order['id']}/audit-log")
    assert r.status_code == 200, r.text
    return r.json()  # neuester Eintrag zuerst


def _plan(client, tag=None):
    r = client.get("/api/v1/production/day-plan",
                   params={"target_date": (tag or date.today()).isoformat()})
    assert r.status_code == 200, r.text
    return r.json()


def _lieferschein(client, order):
    r = client.post(f"/api/v1/sales/orders/{order['id']}/delivery-notes", json={})
    assert r.status_code == 201, r.text
    return r.json()


def _quittieren(client, note, **body):
    return client.patch(f"/api/v1/sales/delivery-notes/{note['id']}/mark-delivered", json=body)


def _produkt(client, name="Erbse", sku="MG-ERB-261008"):
    from app.models.unit import UnitOfMeasure, UnitCategory
    with TestingSessionLocal() as db:
        unit = db.query(UnitOfMeasure).filter_by(code="STK").first()
        if unit is None:
            unit = UnitOfMeasure(code="STK", name="Stück", category=UnitCategory.COUNT)
            db.add(unit)
            db.commit()
        unit_id = str(unit.id)
    r = client.post("/api/v1/products", json={
        "name": name, "sku": sku, "base_price": "3.00",
        "category": "MICROGREEN", "base_unit_id": unit_id,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _fertigware(produkt, gramm):
    """Fertigwarenbestand direkt über das ORM — es gibt keinen schlanken API-Weg."""
    from app.models.inventory import FinishedGoodsInventory
    with TestingSessionLocal() as db:
        inv = FinishedGoodsInventory(
            product_id=uuid.UUID(produkt["id"]), batch_number="FW-261008",
            initial_quantity_g=Decimal(gramm), current_quantity_g=Decimal(gramm),
            harvest_date=date.today(), best_before_date=date.today() + timedelta(days=7),
        )
        db.add(inv)
        db.commit()
        return str(inv.id)


def _bestand(inventory_id):
    from app.models.inventory import FinishedGoodsInventory
    with TestingSessionLocal() as db:
        return db.get(FinishedGoodsInventory, uuid.UUID(inventory_id)).current_quantity_g


def _grammzeile(produkt, gramm=100):
    return [{"product_id": produkt["id"], "product_name": produkt["name"], "quantity": gramm,
             "unit": "g", "unit_price": 0.05, "tax_rate": "REDUZIERT"}]


# ------------------------------------------- Task 1: eine Statusregel

class TestStatusregel:
    """A1: BESTAETIGT → GELIEFERT fehlte, gepackt ließ sich nicht stornieren."""

    def test_uebergangstabelle(self):
        from app.models.order import OrderStatus as S
        from app.services.order_status_service import ERLAUBTE_UEBERGAENGE
        assert ERLAUBTE_UEBERGAENGE == {
            S.ENTWURF: (S.BESTAETIGT, S.STORNIERT),
            S.BESTAETIGT: (S.IN_PRODUKTION, S.GELIEFERT, S.STORNIERT),
            S.IN_PRODUKTION: (S.GELIEFERT, S.STORNIERT),
            S.GELIEFERT: (S.FAKTURIERT,),
            S.FAKTURIERT: (),
            S.STORNIERT: (),
        }

    def test_bestaetigt_direkt_ausgeliefert(self, client):
        o = _bestaetigt(client, _kunde(client))
        r = _status(client, o, "GELIEFERT")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "GELIEFERT"
        assert r.json()["actual_delivery_date"] == _heute().isoformat()

    def test_gepackt_darf_storniert_werden(self, client):
        o = _gepackt(client, _kunde(client))
        r = _status(client, o, "STORNIERT", reason="Kunde hat abgesagt")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "STORNIERT"

    def test_entwurf_nicht_direkt_geliefert(self, client):
        o = _bestellung(client, _kunde(client))
        r = _status(client, o, "GELIEFERT")
        assert r.status_code == 400
        assert r.json()["detail"] == "Statuswechsel nicht möglich: Entwurf → Geliefert"
        assert _lesen(client, o)["status"] == "ENTWURF"

    def test_fehlertext_ohne_enum_wert(self, client):
        o = _gepackt(client, _kunde(client))
        r = _status(client, o, "FAKTURIERT")
        assert r.status_code == 400
        assert r.json()["detail"] == "Statuswechsel nicht möglich: Gepackt → Fakturiert"

    def test_geliefert_bucht_bestand(self, client):
        produkt = _produkt(client)
        lager = _fertigware(produkt, 1000)
        o = _bestaetigt(client, _kunde(client), lines=_grammzeile(produkt, 100))
        assert _status(client, o, "GELIEFERT").status_code == 200
        assert _bestand(lager) == Decimal("900")

    def test_audit_log_mit_lieferdatum_und_nutzer(self, client):
        o = _bestaetigt(client, _kunde(client))
        _status(client, o, "GELIEFERT")
        eintrag = _audit(client, o)[0]
        assert eintrag["action"] == "STATUS_CHANGE"
        assert eintrag["old_values"]["status"] == "BESTAETIGT"
        assert eintrag["new_values"] == {"status": "GELIEFERT",
                                         "actual_delivery_date": _heute().isoformat()}
        assert eintrag["user_id"] == TEST_USER_ID
        assert eintrag["user_name"] == "testuser"

    def test_lieferdatum_nachtragen(self, client):
        gestern = date.today() - timedelta(days=1)
        o = _bestaetigt(client, _kunde(client), liefertag=gestern)
        r = _status(client, o, "GELIEFERT", actual_delivery_date=gestern.isoformat())
        assert r.status_code == 200, r.text
        assert r.json()["actual_delivery_date"] == gestern.isoformat()

    def test_lieferdatum_in_der_zukunft_abgelehnt(self, client):
        o = _bestaetigt(client, _kunde(client))
        r = _status(client, o, "GELIEFERT",
                    actual_delivery_date=(date.today() + timedelta(days=2)).isoformat())
        assert r.status_code == 400
        assert "Zukunft" in r.json()["detail"]
        assert _lesen(client, o)["status"] == "BESTAETIGT"

    def test_lieferdatum_nur_beim_liefern(self, client):
        o = _bestaetigt(client, _kunde(client))
        r = _status(client, o, "IN_PRODUKTION", actual_delivery_date=_heute().isoformat())
        assert r.status_code == 400

    def test_bestandsfehler_rollt_alles_zurueck(self, client, monkeypatch):
        """Status, Lieferdatum und Audit-Log nur zusammen mit dem Bestandsabzug."""
        def kaputt(*a, **k):
            raise RuntimeError("Lager gesperrt")
        monkeypatch.setattr("app.services.order_status_service.deduct_inventory_for_order", kaputt)
        o = _bestaetigt(client, _kunde(client))
        r = _status(client, o, "GELIEFERT")
        assert r.status_code == 500
        assert "Lager gesperrt" in r.json()["detail"]
        bestellung = _lesen(client, o)
        assert bestellung["status"] == "BESTAETIGT"
        assert bestellung["actual_delivery_date"] is None
        assert _audit(client, o)[0]["action"] == "CONFIRM"

    def test_geliefert_nicht_stornierbar(self, client):
        """Charakterisierung — schon vorher so, bleibt so (Bestand ist gebucht)."""
        o = _gepackt(client, _kunde(client))
        assert _status(client, o, "GELIEFERT").status_code == 200
        assert _status(client, o, "STORNIERT").status_code == 400

    def test_storno_nach_gepackt_bucht_keinen_bestand(self, client):
        """Bestand wird erst bei GELIEFERT gebucht: Packen und Stornieren
        lassen ihn unverändert (Entscheidung 08.10.2026)."""
        produkt = _produkt(client)
        lager = _fertigware(produkt, 1000)
        o = _gepackt(client, _kunde(client), lines=_grammzeile(produkt, 100))
        assert _bestand(lager) == Decimal("1000")
        assert _status(client, o, "STORNIERT", reason="Kunde hat abgesagt").status_code == 200
        assert _bestand(lager) == Decimal("1000")


# ------------------------- Task 2: Lieferschein quittieren, gleiche Regel

class TestLieferscheinQuittieren:
    """A1/LÜCKEN 4: Quittieren umging Übergangsregel und Audit-Log; das
    Lieferdatum war immer 'heute', auch beim Nachtragen."""

    def test_quittieren_liefert_mit_audit_log(self, client):
        o = _bestaetigt(client, _kunde(client))
        ls = _lieferschein(client, o)
        r = _quittieren(client, ls, signed_by="Fr. Huber")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "GELIEFERT"

        bestellung = _lesen(client, o)
        assert bestellung["status"] == "GELIEFERT"
        assert bestellung["actual_delivery_date"] == _heute().isoformat()
        eintrag = _audit(client, o)[0]
        assert eintrag["action"] == "LIEFERSCHEIN_QUITTIERT"
        assert eintrag["new_values"]["status"] == "GELIEFERT"
        assert ls["delivery_note_number"] in eintrag["reason"]
        assert eintrag["user_id"] == TEST_USER_ID

    def test_entwurf_kann_nicht_quittiert_werden(self, client):
        o = _bestellung(client, _kunde(client))
        ls = _lieferschein(client, o)
        r = _quittieren(client, ls, signed_by="X")
        assert r.status_code == 400
        assert "Entwurf → Geliefert" in r.json()["detail"]
        assert _lesen(client, o)["status"] == "ENTWURF"
        noten = client.get(f"/api/v1/sales/orders/{o['id']}/delivery-notes").json()
        assert noten[0]["status"] == "ENTWURF"

    def test_stornierte_bestellung_kann_nicht_quittiert_werden(self, client):
        o = _bestaetigt(client, _kunde(client))
        ls = _lieferschein(client, o)
        assert _status(client, o, "STORNIERT").status_code == 200
        assert _quittieren(client, ls).status_code == 400

    def test_lieferdatum_waehlbar(self, client):
        gestern = date.today() - timedelta(days=1)
        o = _bestaetigt(client, _kunde(client), liefertag=gestern)
        ls = _lieferschein(client, o)
        r = _quittieren(client, ls, actual_delivery_date=gestern.isoformat())
        assert r.status_code == 200, r.text
        assert r.json()["actual_delivery_date"] == gestern.isoformat()
        assert _lesen(client, o)["actual_delivery_date"] == gestern.isoformat()

    def test_lieferdatum_in_der_zukunft_abgelehnt(self, client):
        o = _bestaetigt(client, _kunde(client))
        ls = _lieferschein(client, o)
        r = _quittieren(client, ls, actual_delivery_date=(date.today() + timedelta(days=2)).isoformat())
        assert r.status_code == 400
        assert _lesen(client, o)["status"] == "BESTAETIGT"

    def test_quittieren_bucht_bestand(self, client):
        produkt = _produkt(client)
        lager = _fertigware(produkt, 1000)
        o = _bestaetigt(client, _kunde(client), lines=_grammzeile(produkt, 100))
        assert _quittieren(client, _lieferschein(client, o)).status_code == 200
        assert _bestand(lager) == Decimal("900")

    def test_altfall_lieferdatum_nachtragen_ohne_zweite_buchung(self, client):
        """Gernots fünf Bestellungen: per Status-Endpunkt geliefert, ohne Lieferdatum,
        Lieferschein noch offen. Nachträgliches Quittieren trägt das echte Datum nach."""
        from app.models.order import Order
        produkt = _produkt(client)
        lager = _fertigware(produkt, 1000)
        gestern = date.today() - timedelta(days=1)
        o = _bestaetigt(client, _kunde(client), liefertag=gestern, lines=_grammzeile(produkt, 100))
        ls = _lieferschein(client, o)
        assert _status(client, o, "GELIEFERT").status_code == 200
        with TestingSessionLocal() as db:  # Zustand vor dem Fix nachstellen
            db.get(Order, uuid.UUID(o["id"])).actual_delivery_date = None
            db.commit()

        r = _quittieren(client, ls, signed_by="Fahrer", actual_delivery_date=gestern.isoformat())
        assert r.status_code == 200, r.text
        bestellung = _lesen(client, o)
        assert bestellung["status"] == "GELIEFERT"
        assert bestellung["actual_delivery_date"] == gestern.isoformat()
        assert _bestand(lager) == Decimal("900"), "Bestand darf nicht zweimal gebucht werden"
        assert _audit(client, o)[0]["action"] == "LIEFERDATUM_NACHGETRAGEN"

    def test_vorhandenes_lieferdatum_wird_nicht_ueberschrieben(self, client):
        o = _bestaetigt(client, _kunde(client))
        ls = _lieferschein(client, o)
        assert _status(client, o, "GELIEFERT").status_code == 200
        gestern = date.today() - timedelta(days=1)
        assert _quittieren(client, ls, actual_delivery_date=gestern.isoformat()).status_code == 200
        assert _lesen(client, o)["actual_delivery_date"] == _heute().isoformat()

    def test_bestandsfehler_laesst_lieferschein_offen(self, client, monkeypatch):
        """Gegenstück zu test_bestandsfehler_rollt_alles_zurueck: scheitert der
        Bestandsabzug, bleiben Lieferschein und Bestellung unverändert."""
        def kaputt(*a, **k):
            raise RuntimeError("Lager gesperrt")
        monkeypatch.setattr("app.services.order_status_service.deduct_inventory_for_order", kaputt)
        o = _bestaetigt(client, _kunde(client))
        ls = _lieferschein(client, o)
        r = _quittieren(client, ls, signed_by="Fahrer")
        assert r.status_code == 500
        assert "Lager gesperrt" in r.json()["detail"]
        assert _lesen(client, o)["status"] == "BESTAETIGT"
        assert _lesen(client, o)["actual_delivery_date"] is None
        noten = client.get(f"/api/v1/sales/orders/{o['id']}/delivery-notes").json()
        assert (noten[0]["status"], noten[0]["signed_by"]) == ("ENTWURF", None)
        assert _audit(client, o)[0]["action"] == "CONFIRM"


# --------------------- Task 3: Sammel-Endpunkt, gleiche Regel, alle oder keine

class TestSammelStatus:
    """LÜCKEN 3: POST /orders/bulk-status prüfte nichts, buchte keinen Bestand
    und scheiterte an seinem Antwortschema (500 bei jedem Aufruf)."""

    def _sammel(self, client, orders, status):
        return client.post("/api/v1/sales/orders/bulk-status", json={
            "order_ids": [o["id"] for o in orders], "status": status,
        })

    def test_bestaetigt_und_gepackt_auf_geliefert(self, client):
        kunde = _kunde(client)
        a, b = _bestaetigt(client, kunde), _gepackt(client, kunde)
        r = self._sammel(client, [a, b], "GELIEFERT")
        assert r.status_code == 200, r.text
        assert sorted(x["order_number"] for x in r.json()) == sorted([a["order_number"], b["order_number"]])
        for o in (a, b):
            bestellung = _lesen(client, o)
            assert bestellung["status"] == "GELIEFERT"
            assert bestellung["actual_delivery_date"] == _heute().isoformat()
            assert _audit(client, o)[0]["action"] == "BULK_STATUS_CHANGE"

    def test_ein_unzulaessiger_aendert_nichts(self, client):
        kunde = _kunde(client)
        ok, entwurf = _bestaetigt(client, kunde), _bestellung(client, kunde)
        r = self._sammel(client, [ok, entwurf], "GELIEFERT")
        assert r.status_code == 400
        assert entwurf["order_number"] in r.json()["detail"]
        assert "Entwurf" in r.json()["detail"]
        assert _lesen(client, ok)["status"] == "BESTAETIGT"

    def test_bucht_bestand_fuer_jede_bestellung(self, client):
        produkt = _produkt(client)
        lager = _fertigware(produkt, 1000)
        kunde = _kunde(client)
        a = _bestaetigt(client, kunde, lines=_grammzeile(produkt, 100))
        b = _gepackt(client, kunde, lines=_grammzeile(produkt, 100))
        assert self._sammel(client, [a, b], "GELIEFERT").status_code == 200
        assert _bestand(lager) == Decimal("800")

    def test_bestandsfehler_aendert_keine(self, client, monkeypatch):
        def kaputt(*a, **k):
            raise RuntimeError("Lager gesperrt")
        monkeypatch.setattr("app.services.order_status_service.deduct_inventory_for_order", kaputt)
        kunde = _kunde(client)
        a, b = _bestaetigt(client, kunde), _bestaetigt(client, kunde)
        assert self._sammel(client, [a, b], "GELIEFERT").status_code == 500
        assert {_lesen(client, a)["status"], _lesen(client, b)["status"]} == {"BESTAETIGT"}

    def test_gepackt_per_sammelaktion(self, client):
        kunde = _kunde(client)
        a, b = _bestaetigt(client, kunde), _bestaetigt(client, kunde)
        r = self._sammel(client, [a, b], "IN_PRODUKTION")
        assert r.status_code == 200, r.text
        assert {x["status"] for x in r.json()} == {"IN_PRODUKTION"}

    def test_leere_auswahl_abgelehnt(self, client):
        r = client.post("/api/v1/sales/orders/bulk-status", json={"order_ids": [], "status": "GELIEFERT"})
        assert r.status_code == 422

    def test_unbekannte_bestellung_404(self, client):
        """Charakterisierung — war schon so."""
        r = client.post("/api/v1/sales/orders/bulk-status", json={
            "order_ids": [str(uuid.uuid4())], "status": "GELIEFERT",
        })
        assert r.status_code == 404


# ------------------ Task 4: Tagesplan zeigt Gelieferte, Status als Enum-Wert

class TestTagesplanAusliefern:
    """A1: GELIEFERT verschwand aus 'Ausliefern'; Status kam gemischt
    ('Entwurf' übersetzt, alles andere roh)."""

    def test_gelieferte_bleibt_in_ausliefern(self, client):
        o = _bestaetigt(client, _kunde(client))  # Same-Day: verpacken + ausliefern
        assert _status(client, o, "GELIEFERT").status_code == 200
        plan = _plan(client)
        assert [(x["order_id"], x["status"]) for x in plan["ausliefern"]] == [(o["id"], "GELIEFERT")]
        assert plan["verpacken"] == []

    def test_fakturierte_bleibt_in_ausliefern(self, client):
        o = _bestaetigt(client, _kunde(client))
        _status(client, o, "GELIEFERT")
        assert _status(client, o, "FAKTURIERT").status_code == 200
        assert [x["status"] for x in _plan(client)["ausliefern"]] == ["FAKTURIERT"]

    def test_status_kommt_als_enum_wert(self, client):
        kunde = _kunde(client)
        _bestellung(client, kunde)
        _gepackt(client, kunde)
        stati = sorted(x["status"] for x in _plan(client)["ausliefern"])
        assert stati == ["ENTWURF", "IN_PRODUKTION"]

    def test_packaging_plan_status_als_enum_wert(self, client):
        _bestellung(client, _kunde(client), liefertag=date.today() + timedelta(days=1))
        r = client.get("/api/v1/production/packaging-plan",
                       params={"target_date": date.today().isoformat()})
        assert r.json()["items"][0]["orders"][0]["status"] == "ENTWURF"

    def test_stornierte_nicht_im_tagesplan(self, client):
        """Charakterisierung — war schon so."""
        o = _bestaetigt(client, _kunde(client))
        _status(client, o, "STORNIERT")
        plan = _plan(client)
        assert plan["ausliefern"] == [] and plan["verpacken"] == []


# --------------------------- Task 5: Fehlertexte mit Bezeichnung

class TestFehlertexte:
    """Fehlertexte landen als Toast beim Anwender — keine Enum-Werte."""

    def test_bestaetigen(self, client):
        o = _bestaetigt(client, _kunde(client))
        r = client.post(f"/api/v1/sales/orders/{o['id']}/confirm")
        assert r.status_code == 400
        assert r.json()["detail"] == "Bestellung hat Status Bestätigt, kann nicht bestätigt werden"

    def test_loeschen(self, client):
        o = _bestaetigt(client, _kunde(client))
        r = client.delete(f"/api/v1/sales/orders/{o['id']}")
        assert r.status_code == 400
        assert r.json()["detail"].endswith("Diese Bestellung hat Status Bestätigt")

    def test_position_bei_gepackt(self, client):
        o = _gepackt(client, _kunde(client))
        r = client.post(f"/api/v1/sales/orders/{o['id']}/lines", json={
            "product_name": "Kresse", "quantity": 1, "unit": "STK",
            "unit_price": 2.0, "tax_rate": "REDUZIERT",
        })
        assert r.status_code == 400
        assert r.json()["detail"] == "Positionen können nicht hinzugefügt werden bei Status Gepackt"

    def _vorschlag(self, client, status):
        """Produktionsvorschlag direkt über das ORM (Vorbild test_import_chargen.py)."""
        from app.models.forecast import Forecast, ProductionSuggestion, SuggestionStatus
        r = client.post("/api/v1/seeds", json={
            "name": "Rettich", "keimdauer_tage": 2, "wachstumsdauer_tage": 8,
            "erntefenster_min_tage": 9, "erntefenster_optimal_tage": 11,
            "erntefenster_max_tage": 14, "ertrag_gramm_pro_tray": 350,
        })
        assert r.status_code == 201, r.text
        seed_id = uuid.UUID(r.json()["id"])
        with TestingSessionLocal() as db:
            forecast = Forecast(seed_id=seed_id, datum=date.today(), horizont_tage=7,
                                prognostizierte_menge=100, effektive_menge=100, modell_typ="MANUAL")
            db.add(forecast)
            db.flush()
            vorschlag = ProductionSuggestion(
                forecast_id=forecast.id, seed_id=seed_id, empfohlene_trays=2,
                aussaat_datum=date.today(), erwartete_ernte_datum=date.today() + timedelta(days=10),
                status=SuggestionStatus(status),
            )
            db.add(vorschlag)
            db.commit()
            return str(vorschlag.id)

    def test_vorschlag_genehmigen(self, client):
        vid = self._vorschlag(client, "GENEHMIGT")
        r = client.post(f"/api/v1/forecasting/production-suggestions/{vid}/approve", json={})
        assert r.status_code == 400
        assert r.json()["detail"] == "Vorschlag hat Status Genehmigt, kann nicht genehmigt werden"

    def test_vorschlag_ablehnen(self, client):
        vid = self._vorschlag(client, "UMGESETZT")
        r = client.post(f"/api/v1/forecasting/production-suggestions/{vid}/reject",
                        json={"grund": "Zu viel Ware im Lager"})
        assert r.status_code == 400
        assert r.json()["detail"] == "Vorschlag hat Status Umgesetzt, kann nicht abgelehnt werden"


# ===========================================================================
# P2 / A4 — Knopf "Gepackt" im Tagesplan
#
# IN_PRODUKTION heißt in der Oberfläche "Gepackt". Gepackte Bestellungen
# fallen aus "Verpacken" und aus dem Sortenbedarf, bleiben aber in
# "Ausliefern". Kein neuer Status, keine neue Spalte.
# ===========================================================================
import uuid
from datetime import date, timedelta

import pytest

from tests.conftest import TestingSessionLocal


@pytest.fixture()
def _a4_ohne_celery():
    """Anlegen, Bestätigen und Stornieren stoßen über Celery ein Forecast-Update an.

    Ohne Redis wartet jeder dieser Aufrufe rund 20 s auf Wiederholungen. Für
    diese Tests ist das Forecast-Update ohne Belang, deshalb abgeklemmt.
    """
    from unittest.mock import patch
    with patch("app.tasks.forecast_tasks.update_forecast_from_order.delay"):
        yield


def _a4_bestellung(client, liefertag, *, bestaetigen=True, produkt="Erbsen-Schale", menge=5, **extra):
    """Bestellung mit einer Position ohne Produktstamm (Sortenbedarf-Schlüssel = Name)."""
    kunde = client.post("/api/v1/sales/customers", json={
        "name": f"Packkunde {uuid.uuid4().hex[:6]}", "typ": "GASTRO",
    })
    assert kunde.status_code == 201, kunde.text
    payload = {
        "customer_id": kunde.json()["id"],
        "requested_delivery_date": liefertag.isoformat(),
        "lines": [{"product_name": produkt, "quantity": menge, "unit": "STK",
                   "unit_price": 2.5, "tax_rate": "REDUZIERT"}],
    }
    payload.update(extra)
    r = client.post("/api/v1/sales/orders", json=payload)
    assert r.status_code == 201, r.text
    order = r.json()
    if bestaetigen:
        r = client.post(f"/api/v1/sales/orders/{order['id']}/confirm")
        assert r.status_code == 200, r.text
        order = r.json()
    return order


def _a4_status(client, order, status, reason=None):
    """Derselbe Aufruf wie der Knopf im Tagesplan (salesApi.updateOrderStatus)."""
    return client.post(f"/api/v1/sales/orders/{order['id']}/status",
                       json={"status": status, "reason": reason})


def _a4_packen(client, order):
    r = _a4_status(client, order, "IN_PRODUKTION", "Im Tagesplan als gepackt markiert")
    assert r.status_code == 200, r.text
    return r.json()


def _a4_tagesplan(client, tag):
    r = client.get("/api/v1/production/day-plan", params={"target_date": tag.isoformat()})
    assert r.status_code == 200, r.text
    return r.json()


def _a4_packplan(client, tag):
    r = client.get("/api/v1/production/packaging-plan", params={"target_date": tag.isoformat()})
    assert r.status_code == 200, r.text
    return r.json()


def _a4_nummern(zeilen):
    return sorted(z["order_number"] for z in zeilen)


@pytest.mark.usefixtures("_a4_ohne_celery")
class TestGepacktBedeutung:
    """Charakterisierung: was der Statuswechsel nach IN_PRODUKTION heute schon tut.

    Diese Tests sind von Anfang an grün. Sie halten fest, worauf der Knopf
    "Gepackt" im Tagesplan sich verlässt.
    """

    def test_bestaetigte_bestellung_laesst_sich_packen(self, client):
        order = _a4_bestellung(client, date.today() + timedelta(days=1))
        assert _a4_packen(client, order)["status"] == "IN_PRODUKTION"

    def test_entwurf_laesst_sich_nicht_packen(self, client):
        """ENTWURF → IN_PRODUKTION bleibt verboten; der Knopf erscheint nur bei BESTAETIGT."""
        order = _a4_bestellung(client, date.today() + timedelta(days=1), bestaetigen=False)
        r = _a4_status(client, order, "IN_PRODUKTION")
        assert r.status_code == 400, r.text

    def test_packen_bucht_keinen_bestand(self, client):
        """Bestand wird erst bei GELIEFERT gebucht, nicht beim Packen."""
        from app.models.order import Order
        order = _a4_bestellung(client, date.today() + timedelta(days=1))
        _a4_packen(client, order)
        with TestingSessionLocal() as db:
            o = db.get(Order, uuid.UUID(order["id"]))
            assert o.inventory_deducted_at is None
            assert o.actual_delivery_date is None

    def test_packen_steht_im_audit_log(self, client):
        order = _a4_bestellung(client, date.today() + timedelta(days=1))
        _a4_packen(client, order)
        log = client.get(f"/api/v1/sales/orders/{order['id']}/audit-log").json()
        eintrag = [e for e in log if e["action"] == "STATUS_CHANGE"]
        assert eintrag and eintrag[0]["new_values"] == {"status": "IN_PRODUKTION"}
        assert eintrag[0]["reason"] == "Im Tagesplan als gepackt markiert"

    def test_gepackte_bestellung_bleibt_offen(self, client):
        """Der Sammelfilter OFFEN zählt IN_PRODUKTION weiter mit — richtig, gepackt
        ist nicht geliefert. (Das Kreditlimit, sales.py:840-842, nutzt dieselbe
        Statusliste; am Code geprüft, hier nicht getestet.)"""
        order = _a4_bestellung(client, date.today() + timedelta(days=1))
        _a4_packen(client, order)
        r = client.get("/api/v1/sales/orders", params={"status": "OFFEN"})
        assert r.status_code == 200, r.text
        assert [o["order_number"] for o in r.json()["items"]] == [order["order_number"]]

    def test_halle_darf_packen(self, client):
        """Der Knopf sitzt auf dem Hallen-Tablet: production_staff muss durchkommen."""
        from tests.test_rollen import _als, ALLE_ROLLEN
        order = _a4_bestellung(client, date.today() + timedelta(days=1))
        _als(["production_staff"])
        try:
            r = _a4_status(client, order, "IN_PRODUKTION")
        finally:
            _als(ALLE_ROLLEN)
        assert r.status_code == 200, r.text

    def test_gepackte_bestellung_laesst_sich_stornieren(self, client):
        """Vertragstest zu P1 (Übergangstabelle): gepackt, aber nicht geliefert → stornierbar.

        Grün, sobald P1 IN_PRODUKTION → STORNIERT erlaubt. Rot heißt: P1 fehlt.
        Die Oberfläche (EditOrderModal) prüft Step 0 und die Abnahme, nicht dieser Test.
        """
        morgen = date.today() + timedelta(days=1)
        order = _a4_bestellung(client, morgen)
        _a4_packen(client, order)
        r = _a4_status(client, order, "STORNIERT", "Kunde hat abgesagt")
        assert r.status_code == 200, r.text
        assert _a4_tagesplan(client, morgen)["ausliefern"] == []


@pytest.mark.usefixtures("_a4_ohne_celery")
class TestTagesplanGepackt:
    """A4: gepackte Bestellungen raus aus "Verpacken", drin in "Ausliefern"."""

    def test_gepackte_faellt_aus_verpacken(self, client):
        heute, morgen = date.today(), date.today() + timedelta(days=1)
        offen = _a4_bestellung(client, morgen)
        gepackt = _a4_bestellung(client, morgen)
        _a4_packen(client, gepackt)

        plan = _a4_tagesplan(client, heute)
        assert _a4_nummern(plan["verpacken"]) == [offen["order_number"]]
        assert _a4_nummern(plan["verpacken_erledigt"]) == [gepackt["order_number"]]

    def test_gepackte_bleibt_in_ausliefern(self, client):
        morgen = date.today() + timedelta(days=1)
        offen = _a4_bestellung(client, morgen)
        gepackt = _a4_bestellung(client, morgen)
        _a4_packen(client, gepackt)

        plan = _a4_tagesplan(client, morgen)
        assert _a4_nummern(plan["ausliefern"]) == sorted([offen["order_number"], gepackt["order_number"]])

    def test_same_day_gepackt(self, client):
        """Same-Day: Pack- und Liefertag sind derselbe Tag. Nach dem Packen nur noch
        unter Ausliefern (vgl. test_gernot_260817.py::test_same_day_bestellung_wird_heute_verpackt)."""
        heute = date.today()
        order = _a4_bestellung(client, heute)
        _a4_packen(client, order)

        plan = _a4_tagesplan(client, heute)
        assert plan["verpacken"] == []
        assert _a4_nummern(plan["verpacken_erledigt"]) == [order["order_number"]]
        assert _a4_nummern(plan["ausliefern"]) == [order["order_number"]]

    def test_packbar_nur_wenn_bestaetigt(self, client):
        """Der Knopf "Gepackt" braucht BESTAETIGT; ein Entwurf muss erst bestätigt werden."""
        morgen = date.today() + timedelta(days=1)
        entwurf = _a4_bestellung(client, morgen, bestaetigen=False)
        bestaetigt = _a4_bestellung(client, morgen)

        zeilen = {z["order_number"]: z for z in _a4_tagesplan(client, date.today())["verpacken"]}
        assert zeilen[entwurf["order_number"]]["packbar"] is False
        assert zeilen[bestaetigt["order_number"]]["packbar"] is True

    def test_expliziter_packtag_gepackt(self, client):
        """Abweichender Packtag: gepackt fällt auch dort aus Verpacken."""
        heute = date.today()
        order = _a4_bestellung(client, heute + timedelta(days=3), packing_date=heute.isoformat())
        _a4_packen(client, order)

        plan = _a4_tagesplan(client, heute)
        assert plan["verpacken"] == []
        assert _a4_nummern(plan["verpacken_erledigt"]) == [order["order_number"]]

    def test_gelieferte_und_fakturierte_gelten_als_erledigt(self, client):
        """P1 (Task 4) lädt GELIEFERT und FAKTURIERT für "Ausliefern" mit. Am
        Packtag stehen sie unter "Bereits gepackt", nie unter "Verpacken"."""
        heute = date.today()
        geliefert = _a4_bestellung(client, heute)
        fakturiert = _a4_bestellung(client, heute)
        for order in (geliefert, fakturiert):
            _a4_packen(client, order)
            r = _a4_status(client, order, "GELIEFERT")
            assert r.status_code == 200, r.text
        r = _a4_status(client, fakturiert, "FAKTURIERT")
        assert r.status_code == 200, r.text

        plan = _a4_tagesplan(client, heute)
        assert plan["verpacken"] == []
        assert _a4_nummern(plan["verpacken_erledigt"]) == sorted(
            [geliefert["order_number"], fakturiert["order_number"]])


@pytest.mark.usefixtures("_a4_ohne_celery")
class TestSortenbedarfGepackt:
    """A4: Sortenbedarf und Packliste zählen nur, was noch zu packen ist."""

    def test_gepackte_zaehlt_nicht_im_sortenbedarf(self, client):
        heute, morgen = date.today(), date.today() + timedelta(days=1)
        _a4_bestellung(client, morgen, menge=3)
        gepackt = _a4_bestellung(client, morgen, menge=5)
        _a4_packen(client, gepackt)

        plan = _a4_packplan(client, heute)
        bedarf = {k["product_name"]: k["total_quantity"] for k in plan["komponenten"]}
        assert bedarf == {"Erbsen-Schale": 3}

    def test_gepackte_zaehlt_nicht_in_der_packliste(self, client):
        """`items` speist den Tab Verpackungsplan auf der Produktionsseite."""
        heute, morgen = date.today(), date.today() + timedelta(days=1)
        offen = _a4_bestellung(client, morgen, menge=3)
        gepackt = _a4_bestellung(client, morgen, menge=5)
        _a4_packen(client, gepackt)

        items = _a4_packplan(client, heute)["items"]
        assert len(items) == 1
        assert items[0]["total_quantity"] == 3
        assert [o["order_number"] for o in items[0]["orders"]] == [offen["order_number"]]

    def test_gepackte_werden_benannt(self, client):
        """Niemand soll eine Bestellung suchen müssen, die schon im Karton liegt."""
        heute, morgen = date.today(), date.today() + timedelta(days=1)
        gepackt = _a4_bestellung(client, morgen)
        _a4_packen(client, gepackt)

        plan = _a4_packplan(client, heute)
        assert plan["komponenten"] == []
        assert plan["items"] == []
        assert [g["order_number"] for g in plan["gepackt"]] == [gepackt["order_number"]]
        assert plan["gepackt"][0]["order_id"] == gepackt["id"]
        assert plan["gepackt"][0]["delivery_date"] == morgen.isoformat()

    def test_bestaetigte_und_entwuerfe_zaehlen_weiter(self, client):
        """Charakterisierung: ohne Packmarke bleibt alles im Bedarf, auch Entwürfe."""
        heute, morgen = date.today(), date.today() + timedelta(days=1)
        _a4_bestellung(client, morgen, menge=3)
        _a4_bestellung(client, morgen, menge=4, bestaetigen=False)

        bedarf = {k["product_name"]: k["total_quantity"] for k in _a4_packplan(client, heute)["komponenten"]}
        assert bedarf == {"Erbsen-Schale": 7}

    def test_gelieferte_zaehlt_nicht(self, client):
        """Charakterisierung: GELIEFERT war schon vorher ausgeschlossen und bleibt es."""
        heute, morgen = date.today(), date.today() + timedelta(days=1)
        order = _a4_bestellung(client, morgen)
        _a4_packen(client, order)
        r = _a4_status(client, order, "GELIEFERT")
        assert r.status_code == 200, r.text

        plan = _a4_packplan(client, heute)
        assert plan["komponenten"] == []
        assert plan["items"] == []


# ===========================================================================
# P3 / A2 — Kunde in Rechnungsliste, Detail und "Überfällig"
#
# InvoiceResponse kannte customer_name/customer_number seit dem Initial
# Commit, das Invoice-Modell nicht — die Felder kamen immer als null.
# ===========================================================================
from datetime import date, timedelta


def _a2_kunde(client, name="Gasthof Zur Post", nummer="K-A2-001"):
    r = client.post("/api/v1/sales/customers", json={
        "name": name, "typ": "GASTRO", "customer_number": nummer,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _a2_entwurf(client, kunde, *, rechnungsdatum=None, faellig=None):
    """Rechnungsentwurf mit einer Position, Satz ausdrücklich gesetzt."""
    body = {
        "customer_id": kunde["id"],
        "invoice_date": (rechnungsdatum or date.today()).isoformat(),
        "lines": [{
            "description": "Erbse 100 g", "quantity": "2", "unit": "STUECK",
            "unit_price": "3.50", "tax_rate": "REDUZIERT",
        }],
    }
    if faellig is not None:
        body["due_date"] = faellig.isoformat()
    r = client.post("/api/v1/invoices", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _a2_rechnung(client, kunde, *, ueberfaellig=False):
    """Finalisierte (OFFEN) Rechnung; ueberfaellig=True → Zahlungsziel gestern."""
    heute = date.today()
    if ueberfaellig:
        entwurf = _a2_entwurf(client, kunde, rechnungsdatum=heute - timedelta(days=30),
                              faellig=heute - timedelta(days=1))
    else:
        entwurf = _a2_entwurf(client, kunde, faellig=heute + timedelta(days=14))
    r = client.post(f"/api/v1/invoices/{entwurf['id']}/finalize")
    assert r.status_code == 200, r.text
    if ueberfaellig:
        # Seit Paket 3 (Q1) setzt das Finalisieren Rechnungsdatum (heute) und
        # Fälligkeit neu. Überfällig wird die Rechnung wie ein Altbestand:
        # die Daten an der ausgestellten Rechnung zurücksetzen.
        from app.models.invoice import Invoice
        with TestingSessionLocal() as db:
            inv = db.get(Invoice, uuid.UUID(entwurf["id"]))
            inv.invoice_date = heute - timedelta(days=30)
            inv.due_date = heute - timedelta(days=1)
            db.commit()
        return client.get(f"/api/v1/invoices/{entwurf['id']}").json()
    return r.json()


def _a2_liste(r):
    """Zeilen aus GET /invoices bzw. /invoices/overdue.

    Heute eine nackte Liste (api.ts: api.get<Invoice[]>). Stellt Paket 1 die
    Rechnungsliste auf {"items": [...], ...} um, greift der zweite Zweig.
    """
    assert r.status_code == 200, r.text
    daten = r.json()
    return daten["items"] if isinstance(daten, dict) else daten


def _a2_zeile(rows, invoice_id):
    treffer = [r for r in rows if r["id"] == invoice_id]
    assert len(treffer) == 1, f"Rechnung {invoice_id} nicht in der Antwort"
    return treffer[0]


class TestRechnungZeigtKunde:
    """A2: Spalte "Kunde" war in Liste, Detail und "Überfällig" leer."""

    def test_liste(self, client):
        kunde = _a2_kunde(client)
        rechnung = _a2_rechnung(client, kunde)

        zeile = _a2_zeile(_a2_liste(client.get("/api/v1/invoices")), rechnung["id"])
        assert zeile["customer_name"] == "Gasthof Zur Post"
        assert zeile["customer_number"] == "K-A2-001"

    def test_liste_mit_statusfilter_wie_dashboard(self, client):
        """Dashboard.tsx fragt GET /invoices?status=OFFEN ab."""
        kunde = _a2_kunde(client)
        rechnung = _a2_rechnung(client, kunde)

        rows = _a2_liste(client.get("/api/v1/invoices", params={"status": "OFFEN"}))
        assert _a2_zeile(rows, rechnung["id"])["customer_name"] == "Gasthof Zur Post"

    def test_detail(self, client):
        kunde = _a2_kunde(client)
        rechnung = _a2_rechnung(client, kunde)

        r = client.get(f"/api/v1/invoices/{rechnung['id']}")
        assert r.status_code == 200, r.text
        assert r.json()["customer_name"] == "Gasthof Zur Post"
        assert r.json()["customer_number"] == "K-A2-001"

    def test_ueberfaellig(self, client):
        kunde = _a2_kunde(client)
        rechnung = _a2_rechnung(client, kunde, ueberfaellig=True)

        zeile = _a2_zeile(_a2_liste(client.get("/api/v1/invoices/overdue")), rechnung["id"])
        assert zeile["status"] == "UEBERFAELLIG"
        assert zeile["customer_name"] == "Gasthof Zur Post"
        assert zeile["customer_number"] == "K-A2-001"

    def test_ueberfaellig_zweiter_aufruf(self, client):
        """Beim zweiten Aufruf steht die Rechnung schon auf UEBERFAELLIG — Kunde bleibt."""
        kunde = _a2_kunde(client)
        rechnung = _a2_rechnung(client, kunde, ueberfaellig=True)
        client.get("/api/v1/invoices/overdue")

        rows = _a2_liste(client.get("/api/v1/invoices/overdue"))
        assert _a2_zeile(rows, rechnung["id"])["customer_name"] == "Gasthof Zur Post"

    def test_schreibende_endpunkte(self, client):
        """Anlegen, Kopfdaten ändern, Finalisieren und Storno liefern den Kunden mit."""
        alt = _a2_kunde(client)
        neu = _a2_kunde(client, name="Fruchthof Nagel", nummer="K-A2-002")

        entwurf = _a2_entwurf(client, alt, faellig=date.today() + timedelta(days=14))
        assert entwurf["customer_name"] == "Gasthof Zur Post"

        r = client.patch(f"/api/v1/invoices/{entwurf['id']}", json={"customer_id": neu["id"]})
        assert r.status_code == 200, r.text
        assert r.json()["customer_name"] == "Fruchthof Nagel"
        assert r.json()["customer_number"] == "K-A2-002"

        r = client.post(f"/api/v1/invoices/{entwurf['id']}/finalize")
        assert r.status_code == 200, r.text
        assert r.json()["customer_name"] == "Fruchthof Nagel"

        r = client.post(f"/api/v1/invoices/{entwurf['id']}/cancel", json={
            "reason": "Test", "reason_code": "SONSTIGES", "create_credit_note": True,
        })
        assert r.status_code == 200, r.text
        assert r.json()["invoice"]["customer_name"] == "Fruchthof Nagel"
        assert r.json()["credit_note"]["customer_name"] == "Fruchthof Nagel"


# --- P3 / A2: keine Kundenabfrage je Zeile (N+1) ---
from contextlib import contextmanager

from sqlalchemy import event

from tests.conftest import engine as _a2_engine


@contextmanager
def _a2_selects():
    """Zählt SELECT-Anweisungen auf der Test-Engine während des Blocks."""
    zaehler = {"n": 0}

    def _mitzaehlen(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            zaehler["n"] += 1

    event.listen(_a2_engine, "before_cursor_execute", _mitzaehlen)
    try:
        yield zaehler
    finally:
        event.remove(_a2_engine, "before_cursor_execute", _mitzaehlen)


class TestRechnungslistenOhneNPlusEins:
    """Der Kundenname darf nicht pro Zeile eine eigene Abfrage kosten."""

    def _selects(self, client, url):
        with _a2_selects() as z:
            r = client.get(url)
        return z["n"], _a2_liste(r)

    def test_liste(self, client):
        _a2_rechnung(client, _a2_kunde(client, "Kunde 0", "K-A2-100"))
        einer, rows = self._selects(client, "/api/v1/invoices")
        assert len(rows) == 1

        for i in range(1, 4):
            _a2_rechnung(client, _a2_kunde(client, f"Kunde {i}", f"K-A2-10{i}"))
        vier, rows = self._selects(client, "/api/v1/invoices")
        assert len(rows) == 4
        assert {r["customer_name"] for r in rows} == {f"Kunde {i}" for i in range(4)}

        assert vier == einer, f"{einer} SELECTs bei 1 Rechnung, {vier} bei 4 — N+1"

    def test_ueberfaellig(self, client):
        _a2_rechnung(client, _a2_kunde(client, "Kunde 0", "K-A2-100"), ueberfaellig=True)
        einer, rows = self._selects(client, "/api/v1/invoices/overdue")
        assert len(rows) == 1

        for i in range(1, 4):
            _a2_rechnung(client, _a2_kunde(client, f"Kunde {i}", f"K-A2-10{i}"), ueberfaellig=True)
        vier, rows = self._selects(client, "/api/v1/invoices/overdue")
        assert len(rows) == 4
        assert {r["customer_name"] for r in rows} == {f"Kunde {i}" for i in range(4)}

        assert vier == einer, f"{einer} SELECTs bei 1 Rechnung, {vier} bei 4 — N+1"


# ============================================================
# P4 — Abo-Bestellungen (A5)
#
# Der Abo-Lauf suchte das Produkt nur über seed_id. Produkt-Abos haben
# seed_id = None, daraus wurde WHERE products.seed_id IS NULL: Preis und
# Steuersatz irgendeines Produkts ohne Sorte, Text "Abo-Lieferung: Unknown"
# (LfA Förderbank Bayern, vier Entwürfe ab 14.09.2026, je 2,00 EUR).
# Die Fälligkeit prüfte zusätzlich den Abstand zu gueltig_von in ganzen
# Wochen: mehrere Liefertage wirkten nicht. Alle P4-Helfer tragen das
# Präfix _p4_, damit andere Abschnitte in dieselbe Datei schreiben können.
# ============================================================
import uuid
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests.conftest import TestingSessionLocal

_P4_MO = date(2026, 10, 5)   # Montag
_P4_MI = date(2026, 10, 7)   # Mittwoch
_P4_DO = date(2026, 10, 8)   # Donnerstag


def _p4_einheit(code="STK", name="Stück"):
    from app.models.unit import UnitOfMeasure, UnitCategory
    with TestingSessionLocal() as db:
        unit = db.query(UnitOfMeasure).filter_by(code=code).first()
        if unit is None:
            unit = UnitOfMeasure(code=code, name=name, category=UnitCategory.COUNT)
            db.add(unit)
            db.commit()
        return str(unit.id)


def _p4_produkt(client, name, sku, preis, **extra):
    r = client.post("/api/v1/products", json={
        "name": name, "sku": sku, "base_price": str(preis),
        "category": "MICROGREEN", "base_unit_id": _p4_einheit(), **extra,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _p4_kunde(client, name="LfA Förderbank Bayern"):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "GEWERBE"})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _p4_abo(client, kunde, gueltig_von=_P4_MO, **felder):
    body = {
        "kunde_id": kunde["id"], "menge": 2, "einheit": "STUECK",
        "intervall": "WOECHENTLICH", "liefertage": [0],
        "gueltig_von": gueltig_von.isoformat(), **felder,
    }
    r = client.post("/api/v1/sales/subscriptions", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _p4_bestellungen(abo_id=None):
    """Alle Bestellungen (optional nur die eines Abos) mit ihren Positionen."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.order import Order
    with TestingSessionLocal() as db:
        q = select(Order).options(selectinload(Order.lines)).order_by(Order.order_number)
        if abo_id:
            q = q.where(Order.notes.contains(f"Abo {abo_id}"))
        return [
            {
                "order_number": o.order_number,
                "status": o.status.value,
                "requested_delivery_date": o.requested_delivery_date,
                "total_net": o.total_net, "total_vat": o.total_vat, "total_gross": o.total_gross,
                "lines": [
                    {
                        "product_id": str(l.product_id) if l.product_id else None,
                        "product_variant_id": str(l.product_variant_id) if l.product_variant_id else None,
                        "beschreibung": l.beschreibung, "unit": l.unit,
                        "quantity": l.quantity, "unit_price": l.unit_price,
                        "tax_rate": l.tax_rate.value, "line_net": l.line_net,
                    }
                    for l in o.lines
                ],
            }
            for o in db.execute(q).scalars().all()
        ]


def _p4_anlegen(abo_id, heute=_P4_DO):
    """Legt die Abo-Bestellung an wie der Lauf, ohne Fälligkeitsprüfung."""
    from app.models.customer import Subscription
    from app.tasks.subscription_tasks import _create_order_from_subscription
    with TestingSessionLocal() as db:
        sub = db.get(Subscription, uuid.UUID(abo_id))
        _create_order_from_subscription(db, sub, heute)
        db.commit()


def _p4_lauf(heute):
    """Der echte Lauf (Scheduler bzw. "Heute verarbeiten") gegen die Test-DB."""
    from app.tasks.subscription_tasks import process_daily_subscriptions
    with patch("app.tasks.subscription_tasks.SessionLocal", TestingSessionLocal):
        return process_daily_subscriptions(heute=heute)


def _p4_sub(intervall, liefertage, gueltig_von, gueltig_bis=None, aktiv=True):
    """Abo nur mit den Feldern, die die Fälligkeit liest."""
    from app.models.customer import SubscriptionInterval
    return SimpleNamespace(
        aktiv=aktiv, intervall=SubscriptionInterval(intervall), liefertage=liefertage,
        gueltig_von=gueltig_von, gueltig_bis=gueltig_bis,
    )


def _p4_faellige_tage(sub, von, bis):
    from app.tasks.subscription_tasks import ist_faellig
    tage, tag = [], von
    while tag <= bis:
        if ist_faellig(sub, tag):
            tage.append(tag)
        tag += timedelta(days=1)
    return tage

class TestP4Faelligkeit:
    """A5: Mehrere Liefertage wirkten nicht; ein gueltig_von an einem
    Nicht-Liefertag hieß: nie liefern."""

    def test_woechentlich_mo_und_do_liefert_an_beiden_tagen(self):
        sub = _p4_sub("WOECHENTLICH", [0, 3], _P4_MO)
        assert _p4_faellige_tage(sub, _P4_MO, date(2026, 10, 18)) == [
            date(2026, 10, 5), date(2026, 10, 8), date(2026, 10, 12), date(2026, 10, 15),
        ]

    def test_woechentlich_start_an_einem_nicht_liefertag(self):
        """Das Formular setzt gueltig_von = heute. Am Mittwoch angelegt, montags geliefert."""
        sub = _p4_sub("WOECHENTLICH", [0], _P4_MI)
        assert _p4_faellige_tage(sub, _P4_MI, date(2026, 10, 25)) == [
            date(2026, 10, 12), date(2026, 10, 19),
        ]

    def test_zweiwoechentlich_zaehlt_kalenderwochen_ab_erster_lieferung(self):
        sub = _p4_sub("ZWEIWOECHENTLICH", [0, 3], _P4_MI)
        assert _p4_faellige_tage(sub, _P4_MI, date(2026, 10, 25)) == [
            date(2026, 10, 8), date(2026, 10, 19), date(2026, 10, 22),
        ]

    def test_monatlich_mit_liefertag_erster_montag_ab_stichtag(self):
        sub = _p4_sub("MONATLICH", [0], date(2026, 10, 15))
        assert _p4_faellige_tage(sub, date(2026, 10, 15), date(2026, 12, 31)) == [
            date(2026, 10, 19), date(2026, 11, 16), date(2026, 12, 21),
        ]

    def test_monatlich_ohne_liefertag_kappt_auf_monatsende(self):
        sub = _p4_sub("MONATLICH", None, date(2026, 8, 31))
        assert _p4_faellige_tage(sub, date(2026, 8, 31), date(2026, 11, 30)) == [
            date(2026, 8, 31), date(2026, 9, 30), date(2026, 10, 31), date(2026, 11, 30),
        ]

    def test_bisheriges_verhalten_bleibt(self):
        """Absicherung: Fälle, die schon vorher stimmten."""
        taeglich = _p4_sub("TAEGLICH", [0, 1, 2, 3, 4], _P4_MO)
        assert len(_p4_faellige_tage(taeglich, _P4_MO, date(2026, 10, 18))) == 10
        ohne_tage = _p4_sub("WOECHENTLICH", None, _P4_MI)
        assert _p4_faellige_tage(ohne_tage, _P4_MI, date(2026, 10, 21)) == [
            date(2026, 10, 7), date(2026, 10, 14), date(2026, 10, 21),
        ]
        beendet = _p4_sub("WOECHENTLICH", [0], _P4_MO, gueltig_bis=date(2026, 10, 11))
        assert _p4_faellige_tage(beendet, _P4_MO, date(2026, 10, 25)) == [date(2026, 10, 5)]
        pausiert = _p4_sub("WOECHENTLICH", [0], _P4_MO, aktiv=False)
        assert _p4_faellige_tage(pausiert, _P4_MO, date(2026, 10, 25)) == []

    def test_lauf_am_donnerstag_beliefert_mo_do_abo(self, client):
        kunde = _p4_kunde(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50")
        abo = _p4_abo(client, kunde, product_id=produkt["id"], liefertage=[0, 3])

        _p4_lauf(_P4_DO)

        bestellungen = _p4_bestellungen(abo["id"])
        assert len(bestellungen) == 1
        assert bestellungen[0]["requested_delivery_date"] == _P4_DO
        assert bestellungen[0]["status"] == "ENTWURF"


class TestP4AboRechnungstask:
    """A5: Der nie eingeplante Abo-Rechnungstask rechnete fest 0,08 EUR und 7 %."""

    def test_abo_rechnungstask_ist_entfernt(self):
        import app.tasks.invoice_tasks as invoice_tasks
        assert not hasattr(invoice_tasks, "generate_recurring_invoices")


class TestP4AboPosition:
    """A5: Position aus Produkt bzw. Variante, mit Kundenpreis und Produktsatz."""

    def _koeder(self, client):
        """Wie in Produktion: ein Produkt ohne Sorte, das der alte Lauf griff."""
        return _p4_produkt(client, "Mehrwegkiste leer", "P4-KOEDER", "2.00")

    def test_produkt_abo_bekommt_produkt_preis_satz_und_einheit(self, client):
        kunde = _p4_kunde(client)
        self._koeder(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50",
                              tax_rate="STANDARD")
        abo = _p4_abo(client, kunde, product_id=produkt["id"], einheit="KISTE_6")

        _p4_anlegen(abo["id"])

        [bestellung] = _p4_bestellungen(abo["id"])
        [zeile] = bestellung["lines"]
        # Vorher: ("Abo-Lieferung: Unknown", 2,00, REDUZIERT) vom Köder-Produkt
        assert (zeile["beschreibung"], zeile["unit_price"], zeile["tax_rate"]) == (
            "BIO Snackbox | Amaranth", Decimal("4.50"), "STANDARD")
        assert zeile["product_id"] == produkt["id"]
        assert zeile["unit"] == "KISTE_6"
        assert zeile["line_net"] == Decimal("9.00")
        assert bestellung["total_vat"] == Decimal("1.71")
        assert bestellung["total_gross"] == Decimal("10.71")

    def test_sonderpreis_des_kunden_gilt(self, client):
        kunde = _p4_kunde(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50")
        r = client.post(f"/api/v1/sales/customers/{kunde['id']}/prices", json={
            "product_id": produkt["id"], "unit_price": "4.20", "valid_from": "2026-09-01",
        })
        assert r.status_code in (200, 201), r.text
        abo = _p4_abo(client, kunde, product_id=produkt["id"])

        _p4_anlegen(abo["id"])

        [bestellung] = _p4_bestellungen(abo["id"])
        assert bestellung["lines"][0]["unit_price"] == Decimal("4.20")

    def test_variante_liefert_name_einheit_und_preis(self, client):
        kunde = _p4_kunde(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50")
        r = client.post(f"/api/v1/products/{produkt['id']}/variants", json={
            "packaging_unit_id": _p4_einheit("KISTE_12", "Mehrwegkiste 12"),
            "name_suffix": "12er Mehrwegkiste", "price_override": "48.00", "items_per_pack": 12,
        })
        assert r.status_code in (200, 201), r.text
        variante = r.json()
        abo = _p4_abo(client, kunde, product_id=produkt["id"],
                      product_variant_id=variante["id"], menge=1)

        _p4_anlegen(abo["id"])

        [zeile] = _p4_bestellungen(abo["id"])[0]["lines"]
        assert zeile["product_variant_id"] == variante["id"]
        assert zeile["beschreibung"] == "BIO Snackbox | Amaranth — 12er Mehrwegkiste"
        assert zeile["unit"] == "KISTE_12"
        assert zeile["unit_price"] == Decimal("48.00")

    def test_abo_ohne_produkt_und_sorte_legt_nichts_an(self, client):
        from app.models.customer import Subscription, SubscriptionInterval
        from app.tasks.subscription_tasks import AboUebersprungen
        kunde = _p4_kunde(client)
        self._koeder(client)
        with TestingSessionLocal() as db:
            sub = Subscription(
                kunde_id=uuid.UUID(kunde["id"]), menge=Decimal("2"), einheit="STUECK",
                intervall=SubscriptionInterval.WOECHENTLICH, liefertage=[3], gueltig_von=_P4_MO,
            )
            db.add(sub)
            db.commit()
            abo_id = str(sub.id)

        with pytest.raises(AboUebersprungen):
            _p4_anlegen(abo_id)
        assert _p4_bestellungen() == []

    def test_mehrdeutige_sorte_legt_nichts_an(self, client):
        from app.tasks.subscription_tasks import AboUebersprungen
        kunde = _p4_kunde(client)
        sorte = client.post("/api/v1/seeds", json={
            "name": "Gartenkresse", "keimdauer_tage": 3, "wachstumsdauer_tage": 3,
            "erntefenster_min_tage": 6, "erntefenster_optimal_tage": 7,
            "erntefenster_max_tage": 8, "ertrag_gramm_pro_tray": 350,
        }).json()
        _p4_produkt(client, "Kresse Schale", "P4-KR-S", "3.00", seed_id=sorte["id"])
        _p4_produkt(client, "Kresse Kiste", "P4-KR-K", "30.00", seed_id=sorte["id"])
        abo = _p4_abo(client, kunde, seed_id=sorte["id"])

        with pytest.raises(AboUebersprungen):
            _p4_anlegen(abo["id"])
        assert _p4_bestellungen() == []

    def test_lauf_ueberspringt_meldet_und_beliefert_die_anderen(self, client):
        from app.models.customer import Subscription, SubscriptionInterval
        kunde = _p4_kunde(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50")
        gut = _p4_abo(client, kunde, product_id=produkt["id"], liefertage=[3])
        with TestingSessionLocal() as db:
            kaputt = Subscription(
                kunde_id=uuid.UUID(kunde["id"]), menge=Decimal("2"), einheit="STUECK",
                intervall=SubscriptionInterval.WOECHENTLICH, liefertage=[3], gueltig_von=_P4_MO,
            )
            db.add(kaputt)
            db.commit()
            kaputt_id = str(kaputt.id)

        ergebnis = _p4_lauf(_P4_DO)

        assert ergebnis["erstellt"] == 1
        assert [u["abo_id"] for u in ergebnis["uebersprungen"]] == [kaputt_id]
        assert len(_p4_bestellungen(gut["id"])) == 1
        assert _p4_bestellungen(kaputt_id) == []

    def test_sorten_abo_mit_eindeutigem_produkt(self, client):
        """Absicherung: Legacy-Abos über die Sorte liefern weiter das Produkt der Sorte."""
        kunde = _p4_kunde(client)
        sorte = client.post("/api/v1/seeds", json={
            "name": "Gartenkresse", "keimdauer_tage": 3, "wachstumsdauer_tage": 3,
            "erntefenster_min_tage": 6, "erntefenster_optimal_tage": 7,
            "erntefenster_max_tage": 8, "ertrag_gramm_pro_tray": 350,
        }).json()
        self._koeder(client)
        _p4_produkt(client, "Kresse Schale", "P4-KR-S", "3.00", seed_id=sorte["id"])
        abo = _p4_abo(client, kunde, seed_id=sorte["id"])

        _p4_anlegen(abo["id"])

        [zeile] = _p4_bestellungen(abo["id"])[0]["lines"]
        assert zeile["unit_price"] == Decimal("3.00")
        assert zeile["tax_rate"] == "REDUZIERT"

    def test_variables_bundle_wird_uebersprungen(self, client):
        """create_order lehnt ein variables Bundle ohne Sortenauswahl ab
        (sales.py, 'bitte Sorten auswählen'); ein Abo hat keine Auswahl."""
        from app.tasks.subscription_tasks import AboUebersprungen
        kunde = _p4_kunde(client)
        tray = _p4_produkt(client, "Gastrotray 4 Sorten", "P4-TRAY", "18.00")
        abo = _p4_abo(client, kunde, product_id=tray["id"])
        # Seit B6 lehnt schon das Anlegen ein variables Bundle ab; der Lauf
        # muss es trotzdem überspringen, wenn das Produkt erst danach eins wird.
        r = client.patch(f"/api/v1/products/{tray['id']}", json={
            "is_variable_bundle": True, "variable_bundle_min_slots": 4,
            "variable_bundle_max_slots": 4,
        })
        assert r.status_code == 200, r.text

        with pytest.raises(AboUebersprungen, match="variables Bundle"):
            _p4_anlegen(abo["id"])
        assert _p4_bestellungen() == []

    def test_deaktiviertes_produkt_wird_uebersprungen(self, client):
        from app.tasks.subscription_tasks import AboUebersprungen
        kunde = _p4_kunde(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50")
        abo = _p4_abo(client, kunde, product_id=produkt["id"])
        r = client.delete(f"/api/v1/products/{produkt['id']}")  # Soft-Delete: is_active = False
        assert r.status_code == 204, r.text

        with pytest.raises(AboUebersprungen, match="deaktiviert"):
            _p4_anlegen(abo["id"])
        assert _p4_bestellungen() == []


class TestP4AboLauf:
    """A5: Der Knopf "Heute verarbeiten" lief im Default-Mandanten statt im
    Mandanten der Anfrage. Läuft er richtig, treffen er und der 05:00-Lauf
    dieselbe DB: je Abo und Liefertag darf es nur eine Bestellung geben."""

    def test_zweiter_lauf_am_selben_tag_legt_nichts_doppelt_an(self, client):
        kunde = _p4_kunde(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50")
        abo = _p4_abo(client, kunde, product_id=produkt["id"], liefertage=[3])

        _p4_lauf(_P4_DO)
        zweiter = _p4_lauf(_P4_DO)

        assert len(_p4_bestellungen(abo["id"])) == 1
        assert zweiter["erstellt"] == 0
        assert zweiter["bereits_vorhanden"] == 1

    def test_stornierte_abo_bestellung_kommt_nicht_wieder(self, client):
        kunde = _p4_kunde(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50")
        abo = _p4_abo(client, kunde, product_id=produkt["id"], liefertage=[3])
        _p4_lauf(_P4_DO)
        from app.models.order import Order, OrderStatus
        from sqlalchemy import select
        with TestingSessionLocal() as db:
            order = db.execute(select(Order)).scalars().one()
            order.status = OrderStatus.STORNIERT
            db.commit()

        _p4_lauf(_P4_DO)

        assert [b["status"] for b in _p4_bestellungen(abo["id"])] == ["STORNIERT"]

    def test_knopf_nutzt_den_mandanten_der_anfrage(self, client):
        """Der Knopf muss die Session der Anfrage nehmen und meldet auf Deutsch.

        SessionLocal() fiele ohne Scheduler-Kontext auf DEFAULT_TENANT_SLUG
        zurück (database.py, _active_slug). Der Patch lässt jeden Zugriff
        scheitern, statt in TENANTS_DIR/dev.db zu schreiben. Diesen Test nie
        ohne ihn laufen lassen: backend/data/tenants/dev.db ist eine echte
        lokale Dev-DB.
        """
        from app.models.customer import Subscription, SubscriptionInterval
        kunde = _p4_kunde(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50")
        # Täglich ab gestern: fällig, auch wenn der Berliner Kalendertag dem
        # des Testrechners schon voraus ist.
        gestern = date.today() - timedelta(days=1)
        abo = _p4_abo(client, kunde, product_id=produkt["id"], intervall="TAEGLICH",
                      liefertage=None, gueltig_von=gestern)
        with TestingSessionLocal() as db:
            db.add(Subscription(
                kunde_id=uuid.UUID(kunde["id"]), menge=Decimal("2"), einheit="STUECK",
                intervall=SubscriptionInterval.TAEGLICH, gueltig_von=gestern,
            ))
            db.commit()

        with patch("app.tasks.subscription_tasks.SessionLocal",
                   side_effect=AssertionError("Knopf nutzt SessionLocal (Default-Mandant)")):
            r = client.post("/api/v1/sales/subscriptions/process-today")

        assert r.status_code == 200, r.text
        assert len(_p4_bestellungen(abo["id"])) == 1
        assert r.json()["message"] == (
            "1 Abo-Bestellung angelegt. 1 Abo übersprungen: "
            "LfA Förderbank Bayern (Abo hat weder Produkt noch Sorte)"
        )

    def test_liefertag_ist_der_berliner_kalendertag(self):
        """Der Container läuft in UTC: 22:30 UTC am 07.10. ist in München schon der 08.10."""
        from datetime import datetime, timezone
        from app.services import order_status_service
        from app.tasks.subscription_tasks import liefertag_heute

        class _Uhr(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 10, 7, 22, 30, tzinfo=timezone.utc).astimezone(tz)

        # liefertag_heute ruft order_status_service.heute_berlin (eine Regel)
        with patch.object(order_status_service, "datetime", _Uhr):
            assert liefertag_heute() == date(2026, 10, 8)


class TestNacharbeitStornosperre:
    @pytest.mark.parametrize("bestellstatus", ["ENTWURF", "BESTAETIGT", "IN_PRODUKTION"])
    @pytest.mark.parametrize("rechnungsart", ["entwurf", "offen", "sammel"])
    @pytest.mark.parametrize("weg", ["status", "sammel"])
    def test_aktive_rechnung_sperrt_storno_bis_rechnungsstorno(
        self, client, bestellstatus, rechnungsart, weg
    ):
        kunde = _kunde(client)
        anlegen = {
            "ENTWURF": _bestellung, "BESTAETIGT": _bestaetigt, "IN_PRODUKTION": _gepackt,
        }[bestellstatus]
        order = anlegen(client, kunde)
        weitere = _bestaetigt(client, kunde)
        if rechnungsart == "sammel":
            _lieferschein(client, order)
            response = client.post("/api/v1/invoices/batch-run/commit", json={
                "period_from": order["requested_delivery_date"],
                "period_to": order["requested_delivery_date"],
                "customer_ids": [kunde["id"]],
            })
            assert response.status_code == 201, response.text
            rechnung = response.json()["rechnungen"][0]
            # Der Lauf legt Entwürfe an (Paket 3, Q1); gemeint ist die ausgestellte Sammelrechnung
            response = client.post(f"/api/v1/invoices/{rechnung['id']}/finalize")
            assert response.status_code == 200, response.text
            rechnung = response.json()
        else:
            response = client.post(f"/api/v1/invoices/from-order/{order['id']}")
            assert response.status_code == 201, response.text
            rechnung = response.json()
            if rechnungsart == "offen":
                response = client.post(f"/api/v1/invoices/{rechnung['id']}/finalize")
                assert response.status_code == 200, response.text
                # Die Rechnungsnummer vergibt erst das Finalisieren (Paket 3, Q1)
                rechnung = response.json()

        def stornieren():
            if weg == "status":
                return _status(client, order, "STORNIERT", reason="Aus Bearbeiten-Dialog")
            return client.post("/api/v1/sales/orders/bulk-status", json={
                "order_ids": [weitere["id"], order["id"]], "status": "STORNIERT",
            })

        vorher = _audit(client, order)
        response = stornieren()
        assert response.status_code == 400, response.text
        if rechnungsart == "entwurf":
            # Ein Entwurf wird verworfen, nicht storniert, und erscheint ohne
            # seinen Platzhalter (Paket 3, Q1)
            assert "Rechnungsentwurf (noch ohne Nummer)" in response.json()["detail"]
            assert "erst den Entwurf verwerfen" in response.json()["detail"]
        else:
            assert rechnung["invoice_number"] in response.json()["detail"]
            assert "erst die Rechnung stornieren" in response.json()["detail"]
        assert _lesen(client, order)["status"] == bestellstatus
        assert _lesen(client, weitere)["status"] == "BESTAETIGT"
        assert _audit(client, order) == vorher

        response = client.post(f"/api/v1/invoices/{rechnung['id']}/cancel", json={
            "reason": "Bestellung entfällt", "create_credit_note": rechnungsart != "entwurf",
        })
        assert response.status_code == 200, response.text
        response = stornieren()
        assert response.status_code == 200, response.text
        assert _lesen(client, order)["status"] == "STORNIERT"

    def test_service_verweigert_storno_vor_jeder_aenderung(self, client):
        from app.models.order import Order, OrderStatus
        from app.services.order_status_service import StatuswechselFehler, setze_status

        order = _bestaetigt(client, _kunde(client))
        response = client.post(f"/api/v1/invoices/from-order/{order['id']}")
        assert response.status_code == 201, response.text
        with TestingSessionLocal() as db:
            gespeichert = db.get(Order, uuid.UUID(order["id"]))
            # Ein Entwurf erscheint ohne seinen Platzhalter (Paket 3, Q1)
            with pytest.raises(StatuswechselFehler, match=r"Rechnungsentwurf \(noch ohne Nummer\)"):
                setze_status(db, gespeichert, OrderStatus.STORNIERT, user=None)
            assert gespeichert.status == OrderStatus.BESTAETIGT
            assert not db.new


class TestNacharbeitPacktagBerlin:
    @pytest.fixture(params=[("2026-10-07T22:30:00+00:00", date(2026, 10, 8)),
                            ("2026-01-07T23:30:00+00:00", date(2026, 1, 8))])
    def berliner_mitternacht(self, request, monkeypatch):
        from datetime import datetime
        from app.models import order as order_model
        from app.services import order_status_service

        zeitpunkt, heute = request.param
        instant = datetime.fromisoformat(zeitpunkt)

        class BerlinerUhr(datetime):
            @classmethod
            def now(cls, tz=None):
                return instant.astimezone(tz)

        class ServerDatum(date):
            @classmethod
            def today(cls):
                return instant.date()

        monkeypatch.setattr(order_status_service, "datetime", BerlinerUhr)
        monkeypatch.setattr(order_model, "date", ServerDatum)
        return heute

    def test_packtag_verwendet_berliner_tag(self, berliner_mitternacht):
        from app.models.order import Order

        heute = berliner_mitternacht
        assert Order.resolve_packing_date(heute, None) == heute
        assert Order.resolve_packing_date(heute + timedelta(days=1), None) is None
        assert Order.resolve_packing_date(heute, heute - timedelta(days=2)) == heute - timedelta(days=2)

    def test_heute_verarbeiten_setzt_packtag(self, client, berliner_mitternacht):
        from app.models.order import Order

        heute = berliner_mitternacht
        kunde = _p4_kunde(client)
        produkt = _p4_produkt(client, "Erbse", "BERLIN-ABO", "3.50")
        _p4_abo(client, kunde, gueltig_von=heute, product_id=produkt["id"],
                intervall="TAEGLICH", liefertage=[])
        response = client.post("/api/v1/sales/subscriptions/process-today")
        assert response.status_code == 200, response.text
        assert response.json()["details"]["erstellt"] == 1
        with TestingSessionLocal() as db:
            order = db.query(Order).one()
            assert order.requested_delivery_date == heute
            assert order.packing_date == heute
            assert order.effective_packing_date == heute


class TestNacharbeitLeistungsdatum:
    def _lieferung(self, client, ist_tag, ls_tag, mit_lieferschein=True):
        from app.models.documents import DeliveryNote

        order = _bestaetigt(client, _kunde(client), liefertag=date(2026, 3, 5))
        note = _lieferschein(client, order) if mit_lieferschein else None
        if ist_tag:
            response = _status(client, order, "GELIEFERT", actual_delivery_date=ist_tag)
            assert response.status_code == 200, response.text
        if ls_tag:
            with TestingSessionLocal() as db:
                db.get(DeliveryNote, uuid.UUID(note["id"])).actual_delivery_date = date.fromisoformat(ls_tag)
                db.commit()
        return order, note

    @pytest.mark.parametrize("mit_lieferschein,ist_tag,ls_tag,erwartet", [
        (True, "2026-03-06", None, "2026-03-06"),
        (True, "2026-03-06", "2026-03-07", "2026-03-07"),
        (True, None, None, "2026-03-05"),
        (False, "2026-03-06", None, "2026-03-06"),
        (False, None, None, "2026-03-05"),
    ])
    def test_rechnung_aus_bestellung_nutzt_leistungsdatum(
        self, client, mit_lieferschein, ist_tag, ls_tag, erwartet
    ):
        order, note = self._lieferung(client, ist_tag, ls_tag, mit_lieferschein)
        response = client.post(f"/api/v1/invoices/from-order/{order['id']}")
        assert response.status_code == 201, response.text
        rechnung = response.json()
        assert rechnung["delivery_date"] == erwartet
        if note:
            response = client.get(f"/api/v1/invoices/{rechnung['id']}/delivery-notes")
            assert response.status_code == 200, response.text
            assert response.json()[0]["lieferdatum"] == erwartet

    @pytest.mark.parametrize("ist_tag,ls_tag,erwartet", [
        ("2026-03-06", None, "2026-03-06"),
        ("2026-03-06", "2026-03-07", "2026-03-07"),
        (None, None, "2026-03-05"),
    ])
    def test_sammelrechnung_filtert_und_zeigt_leistungsdatum(self, client, ist_tag, ls_tag, erwartet):
        self._lieferung(client, ist_tag, ls_tag)
        anfrage = {"period_from": erwartet, "period_to": erwartet}
        response = client.post("/api/v1/invoices/batch-run/preview", json=anfrage)
        assert response.status_code == 200, response.text
        assert len(response.json()["kunden"]) == 1
        if erwartet != "2026-03-05":
            response = client.post("/api/v1/invoices/batch-run/preview", json={
                "period_from": "2026-03-05", "period_to": "2026-03-05",
            })
            assert response.status_code == 200, response.text
            assert response.json()["kunden"] == []
        response = client.post("/api/v1/invoices/batch-run/commit", json=anfrage)
        assert response.status_code == 201, response.text
        rechnung = response.json()["rechnungen"][0]
        assert rechnung["service_period_start"] == erwartet
        assert rechnung["service_period_end"] == erwartet
        response = client.get(f"/api/v1/invoices/{rechnung['id']}/delivery-notes")
        assert response.status_code == 200, response.text
        assert response.json()[0]["lieferdatum"] == erwartet


class TestNacharbeitBestellliste:
    @pytest.mark.parametrize("page,page_size,erwartete_nummern", [
        (1, 100, list(range(100, 0, -1))),
        (2, 100, [0]),
        (1, 150, list(range(100, 0, -1))),
    ])
    def test_hundert_bestellungen_stabil_neueste_zuerst(self, client, page, page_size, erwartete_nummern):
        from datetime import datetime
        from app.models.order import Order

        kunde = _kunde(client)
        with TestingSessionLocal() as db:
            for nummer in range(100, -1, -1):
                db.add(Order(
                    order_number=f"BE-LISTE-{nummer:04d}", customer_id=uuid.UUID(kunde["id"]),
                    order_date=datetime(2026, 3, 6, 12),
                    requested_delivery_date=date(2026, 3, 10),
                ))
            db.commit()
        response = client.get("/api/v1/sales/orders", params={"page": page, "page_size": page_size})
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 101
        assert [order["order_number"] for order in response.json()["items"]] == [
            f"BE-LISTE-{nummer:04d}" for nummer in erwartete_nummern
        ]

    def test_bestelldatum_hat_vorrang_vor_lieferdatum_und_nummer(self, client):
        from datetime import datetime
        from app.models.order import Order

        kunde = _kunde(client)
        with TestingSessionLocal() as db:
            db.add_all([
                Order(order_number="BE-ALT-9999", customer_id=uuid.UUID(kunde["id"]),
                      order_date=datetime(2026, 3, 5), requested_delivery_date=date(2026, 12, 1)),
                Order(order_number="BE-NEU-0001", customer_id=uuid.UUID(kunde["id"]),
                      order_date=datetime(2026, 3, 6), requested_delivery_date=date(2026, 3, 7)),
            ])
            db.commit()
        response = client.get("/api/v1/sales/orders", params={"page_size": 100})
        assert response.status_code == 200, response.text
        assert [order["order_number"] for order in response.json()["items"]] == [
            "BE-NEU-0001", "BE-ALT-9999",
        ]
