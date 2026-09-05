"""Warenfluss-Release, AP2: Sammelrechnung aus Lieferscheinen.

Gernots Fall: manche Kunden wollen EINE Monatsrechnung, zusammengesetzt aus
allen Lieferscheinen des Monats. Aggregiert wird je Artikel + Einheit +
Einzelpreis + Steuersatz; die enthaltenen Lieferscheine bleiben referenziert.
"""
from datetime import date
from decimal import Decimal

import pytest

PREVIEW = "/api/v1/invoices/batch-run/preview"
COMMIT = "/api/v1/invoices/batch-run/commit"


def _bestellung_mit_ls(client, customer_id, liefertag, zeilen):
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": customer_id,
        "requested_delivery_date": liefertag,
        "lines": zeilen,
    })
    assert r.status_code == 201, r.text
    note = client.post(f"/api/v1/sales/orders/{r.json()['id']}/delivery-notes", json={})
    assert note.status_code == 201, note.text
    return note.json()


@pytest.fixture
def maerz_lieferungen(client, sample_customer):
    """Zwei Lieferungen im März: derselbe Artikel zweimal zum selben Preis,
    einmal zu einem anderen — ergibt zwei getrennte Positionen."""
    ls1 = _bestellung_mit_ls(client, sample_customer["id"], "2026-03-05", [
        {"product_name": "Erbsen-Schale", "quantity": 10, "unit": "STK",
         "unit_price": 2.50, "tax_rate": "REDUZIERT"},
    ])
    ls2 = _bestellung_mit_ls(client, sample_customer["id"], "2026-03-19", [
        {"product_name": "Erbsen-Schale", "quantity": 5, "unit": "STK",
         "unit_price": 2.50, "tax_rate": "REDUZIERT"},
        {"product_name": "Erbsen-Schale", "quantity": 3, "unit": "STK",
         "unit_price": 3.00, "tax_rate": "REDUZIERT"},
    ])
    return [ls1, ls2]


def _lauf(client, endpoint, **extra):
    return client.post(endpoint, json={
        "period_from": "2026-03-01", "period_to": "2026-03-31", **extra,
    })


class TestVorschau:
    def test_aggregiert_je_artikel_und_preis(self, client, sample_customer, maerz_lieferungen):
        r = _lauf(client, PREVIEW)

        assert r.status_code == 200, r.text
        kunden = r.json()["kunden"]
        assert len(kunden) == 1
        k = kunden[0]
        assert k["anzahl_lieferscheine"] == 2

        # unit_price kommt als JSON-Zahl (2.5) — für den Vergleich normalisieren
        positionen = {
            (p["description"], Decimal(str(p["unit_price"])).quantize(Decimal("0.01"))):
                Decimal(str(p["quantity"]))
            for p in k["positionen"]
        }
        # 10 + 5 zum selben Preis werden eine Position, der andere Preis bleibt eigen
        assert positionen[("Erbsen-Schale", Decimal("2.50"))] == Decimal("15")
        assert positionen[("Erbsen-Schale", Decimal("3.00"))] == Decimal("3")

    def test_vorschau_schreibt_nichts(self, client, sample_customer, maerz_lieferungen):
        _lauf(client, PREVIEW)
        # Der Lauf danach findet weiterhin beide Lieferscheine
        r = _lauf(client, PREVIEW)
        assert r.json()["kunden"][0]["anzahl_lieferscheine"] == 2

    def test_zeitraum_grenzt_ab(self, client, sample_customer, maerz_lieferungen):
        r = client.post(PREVIEW, json={
            "period_from": "2026-04-01", "period_to": "2026-04-30",
        })
        assert r.json()["kunden"] == []


class TestFestschreiben:
    def test_eine_rechnung_je_kunde_mit_leistungszeitraum(self, client, sample_customer, maerz_lieferungen):
        r = _lauf(client, COMMIT)

        assert r.status_code == 201, r.text
        rechnungen = r.json()["rechnungen"]
        assert len(rechnungen) == 1
        rechnung = rechnungen[0]
        # 15×2.50 + 3×3.00 = 46.50 netto
        assert Decimal(str(rechnung["subtotal"])) == Decimal("46.50")

        detail = client.get(f"/api/v1/invoices/{rechnung['id']}").json()
        assert detail["service_period_start"] == "2026-03-01"
        assert detail["service_period_end"] == "2026-03-31"

    def test_lieferscheine_haengen_an_der_rechnung(self, client, sample_customer, maerz_lieferungen):
        rechnung = _lauf(client, COMMIT).json()["rechnungen"][0]

        r = client.get(f"/api/v1/invoices/{rechnung['id']}/delivery-notes")
        assert r.status_code == 200, r.text
        nummern = {ls["delivery_note_number"] for ls in r.json()}
        assert nummern == {ls["delivery_note_number"] for ls in maerz_lieferungen}

    def test_zweiter_lauf_ist_leer(self, client, sample_customer, maerz_lieferungen):
        _lauf(client, COMMIT)
        zweiter = _lauf(client, COMMIT)
        assert zweiter.json()["rechnungen"] == []

    def test_nach_storno_sind_die_lieferscheine_wieder_im_lauf(self, client, sample_customer, maerz_lieferungen):
        """R1.6 + R2.5 zusammen: Storno gibt frei, der nächste Lauf nimmt sie."""
        erste = _lauf(client, COMMIT).json()["rechnungen"][0]

        storno = client.post(f"/api/v1/invoices/{erste['id']}/cancel", json={
            "reason": "Preisfehler", "reason_code": "PREISFEHLER",
        })
        assert storno.status_code == 200, storno.text

        zweite = _lauf(client, COMMIT).json()["rechnungen"]
        assert len(zweite) == 1
        assert zweite[0]["id"] != erste["id"]
        assert Decimal(str(zweite[0]["subtotal"])) == Decimal("46.50")

    def test_kundenfilter(self, client, sample_customer, maerz_lieferungen):
        r = _lauf(client, COMMIT, customer_ids=["00000000-0000-0000-0000-0000000000ff"])
        assert r.json()["rechnungen"] == []
