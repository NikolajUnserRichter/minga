"""Warenfluss-Release, AP3 v2: Chargen-Historie mit Report, Bestandswirkung, Rollback.

Der bestehende Import (imports.py, Entity grow_batches) legt Chargen an, aber:
der erste Fehler bricht alles ab (kein Zeilenreport), es gibt keine
Import-Läufe (kein Rollback), und er bucht keine Lagerbewegungen — die
Warenfluss-Auswertung sah die Historie nicht.

Wichtige Festlegung: historische Bewegungen (source=import) buchen ins
JOURNAL, nicht auf den Ist-Bestand. Der Ist-Bestand ist gezählte Gegenwart —
ihn um Historie zu verändern, würde ihn verfälschen.
"""
import io
from datetime import date
from decimal import Decimal

import pytest
from openpyxl import Workbook

SPALTEN = ["sorte", "aussaat_datum", "tray_anzahl", "externe_chargennummer",
           "saatgut_gramm", "ernte_datum", "ernte_menge_gramm",
           "ausschuss_menge_gramm", "ausschuss_grund", "notiz"]


def _xlsx(zeilen: list[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Daten"
    ws.append(SPALTEN)
    for z in zeilen:
        ws.append([z.get(s) for s in SPALTEN])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload(client, url, daten: bytes, **params):
    return client.post(url, params=params, files={
        "file": ("chargen.xlsx", daten,
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    })


@pytest.fixture
def zwei_zeilen(sample_seed):
    return [
        {"sorte": sample_seed["name"], "aussaat_datum": "2026-03-10",
         "tray_anzahl": 4, "externe_chargennummer": "ALT-001", "saatgut_gramm": 200},
        {"sorte": sample_seed["name"], "aussaat_datum": "2026-03-12",
         "tray_anzahl": 2, "externe_chargennummer": "ALT-002", "saatgut_gramm": 100,
         "ernte_datum": "2026-03-24", "ernte_menge_gramm": 1500,
         "ausschuss_menge_gramm": 100, "ausschuss_grund": "Schimmel"},
    ]


def _bewegungen_im_maerz(client):
    r = client.get("/api/v1/inventory/movements",
                   params={"from_date": "2026-03-01", "to_date": "2026-03-31"})
    assert r.status_code == 200, r.text
    return r.json()


def _batches(client):
    r = client.get("/api/v1/production/grow-batches").json()
    return r if isinstance(r, list) else r.get("items", [])


class TestValidierung:
    """R3.3: Dry-Run mit Zeilenreport, bevor irgendetwas geschrieben wird."""

    def test_gueltige_datei_meldet_alle_zeilen_ok(self, client, zwei_zeilen):
        r = _upload(client, "/api/v1/imports/grow-batches/validate", _xlsx(zwei_zeilen))

        assert r.status_code == 200, r.text
        report = r.json()
        assert report["zusammenfassung"]["ok"] == 2
        assert report["zusammenfassung"]["fehler"] == 0
        assert all(z["status"] == "OK" for z in report["zeilen"])

    def test_unbekannte_sorte_als_fehler_mit_zeilennummer(self, client, zwei_zeilen):
        zwei_zeilen[1]["sorte"] = "Fantasia"
        r = _upload(client, "/api/v1/imports/grow-batches/validate", _xlsx(zwei_zeilen))

        report = r.json()
        fehler = [z for z in report["zeilen"] if z["status"] == "FEHLER"]
        assert len(fehler) == 1
        assert fehler[0]["zeile"] == 3  # Kopfzeile ist Zeile 1
        assert "Fantasia" in fehler[0]["meldung"]
        assert report["fehlende_sorten"] == ["Fantasia"]

    def test_fehlendes_pflichtfeld_als_fehler(self, client, zwei_zeilen):
        zwei_zeilen[0]["aussaat_datum"] = None
        r = _upload(client, "/api/v1/imports/grow-batches/validate", _xlsx(zwei_zeilen))

        fehler = [z for z in r.json()["zeilen"] if z["status"] == "FEHLER"]
        assert len(fehler) == 1 and fehler[0]["zeile"] == 2

    def test_validate_schreibt_nichts(self, client, zwei_zeilen):
        _upload(client, "/api/v1/imports/grow-batches/validate", _xlsx(zwei_zeilen))
        assert _batches(client) == []


class TestCommit:
    def test_legt_chargen_an_und_liefert_run_id(self, client, zwei_zeilen):
        r = _upload(client, "/api/v1/imports/grow-batches/commit", _xlsx(zwei_zeilen))

        assert r.status_code == 201, r.text
        ergebnis = r.json()
        assert ergebnis["created"] == 2
        assert ergebnis["import_run_id"]
        assert len(_batches(client)) == 2

    def test_idempotent_ueber_externe_chargennummer(self, client, zwei_zeilen):
        _upload(client, "/api/v1/imports/grow-batches/commit", _xlsx(zwei_zeilen))
        zweiter = _upload(client, "/api/v1/imports/grow-batches/commit", _xlsx(zwei_zeilen)).json()

        assert zweiter["created"] == 0
        assert zweiter["skipped"] == 2

    def test_bucht_verbrauch_ernte_und_ausschuss_historisch(self, client, zwei_zeilen):
        """R3.5: Bewegungen tragen das historische Datum — die Warenfluss-
        Auswertung stimmt damit rückwirkend."""
        _upload(client, "/api/v1/imports/grow-batches/commit", _xlsx(zwei_zeilen))

        bewegungen = _bewegungen_im_maerz(client)
        nach_typ = {}
        for b in bewegungen:
            nach_typ.setdefault(b["movement_type"], []).append(b)

        # Zwei Aussaaten → zwei Saatgutverbräuche, negativ, am Aussaattag
        verbrauch = sorted(nach_typ["PRODUKTION"], key=lambda b: b["movement_date"])
        assert [Decimal(str(b["quantity"])) for b in verbrauch] == [Decimal("-200"), Decimal("-100")]
        assert verbrauch[0]["movement_date"].startswith("2026-03-10")

        ernte = nach_typ["ERNTE"]
        assert Decimal(str(ernte[0]["quantity"])) == Decimal("1500")
        assert ernte[0]["movement_date"].startswith("2026-03-24")

        verlust = nach_typ["VERLUST"]
        assert Decimal(str(verlust[0]["quantity"])) == Decimal("-100")

    def test_ohne_lagerbewegungen_keine_buchungen(self, client, zwei_zeilen):
        _upload(client, "/api/v1/imports/grow-batches/commit", _xlsx(zwei_zeilen),
                lagerbewegungen=False)
        assert _bewegungen_im_maerz(client) == []

    def test_fehlerhafte_datei_wird_komplett_abgelehnt(self, client, zwei_zeilen):
        zwei_zeilen[1]["sorte"] = "Fantasia"
        r = _upload(client, "/api/v1/imports/grow-batches/commit", _xlsx(zwei_zeilen))

        assert r.status_code == 400, r.text
        assert _batches(client) == []


class TestRollback:
    """R3.6: Ein Lauf lässt sich in einem Schritt zurückrollen."""

    def test_rollback_entfernt_chargen_und_bewegungen(self, client, zwei_zeilen):
        run_id = _upload(client, "/api/v1/imports/grow-batches/commit",
                         _xlsx(zwei_zeilen)).json()["import_run_id"]

        r = client.delete(f"/api/v1/imports/runs/{run_id}")

        assert r.status_code == 200, r.text
        assert _batches(client) == []
        assert _bewegungen_im_maerz(client) == []

    def test_rollback_nur_einmal(self, client, zwei_zeilen):
        run_id = _upload(client, "/api/v1/imports/grow-batches/commit",
                         _xlsx(zwei_zeilen)).json()["import_run_id"]
        client.delete(f"/api/v1/imports/runs/{run_id}")

        assert client.delete(f"/api/v1/imports/runs/{run_id}").status_code == 409

    def test_rollback_blockiert_bei_folgebelegen(self, client, zwei_zeilen):
        """Hängt an einer importierten Charge inzwischen eine echte Ernte,
        darf der Lauf nicht mehr verschwinden."""
        run_id = _upload(client, "/api/v1/imports/grow-batches/commit",
                         _xlsx(zwei_zeilen)).json()["import_run_id"]

        r = client.post("/api/v1/production/harvests", json={
            "grow_batch_id": _batches(client)[0]["id"],
            "ernte_datum": date.today().isoformat(),
            "menge_gramm": 500,
        })
        assert r.status_code in (200, 201), r.text

        assert client.delete(f"/api/v1/imports/runs/{run_id}").status_code == 409


class TestChargenVorschlag:
    """R4.3: der Forecast liefert Grid-kompatible Vorschlagszeilen —
    dieselbe Form wie der Import, damit das Chargen-Grid sie vorbefüllen kann."""

    def test_vorschlaege_der_zielwoche_als_grid_zeilen(self, client, db, sample_seed):
        from uuid import UUID
        from app.models.forecast import Forecast, ProductionSuggestion, SuggestionStatus

        forecast = Forecast(seed_id=UUID(sample_seed["id"]),
                            datum=date.today(), horizont_tage=7,
                            prognostizierte_menge=100, effektive_menge=100, modell_typ="MANUAL")
        db.add(forecast)
        db.flush()
        db.add(ProductionSuggestion(
            forecast_id=forecast.id, seed_id=UUID(sample_seed["id"]),
            empfohlene_trays=6, aussaat_datum=date(2026, 9, 7),   # Montag der Zielwoche
            erwartete_ernte_datum=date(2026, 9, 18),
            status=SuggestionStatus.VORGESCHLAGEN,
        ))
        db.add(ProductionSuggestion(  # andere Woche → draußen
            forecast_id=forecast.id, seed_id=UUID(sample_seed["id"]),
            empfohlene_trays=2, aussaat_datum=date(2026, 9, 21),
            erwartete_ernte_datum=date(2026, 10, 2),
            status=SuggestionStatus.VORGESCHLAGEN,
        ))
        db.commit()

        r = client.get("/api/v1/production/grow-batch-suggestions",
                       params={"target_week": "2026-09-09"})  # Mittwoch derselben Woche

        assert r.status_code == 200, r.text
        zeilen = r.json()
        assert len(zeilen) == 1
        assert zeilen[0]["sorte"] == sample_seed["name"]
        assert zeilen[0]["tray_anzahl"] == 6
        assert zeilen[0]["aussaat_datum"] == "2026-09-07"


class TestGridZeilen:
    """R4.1/R4.2: das Chargen-Grid schickt JSON-Zeilen statt einer Datei —
    gleiche Validierung, gleiche Transaktion, gleicher Lauf."""

    def test_commit_rows_legt_chargen_an(self, client, sample_seed):
        r = client.post("/api/v1/imports/grow-batches/commit-rows", json={
            "zeilen": [
                {"sorte": sample_seed["name"], "aussaat_datum": "2026-09-07",
                 "tray_anzahl": 4, "saatgut_gramm": 120},
                {"sorte": sample_seed["name"], "aussaat_datum": "2026-09-07",
                 "tray_anzahl": 2, "saatgut_gramm": 60,
                 "externe_chargennummer": "GRID-2"},
            ],
            "lagerbewegungen": True,
        })
        assert r.status_code == 201, r.text
        assert r.json()["created"] == 2
        assert len(_batches(client)) == 2

    def test_validate_rows_meldet_fehler_mit_zeile(self, client, sample_seed):
        r = client.post("/api/v1/imports/grow-batches/validate-rows", json={
            "zeilen": [{"sorte": "Fantasia", "aussaat_datum": "2026-09-07", "tray_anzahl": 1}],
        })
        assert r.status_code == 200, r.text
        assert r.json()["zeilen"][0]["status"] == "FEHLER"
        assert r.json()["zeilen"][0]["zeile"] == 1
