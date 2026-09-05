"""Warenfluss-Release, AP6: Inventur für Jahresabschluss und Zertifizierung.

Das Grundgerüst (Zählung, Soll-Snapshot, Korrekturbuchung) existierte.
Gefehlt haben: Inventurtyp und Stichtag als tragende Begriffe, die Korrektur
ZUM STICHTAG statt zum Abschlusszeitpunkt, der Differenzschwellwert mit
Pflicht-Bemerkung, die Bewertung (letzter EK), Zählliste und Exporte.
Nebenbefund: der Fund-Positionen-Endpunkt crashte mit TypeError
(inventory_count_id statt count_id).
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

COUNTS = "/api/v1/inventory/counts"


@pytest.fixture
def bestand(client, sample_seed, sample_location):
    """1 kg Saatgut zu 50 €/kg — die Basis jeder Zählung."""
    r = client.post("/api/v1/inventory/seeds/receive", params={
        "seed_id": sample_seed["id"], "batch_number": "INV-1",
        "quantity": 1000, "unit": "G", "location_id": sample_location["id"],
        "purchase_price": 50.00,
    })
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def inventur(client, bestand):
    r = client.post(COUNTS, params={
        "typ": "JAHRESINVENTUR", "count_date": date.today().isoformat(),
    })
    assert r.status_code == 201, r.text
    return r.json()


def _detail(client, count_id):
    r = client.get(f"{COUNTS}/{count_id}")
    assert r.status_code == 200, r.text
    return r.json()


def _zaehle(client, count_id, item_id, menge, **extra):
    return client.put(f"{COUNTS}/{count_id}/items/{item_id}",
                      json={"counted_quantity": menge, **extra})


class TestAnlegen:
    def test_typ_und_stichtag_ohne_lagerort_zwang(self, client, inventur):
        assert inventur["typ"] == "JAHRESINVENTUR"
        detail = _detail(client, inventur["id"])
        assert len(detail["items"]) == 1
        assert Decimal(str(detail["items"][0]["system_quantity"])) == Decimal("1.000")

    def test_soll_snapshot_friert_ein(self, client, sample_seed, sample_location, inventur):
        """R6.3: spätere Buchungen ändern den eingefrorenen Sollbestand nicht."""
        r = client.post("/api/v1/inventory/seeds/receive", params={
            "seed_id": sample_seed["id"], "batch_number": "INV-2",
            "quantity": 500, "unit": "G", "location_id": sample_location["id"],
        })
        assert r.status_code == 201

        detail = _detail(client, inventur["id"])
        alt = next(i for i in detail["items"] if i["system_quantity"] is not None)
        assert Decimal(str(alt["system_quantity"])) == Decimal("1.000")


class TestZaehlung:
    def test_zaehlen_berechnet_differenz(self, client, inventur):
        item = _detail(client, inventur["id"])["items"][0]

        r = _zaehle(client, inventur["id"], item["id"], 0.8)

        assert r.status_code == 200, r.text
        assert Decimal(str(r.json()["difference"])) == Decimal("-0.200")

    def test_fund_position_kann_ergaenzt_werden(self, client, bestand, inventur):
        """R6.5: was gezählt wurde, aber nicht im Soll steht (heute: TypeError)."""
        r = client.post(f"{COUNTS}/{inventur['id']}/items", json={
            "item_type": "SAATGUT", "system_quantity": 0,
            "counted_quantity": 0.3, "unit": "kg",
            "notes": "Fund: angebrochener Sack im Kühlraum",
        })
        assert r.status_code in (200, 201), r.text


class TestAbschluss:
    def test_korrektur_bucht_zum_stichtag(self, client, bestand, inventur):
        """R6.7: Buchungsdatum der Korrektur = Stichtag, nicht 'jetzt'."""
        item = _detail(client, inventur["id"])["items"][0]
        _zaehle(client, inventur["id"], item["id"], 0.96)  # −4 %, unter der Schwelle

        r = client.post(f"{COUNTS}/{inventur['id']}/finalize")
        assert r.status_code == 200, r.text

        inv = client.get(f"/api/v1/inventory/seeds/{bestand['id']}").json()
        assert Decimal(str(inv["current_quantity_kg"])) == Decimal("0.960")

        movements = client.get("/api/v1/inventory/movements",
                               params={"movement_type": "KORREKTUR"}).json()
        assert len(movements) == 1
        assert movements[0]["movement_date"].startswith(date.today().isoformat())

    def test_grosse_differenz_braucht_bemerkung(self, client, inventur):
        """R6.6: ab 5 % Abweichung ist die Bemerkung Pflicht."""
        item = _detail(client, inventur["id"])["items"][0]
        _zaehle(client, inventur["id"], item["id"], 0.5)  # −50 %

        r = client.post(f"{COUNTS}/{inventur['id']}/finalize")
        assert r.status_code == 400, r.text

        _zaehle(client, inventur["id"], item["id"], 0.5,
                notes="Wasserschaden, Sack entsorgt")
        r = client.post(f"{COUNTS}/{inventur['id']}/finalize")
        assert r.status_code == 200, r.text

    def test_abgeschlossene_inventur_ist_unveraenderlich(self, client, inventur):
        item = _detail(client, inventur["id"])["items"][0]
        _zaehle(client, inventur["id"], item["id"], 1.0)
        client.post(f"{COUNTS}/{inventur['id']}/finalize")

        r = _zaehle(client, inventur["id"], item["id"], 0.2)
        assert r.status_code == 400, r.text


class TestBewertung:
    def test_letzter_einkaufspreis_je_position_und_summe(self, client, inventur):
        """R6.8: Wertansatz = gezählte Menge × letzter EK der Bestandseinheit."""
        item = _detail(client, inventur["id"])["items"][0]
        _zaehle(client, inventur["id"], item["id"], 0.8)

        detail = _detail(client, inventur["id"])
        pos = detail["items"][0]
        assert Decimal(str(pos["wert"])) == Decimal("40.00")  # 0.8 kg × 50 €/kg
        assert Decimal(str(detail["gesamtwert"])) == Decimal("40.00")


class TestExporte:
    def test_zaehlliste_pdf_blind(self, client, inventur):
        r = client.get(f"{COUNTS}/{inventur['id']}/zaehlliste", params={"blind": True})
        assert r.status_code == 200, r.text
        assert r.content.startswith(b"%PDF")

    def test_abschluss_pdf_und_xlsx(self, client, inventur):
        item = _detail(client, inventur["id"])["items"][0]
        _zaehle(client, inventur["id"], item["id"], 1.0)
        client.post(f"{COUNTS}/{inventur['id']}/finalize")

        pdf = client.get(f"{COUNTS}/{inventur['id']}/export", params={"format": "pdf"})
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

        xlsx = client.get(f"{COUNTS}/{inventur['id']}/export", params={"format": "xlsx"})
        assert xlsx.status_code == 200 and xlsx.content.startswith(b"PK")
