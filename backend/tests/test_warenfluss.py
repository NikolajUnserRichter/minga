"""Warenfluss-Release, AP4b: Härtung des Bestands-Bewegungsjournals.

Das Journal (InventoryMovement) existiert seit langem — aber zwei Dinge
verhindern, dass es als Zertifizierungsnachweis taugt:

1. Substrat- und Pfandkisten-Artikel laufen über packaging_inventory mit
   article_type, die Bewegungen wurden aber hart als VERPACKUNG gebucht —
   im Journal sind die Materialflüsse damit nicht unterscheidbar (R5.7).
2. Es gab keine Gegenbuchung: eine Fehlbuchung ließ sich nur durch manuelles
   Gegeneingeben korrigieren, ohne Verweis auf die Ursprungsbewegung (R4.7).
"""
from decimal import Decimal

import pytest


def _bestand(client, location, seed, charge, gramm):
    r = client.post("/api/v1/inventory/seeds/receive", params={
        "seed_id": seed["id"], "batch_number": charge,
        "quantity": gramm, "unit": "G", "location_id": location["id"],
    })
    assert r.status_code == 201, r.text
    return r.json()


class TestMaterialtypImJournal:
    """Substrat und Pfandkisten müssen als solche im Journal stehen."""

    def _wareneingang(self, client, sku, article_type):
        r = client.post("/api/v1/inventory/packaging/receive", params={
            "sku": sku, "name": f"Test {sku}", "quantity": 100,
            "unit": "Stück", "article_type": article_type,
        })
        assert r.status_code == 201, r.text
        return r.json()

    def _bewegungen_fuer(self, client, packaging_id):
        r = client.get("/api/v1/inventory/movements")
        assert r.status_code == 200, r.text
        return [m for m in r.json() if m.get("packaging_id") == packaging_id]

    def test_substrat_wareneingang_bucht_substrat(self, client):
        artikel = self._wareneingang(client, "ERDE-1", "SUBSTRAT")
        bewegungen = self._bewegungen_fuer(client, artikel["id"])
        assert len(bewegungen) == 1
        assert bewegungen[0]["item_type"] == "SUBSTRAT"

    def test_pfandkiste_wareneingang_bucht_pfandkiste(self, client):
        artikel = self._wareneingang(client, "PFAND-1", "PFANDKISTE")
        bewegungen = self._bewegungen_fuer(client, artikel["id"])
        assert bewegungen[0]["item_type"] == "PFANDKISTE"

    def test_verpackung_bleibt_verpackung(self, client):
        artikel = self._wareneingang(client, "SCHALE-1", "VERPACKUNG")
        bewegungen = self._bewegungen_fuer(client, artikel["id"])
        assert bewegungen[0]["item_type"] == "VERPACKUNG"


class TestGegenbuchung:
    """R4.7: Bewegungen sind unveränderlich — korrigiert wird per Gegenbuchung."""

    def _entnahme(self, client, sample_seed, sample_location):
        bestand = _bestand(client, sample_location, sample_seed, "GB-1", 1000)
        r = client.post(f"/api/v1/inventory/seeds/{bestand['id']}/consume",
                        params={"quantity": 0.25})
        assert r.status_code == 200, r.text
        return bestand, r.json()["movement"]

    def test_gegenbuchung_stellt_bestand_wieder_her(self, client, sample_seed, sample_location):
        bestand, bewegung = self._entnahme(client, sample_seed, sample_location)

        r = client.post(f"/api/v1/inventory/movements/{bewegung['id']}/reverse",
                        json={"grund": "Fehlbuchung — falscher Sack gescannt"})

        assert r.status_code == 201, r.text
        gegen = r.json()
        # Entnahme war -0.250 → Gegenbuchung +0.250, Bestand wieder voll
        assert Decimal(str(gegen["quantity"])) == Decimal("0.250")
        assert gegen["reverses_movement_id"] == bewegung["id"]

        inv = client.get(f"/api/v1/inventory/seeds/{bestand['id']}").json()
        assert Decimal(str(inv["current_quantity_kg"])) == Decimal("1.000")

    def test_original_bleibt_unveraendert(self, client, sample_seed, sample_location):
        _, bewegung = self._entnahme(client, sample_seed, sample_location)
        client.post(f"/api/v1/inventory/movements/{bewegung['id']}/reverse",
                    json={"grund": "Fehlbuchung"})

        alle = client.get("/api/v1/inventory/movements").json()
        original = next(m for m in alle if m["id"] == bewegung["id"])
        assert Decimal(str(original["quantity"])) == Decimal("-0.250")

    def test_gegenbuchung_braucht_grund(self, client, sample_seed, sample_location):
        _, bewegung = self._entnahme(client, sample_seed, sample_location)
        r = client.post(f"/api/v1/inventory/movements/{bewegung['id']}/reverse", json={})
        assert r.status_code == 422, r.text

    def test_doppelte_gegenbuchung_wird_abgelehnt(self, client, sample_seed, sample_location):
        """Zweimal rückgängig = doppelter Bestand — muss scheitern."""
        _, bewegung = self._entnahme(client, sample_seed, sample_location)
        erste = client.post(f"/api/v1/inventory/movements/{bewegung['id']}/reverse",
                            json={"grund": "Fehlbuchung"})
        assert erste.status_code == 201

        zweite = client.post(f"/api/v1/inventory/movements/{bewegung['id']}/reverse",
                             json={"grund": "nochmal"})
        assert zweite.status_code == 409, zweite.text

    def test_gegenbuchung_einer_gegenbuchung_wird_abgelehnt(self, client, sample_seed, sample_location):
        """Die Korrektur der Korrektur ist eine neue Buchung, kein Reverse-Reverse."""
        _, bewegung = self._entnahme(client, sample_seed, sample_location)
        gegen = client.post(f"/api/v1/inventory/movements/{bewegung['id']}/reverse",
                            json={"grund": "Fehlbuchung"}).json()

        r = client.post(f"/api/v1/inventory/movements/{gegen['id']}/reverse",
                        json={"grund": "doch nicht"})
        assert r.status_code == 400, r.text

    def test_unbekannte_bewegung_gibt_404(self, client):
        r = client.post("/api/v1/inventory/movements/00000000-0000-0000-0000-0000000000ff/reverse",
                        json={"grund": "x"})
        assert r.status_code == 404, r.text


HEUTE = None  # wird unten aus date.today() gesetzt — Reports rechnen mit echten Daten


class TestWarenflussReport:
    """AP5: Saatgut-Warenfluss je Sorte — der Zertifizierungsnachweis.

    Einheiten-Falle: Saatgut-Bewegungen aus dem Lager laufen in kg, die aus
    dem Historien-Import in g. Der Report normalisiert auf Gramm.
    """

    def _saatgut_szenario(self, client, sample_seed, sample_location):
        """Zugang 1000 g, Entnahme 250 g — beides heute."""
        bestand = _bestand(client, sample_location, sample_seed, "WF-1", 1000)
        r = client.post(f"/api/v1/inventory/seeds/{bestand['id']}/consume",
                        params={"quantity": 0.25})
        assert r.status_code == 200, r.text

    def _report(self, client, **params):
        from datetime import date
        params.setdefault("material_type", "SAATGUT")
        params.setdefault("von", "2026-01-01")
        params.setdefault("bis", date.today().isoformat())
        r = client.get("/api/v1/reports/material-flow", params=params)
        assert r.status_code == 200, r.text
        return r.json()

    def test_saatgut_summen_je_sorte_in_gramm(self, client, sample_seed, sample_location):
        self._saatgut_szenario(client, sample_seed, sample_location)

        report = self._report(client)

        zeile = next(z for z in report["zeilen"] if z["schluessel"] == sample_seed["name"])
        assert Decimal(str(zeile["zugang"])) == Decimal("1000")
        assert Decimal(str(zeile["verbrauch"])) == Decimal("-250")
        assert Decimal(str(zeile["endbestand"])) == Decimal("750")

    def test_anfangsbestand_kommt_aus_bewegungen_vor_dem_zeitraum(self, client, sample_seed, sample_location):
        from datetime import date, timedelta
        self._saatgut_szenario(client, sample_seed, sample_location)

        # Zeitraum beginnt erst morgen → alles Heutige wandert in den Anfangsbestand
        morgen = (date.today() + timedelta(days=1)).isoformat()
        report = self._report(client, von=morgen, bis=morgen)

        zeile = next(z for z in report["zeilen"] if z["schluessel"] == sample_seed["name"])
        assert Decimal(str(zeile["anfangsbestand"])) == Decimal("750")
        assert Decimal(str(zeile["zugang"])) == Decimal("0")
        assert Decimal(str(zeile["endbestand"])) == Decimal("750")

    def test_substrat_und_verpackung_getrennt(self, client):
        for sku, art in [("ERDE-9", "SUBSTRAT"), ("SCHALE-9", "VERPACKUNG")]:
            r = client.post("/api/v1/inventory/packaging/receive", params={
                "sku": sku, "name": f"Artikel {sku}", "quantity": 100, "article_type": art,
            })
            assert r.status_code == 201, r.text

        substrat = self._report(client, material_type="SUBSTRAT")
        schluessel = [z["schluessel"] for z in substrat["zeilen"]]
        assert "Artikel ERDE-9" in schluessel
        assert "Artikel SCHALE-9" not in schluessel

    def test_drilldown_kennzeichnet_importierte_bewegungen(self, client, sample_seed):
        """R5.6: importierte Historie ist im Drilldown als solche erkennbar."""
        import io as _io
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.title = "Daten"
        ws.append(["sorte", "aussaat_datum", "tray_anzahl", "externe_chargennummer", "saatgut_gramm"])
        ws.append([sample_seed["name"], "2026-03-10", 4, "DD-1", 200])
        buf = _io.BytesIO(); wb.save(buf)
        r = client.post("/api/v1/imports/grow-batches/commit", files={
            "file": ("h.xlsx", buf.getvalue(),
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert r.status_code == 201, r.text

        details = client.get("/api/v1/reports/material-flow/details", params={
            "material_type": "SAATGUT", "von": "2026-03-01", "bis": "2026-03-31",
        })
        assert details.status_code == 200, details.text
        zeilen = details.json()
        assert len(zeilen) == 1
        assert zeilen[0]["aus_import"] is True
        assert zeilen[0]["sorte"] == sample_seed["name"]

    def test_export_csv_und_pdf(self, client, sample_seed, sample_location):
        self._saatgut_szenario(client, sample_seed, sample_location)

        csv = client.get("/api/v1/reports/material-flow/export",
                         params={"material_type": "SAATGUT", "format": "csv",
                                 "von": "2026-01-01", "bis": "2026-12-31"})
        assert csv.status_code == 200, csv.text
        assert sample_seed["name"] in csv.text

        pdf = client.get("/api/v1/reports/material-flow/export",
                         params={"material_type": "SAATGUT", "format": "pdf",
                                 "von": "2026-01-01", "bis": "2026-12-31"})
        assert pdf.status_code == 200
        assert pdf.content.startswith(b"%PDF")
