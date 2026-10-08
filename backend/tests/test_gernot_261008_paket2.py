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
