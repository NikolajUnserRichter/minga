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
