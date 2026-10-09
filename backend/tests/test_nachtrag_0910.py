"""Nachtrag 09.10.2026 — Gernots Feedback vom 09.10. (Word-Kommentare und
Excel-Sammelrechnung).

Gemeinsame Testdatei aller Abschnitte. Helfer und Klassen tragen ein
Abschnitts-Präfix (_d_/TestD für Abschnitt D usw.): ein gleichnamiger Helfer
würde still ersetzt. Jeder Abschnitt bringt seine Importe selbst mit.
"""


# ============================================================
# D — DATEV-Export im Kontenrahmen des Mandanten (SKR03 | SKR04)
#
# Gernot (09.10.2026): MingaGreens bucht mit DATEV Mittelstand Faktura mit
# Rechnungswesen und DATEV Unternehmen online im SKR04. Der Export kannte nur
# SKR03. Einstellung DATEV_KONTENRAHMEN (ohne Eintrag SKR03), eine
# Kontentabelle je Rahmen (app.services.kontenrahmen). Festgeschriebene
# Rechnungen werden nie umgeschrieben: der Export bildet die Standard-
# Erlöskonten aus Steuersatz und Rahmen ab, ein Sonderkonto bleibt.
# Kontierung vom Steuerberater zu bestätigen.
# ============================================================
import csv
import io
import uuid
from datetime import date
from decimal import Decimal

import pytest

from tests.conftest import TestingSessionLocal

_D_KOPF = [
    "Umsatz", "Soll/Haben", "WKZ", "Kurs", "Basisumsatz",
    "Konto", "Gegenkonto", "BU-Schlüssel", "Belegdatum",
    "Belegfeld 1", "Belegfeld 2", "Buchungstext",
]

#: Ware zu 7 %, Pfandkiste zu 19 % (wie RE-00002):
#: 10 × 2,50 = 25,00 + 1,75 USt = 26,75 | 2 × 3,00 = 6,00 + 1,14 USt = 7,14
_D_GEMISCHT = [
    ("Erbsen-Schale", 10, "2.50", "REDUZIERT"),
    ("Pfandkiste 6er", 2, "3.00", "STANDARD"),
]


def _d_rahmen(client, wert):
    return client.patch("/api/v1/admin/settings", json={"DATEV_KONTENRAHMEN": wert})


def _d_setze_rahmen(client, wert):
    r = _d_rahmen(client, wert)
    assert r.status_code == 200, r.text


def _d_einstellung(client, key):
    r = client.get("/api/v1/admin/settings")
    assert r.status_code == 200, r.text
    return next(s for s in r.json() if s["key"] == key)


def _d_kunde(client, name="Ökoring Testkunde", konto="10008"):
    r = client.post("/api/v1/sales/customers",
                    json={"name": name, "typ": "HANDEL", "datev_account": konto})
    assert r.status_code == 201, r.text
    return r.json()


def _d_rechnung(client, kunde, positionen, finalisieren=True):
    """positionen: (Beschreibung, Menge, Preis, Satz[, Sonderkonto])."""
    r = client.post("/api/v1/invoices", json={
        "customer_id": kunde["id"], "invoice_date": date.today().isoformat(),
    })
    assert r.status_code == 201, r.text
    rechnung = r.json()
    for beschreibung, menge, preis, satz, *sonderkonto in positionen:
        zeile = {"description": beschreibung, "quantity": menge, "unit": "STK",
                 "unit_price": preis, "tax_rate": satz}
        if sonderkonto:
            zeile["buchungskonto"] = sonderkonto[0]
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/lines", json=zeile)
        assert r.status_code == 201, r.text
    if finalisieren:
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/finalize")
        assert r.status_code == 200, r.text
        rechnung = r.json()
    return rechnung


def _d_positionen(client, rechnung):
    r = client.get(f"/api/v1/invoices/{rechnung['id']}")
    assert r.status_code == 200, r.text
    return sorted(r.json()["lines"], key=lambda l: l["position"])


def _d_als_exportiert(rechnung_id):
    from app.models.invoice import Invoice
    with TestingSessionLocal() as db:
        db.get(Invoice, uuid.UUID(rechnung_id)).datev_exported = True
        db.commit()


class TestDKontentabelle:
    """Eine Tabelle je Rahmen, SKR03 = Bestand."""

    def test_skr03_ist_der_bisherige_bestand(self):
        from app.models.invoice import STANDARD_ACCOUNTS
        from app.services.kontenrahmen import SACHKONTEN
        assert SACHKONTEN["SKR03"] == STANDARD_ACCOUNTS == {
            "erloes_7": "8300", "erloes_19": "8400", "erloes_steuerfrei": "8100",
            "forderungen": "1400", "bank": "1200", "kasse": "1000",
        }

    def test_skr04_konten(self):
        from app.services.kontenrahmen import SACHKONTEN
        assert SACHKONTEN["SKR04"] == {
            "erloes_7": "4300", "erloes_19": "4400", "erloes_steuerfrei": "4100",
            "forderungen": "1200", "bank": "1800", "kasse": "1600",
        }

    def test_erloeskonto_je_satz_und_rahmen(self):
        from app.models.enums import TaxRate
        from app.services.kontenrahmen import erloeskonto_fuer
        saetze = (TaxRate.REDUZIERT, TaxRate.STANDARD, TaxRate.STEUERFREI)
        assert [erloeskonto_fuer(s, "SKR03") for s in saetze] == ["8300", "8400", "8100"]
        assert [erloeskonto_fuer(s, "SKR04") for s in saetze] == ["4300", "4400", "4100"]

    def test_standardkonten_beider_rahmen_folgen_dem_satz(self):
        from app.services.kontenrahmen import ist_standard_erloeskonto
        for konto in (None, "", "8300", "8400", "8100", "4300", "4400", "4100"):
            assert ist_standard_erloeskonto(konto), konto
        for konto in ("8338", "8301", "4337", "1200"):
            assert not ist_standard_erloeskonto(konto), konto

    def test_sonderkonto_aus_dem_anderen_rahmen(self):
        from app.services.kontenrahmen import sonderkonto_pruefen
        sonderkonto_pruefen("8338", "SKR03")
        sonderkonto_pruefen("4337", "SKR04")
        sonderkonto_pruefen("8300", "SKR04")   # Standardkonto: folgt dem Satz
        sonderkonto_pruefen(None, "SKR04")
        with pytest.raises(ValueError, match="8338 passt nicht zum Kontenrahmen SKR04"):
            sonderkonto_pruefen("8338", "SKR04")
        with pytest.raises(ValueError, match="4337 passt nicht zum Kontenrahmen SKR03"):
            sonderkonto_pruefen("4337", "SKR03")


class TestDEinstellung:
    """DATEV_KONTENRAHMEN über die Admin-Einstellungen, mit Prüfung."""

    def test_ohne_eintrag_gilt_skr03(self, client):
        from app.services.kontenrahmen import kontenrahmen
        assert _d_einstellung(client, "DATEV_KONTENRAHMEN")["source"] == "none"
        with TestingSessionLocal() as db:
            assert kontenrahmen(db) == "SKR03"

    def test_umgebungsvariablen_wirken_nicht(self, client, monkeypatch):
        """Eine Container-Variable gälte für alle Mandanten."""
        from app.services.kontenrahmen import export_sperre, kontenrahmen
        monkeypatch.setenv("DATEV_KONTENRAHMEN", "SKR04")
        monkeypatch.setenv("DATEV_EXPORT_SPERRE", "aus der Umgebung")
        with TestingSessionLocal() as db:
            assert kontenrahmen(db) == "SKR03"
            assert export_sperre(db) is None

    def test_skr04_setzen_schreibweise_egal(self, client):
        from app.services.kontenrahmen import kontenrahmen
        r = _d_rahmen(client, " skr04 ")
        assert r.status_code == 200, r.text
        assert _d_einstellung(client, "DATEV_KONTENRAHMEN")["value"] == "SKR04"
        with TestingSessionLocal() as db:
            assert kontenrahmen(db) == "SKR04"

    def test_unbekannter_rahmen_422(self, client):
        r = _d_rahmen(client, "SKR05")
        assert r.status_code == 422, r.text
        assert "SKR03 oder SKR04 erwartet" in r.json()["detail"]
        assert _d_einstellung(client, "DATEV_KONTENRAHMEN")["source"] == "none"

    def test_leeren_ist_kein_stiller_wechsel(self, client):
        _d_setze_rahmen(client, "SKR04")
        for leer in ("", None):
            r = _d_rahmen(client, leer)
            assert r.status_code == 422, r.text
            assert "leeren nicht möglich — SKR03 oder SKR04 angeben" in r.json()["detail"]
        assert _d_einstellung(client, "DATEV_KONTENRAHMEN")["value"] == "SKR04"

    def test_smtp_karte_speichert_weiter(self, client):
        """Die SMTP-Karte (Settings.tsx) schickt beim Speichern JEDE bekannte
        Einstellung mit dem geladenen Wert zurück, ungesetzte als null. Das darf
        weder scheitern noch den Rahmen umstellen — ohne und mit Eintrag."""
        def wie_die_karte():
            daten = client.get("/api/v1/admin/settings").json()
            return {s["key"]: (s["value"] or None) for s in daten
                    if not (s["is_secret"] and s["value"] == "***")}

        r = client.patch("/api/v1/admin/settings", json=wie_die_karte())
        assert r.status_code == 200, r.text
        assert _d_einstellung(client, "DATEV_KONTENRAHMEN")["source"] == "none"

        _d_setze_rahmen(client, "SKR04")
        r = client.patch("/api/v1/admin/settings", json=wie_die_karte())
        assert r.status_code == 200, r.text
        assert _d_einstellung(client, "DATEV_KONTENRAHMEN")["value"] == "SKR04"

    def test_wechsel_nach_exportierter_rechnung_gesperrt(self, client):
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        _d_als_exportiert(rechnung["id"])

        r = _d_rahmen(client, "SKR04")

        assert r.status_code == 422, r.text
        assert "nach dem ersten DATEV-Export nicht mehr änderbar" in r.json()["detail"]
        assert _d_einstellung(client, "DATEV_KONTENRAHMEN")["source"] == "none"
        # Den geltenden Rahmen ausdrücklich speichern ist kein Wechsel
        assert _d_rahmen(client, "SKR03").status_code == 200

    def test_wechsel_nach_exportierter_zahlung_gesperrt(self, client):
        from app.models.invoice import Payment
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/payments", json={
            "amount": "33.89", "payment_date": date.today().isoformat()})
        assert r.status_code == 201, r.text
        with TestingSessionLocal() as db:
            db.get(Payment, uuid.UUID(r.json()["id"])).datev_exported = True
            db.commit()

        assert _d_rahmen(client, "SKR04").status_code == 422

    def test_sperrgrund_setzen_und_aufheben(self, client):
        from app.services.kontenrahmen import export_sperre
        grund = "Kontierung SKR04 vom Steuerberater noch nicht bestätigt"
        r = client.patch("/api/v1/admin/settings", json={"DATEV_EXPORT_SPERRE": grund})
        assert r.status_code == 200, r.text
        with TestingSessionLocal() as db:
            assert export_sperre(db) == grund

        r = client.patch("/api/v1/admin/settings", json={"DATEV_EXPORT_SPERRE": ""})
        assert r.status_code == 200, r.text
        with TestingSessionLocal() as db:
            assert export_sperre(db) is None


class TestDKontierungBeimAnlegen:
    """Neue Positionen und der Satzwechsel im Entwurf nehmen das Konto des
    Rahmens. Gespeichert ist es nur ein Vorschlag — maßgeblich bildet der
    Export ab (TestDExport)."""

    def test_skr03_wie_bisher(self, client):
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT, finalisieren=False)
        assert [p["buchungskonto"] for p in _d_positionen(client, rechnung)] == ["8300", "8400"]

    def test_skr04_neue_positionen(self, client):
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT + [
            ("Kresse Export", 1, "5.00", "STEUERFREI"),
        ], finalisieren=False)
        assert [p["buchungskonto"] for p in _d_positionen(client, rechnung)] == ["4300", "4400", "4100"]

    def test_satzwechsel_im_entwurf_skr04(self, client):
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client), [("Pfandkiste", 1, "10.00", "REDUZIERT")],
                               finalisieren=False)
        zeile = _d_positionen(client, rechnung)[0]
        assert zeile["buchungskonto"] == "4300"
        url = f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}"

        r = client.patch(url, json={"tax_rate": "STANDARD"})

        assert r.status_code == 200, r.text
        assert r.json()["buchungskonto"] == "4400"
        assert client.patch(url, json={"tax_rate": "STEUERFREI"}).json()["buchungskonto"] == "4100"

    def test_entwurf_aus_der_skr03_zeit_folgt_dem_neuen_rahmen(self, client):
        rechnung = _d_rechnung(client, _d_kunde(client), [("Pfandkiste", 1, "10.00", "REDUZIERT")],
                               finalisieren=False)
        zeile = _d_positionen(client, rechnung)[0]
        assert zeile["buchungskonto"] == "8300"
        _d_setze_rahmen(client, "SKR04")

        r = client.patch(f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}",
                         json={"tax_rate": "STANDARD"})

        assert r.status_code == 200, r.text
        assert r.json()["buchungskonto"] == "4400"

    def test_entwurf_aus_der_skr04_zeit_folgt_skr03(self, client):
        """Auch 4300 gilt als Standardkonto (vor dem ersten Export ist der
        Rahmen noch wählbar)."""
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client), [("Pfandkiste", 1, "10.00", "REDUZIERT")],
                               finalisieren=False)
        zeile = _d_positionen(client, rechnung)[0]
        assert zeile["buchungskonto"] == "4300"
        _d_setze_rahmen(client, "SKR03")

        r = client.patch(f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}",
                         json={"tax_rate": "STANDARD"})

        assert r.json()["buchungskonto"] == "8400"

    def test_ausdrueckliches_standardkonto_folgt_dem_satz(self, client):
        """Ein mitgeschicktes Standardkonto (z. B. 8400 aus einem alten Client)
        ist kein Sonderkonto: es folgt Satz und Rahmen."""
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client),
                               [("Erbsen-Schale", 1, "2.50", "REDUZIERT", "8400")], finalisieren=False)
        assert [p["buchungskonto"] for p in _d_positionen(client, rechnung)] == ["4300"]

    def test_sonderkonto_des_rahmens_bleibt(self, client):
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client),
                               [("Kresse Sonderaktion", 1, "10.00", "REDUZIERT", "4337")],
                               finalisieren=False)
        zeile = _d_positionen(client, rechnung)[0]
        assert zeile["buchungskonto"] == "4337"
        r = client.patch(f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}",
                         json={"tax_rate": "STANDARD"})
        assert r.json()["buchungskonto"] == "4337"

    def test_sonderkonto_aus_dem_anderen_rahmen_400(self, client):
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client), [], finalisieren=False)

        r = client.post(f"/api/v1/invoices/{rechnung['id']}/lines", json={
            "description": "Kresse", "quantity": 1, "unit": "STK", "unit_price": "10.00",
            "tax_rate": "REDUZIERT", "buchungskonto": "8338"})

        assert r.status_code == 400, r.text
        assert r.json()["detail"] == (
            "Erlöskonto 8338 passt nicht zum Kontenrahmen SKR04 "
            "(Kontenklasse 8 ist dort kein Erlöskonto)")
        assert _d_positionen(client, rechnung) == []


def _d_export_roh(client, zahlungen=False, download=False):
    pfad = "/api/v1/invoices/datev-export" + ("/download" if download else "")
    return client.post(pfad, json={
        "from_date": date.today().isoformat(), "to_date": date.today().isoformat(),
        "include_payments": zahlungen,
    })


def _d_export(client, zahlungen=False):
    r = _d_export_roh(client, zahlungen)
    assert r.status_code == 200, r.text
    daten = r.json()
    zeilen = list(csv.reader(io.StringIO(daten["csv_content"]), delimiter=";"))
    return daten, zeilen[0], zeilen[1:]


def _d_zeile(betrag, sh, konto, gegenkonto, belegnr, text, belegfeld2=""):
    """Eine erwartete Buchungszeile, Spalte für Spalte in Kopf-Reihenfolge."""
    return [betrag, sh, "EUR", "", "", konto, gegenkonto, "",
            date.today().strftime("%d%m"), belegnr, belegfeld2, text]


def _d_exportiert(rechnung_id):
    from app.models.invoice import Invoice
    with TestingSessionLocal() as db:
        return db.get(Invoice, uuid.UUID(rechnung_id)).datev_exported


def _d_zahlung(client, rechnung, betrag, methode="UEBERWEISUNG", referenz=None):
    body = {"amount": betrag, "payment_date": date.today().isoformat(), "payment_method": methode}
    if referenz:
        body["reference"] = referenz
    r = client.post(f"/api/v1/invoices/{rechnung['id']}/payments", json=body)
    assert r.status_code == 201, r.text


class TestDExportSkr04:
    """Spaltengenau im SKR04: Erlöse 4300/4400, Bank 1800, Kasse 1600."""

    def test_gemischte_rechnung_spaltengenau(self, client):
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        nr = rechnung["invoice_number"]

        daten, kopf, zeilen = _d_export(client)

        assert kopf == _D_KOPF
        assert zeilen == [
            _d_zeile("26,75", "S", "10008", "4300", nr, "Rechnung 7 % Ökoring Testkunde"),
            _d_zeile("7,14", "S", "10008", "4400", nr, "Rechnung 19 % Ökoring Testkunde"),
        ]
        assert daten["record_count"] == 2
        assert Decimal(str(daten["total_amount"])) == Decimal("33.89")

    def test_bestandsrechnung_wird_abgebildet_nicht_umgeschrieben(self, client):
        """GoBD: die Rechnung aus der SKR03-Zeit behält 8300/8400 an ihren
        Positionen; erst der Export bildet sie auf SKR04 ab."""
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        nr = rechnung["invoice_number"]
        vorher = client.get(f"/api/v1/invoices/{rechnung['id']}").json()
        assert [l["buchungskonto"] for l in vorher["lines"]] == ["8300", "8400"]
        _d_setze_rahmen(client, "SKR04")

        _, _, zeilen = _d_export(client)

        assert zeilen == [
            _d_zeile("26,75", "S", "10008", "4300", nr, "Rechnung 7 % Ökoring Testkunde"),
            _d_zeile("7,14", "S", "10008", "4400", nr, "Rechnung 19 % Ökoring Testkunde"),
        ]
        nachher = client.get(f"/api/v1/invoices/{rechnung['id']}").json()
        assert nachher["lines"] == vorher["lines"]
        for feld in ("subtotal", "tax_amount", "total", "status", "invoice_number"):
            assert nachher[feld] == vorher[feld], feld

    def test_storno_spaltengenau(self, client):
        """Storno einer Bestandsrechnung nach dem Wechsel: die Stornorechnung
        spiegelt die Konten des Originals (8300/8400), beide landen auf
        4300/4400 und heben sich auf."""
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        _d_setze_rahmen(client, "SKR04")
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/cancel",
                        json={"reason": "Pfand mit 7 % berechnet"})
        assert r.status_code == 200, r.text
        storno = r.json()["credit_note"]
        nr, snr = rechnung["invoice_number"], storno["invoice_number"]
        assert [p["buchungskonto"] for p in _d_positionen(client, storno)] == ["8300", "8400"]

        daten, _, zeilen = _d_export(client)

        assert zeilen == [
            _d_zeile("26,75", "S", "10008", "4300", nr, "Rechnung 7 % Ökoring Testkunde"),
            _d_zeile("7,14", "S", "10008", "4400", nr, "Rechnung 19 % Ökoring Testkunde"),
            _d_zeile("26,75", "H", "10008", "4300", snr, f"Storno {nr} 7 % Ökoring Testkunde"),
            _d_zeile("7,14", "H", "10008", "4400", snr, f"Storno {nr} 19 % Ökoring Testkunde"),
        ]
        assert Decimal(str(daten["total_amount"])) == Decimal("0.00")

    def test_zahlungen_spaltengenau(self, client):
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        nr = rechnung["invoice_number"]
        _d_zahlung(client, rechnung, "20.00", referenz="Überweisung 1")
        _d_zahlung(client, rechnung, "13.89", methode="BAR")

        daten, _, zeilen = _d_export(client, zahlungen=True)

        assert zeilen[:2] == [
            _d_zeile("26,75", "S", "10008", "4300", nr, "Rechnung 7 % Ökoring Testkunde"),
            _d_zeile("7,14", "S", "10008", "4400", nr, "Rechnung 19 % Ökoring Testkunde"),
        ]
        assert sorted(zeilen[2:]) == sorted([
            _d_zeile("20,00", "S", "1800", "10008", nr, "Zahlung Ökoring Testkunde", "Überweisung 1"),
            _d_zeile("13,89", "S", "1600", "10008", nr, "Zahlung Ökoring Testkunde"),
        ])
        assert daten["record_count"] == 4

    def test_ruecklastschrift_auf_die_bank_des_rahmens(self, client):
        """SEPA (B10): Einzug S, Rücklastschrift als Gegenbuchung H — beide 1800."""
        from app.models.invoice import Payment, PaymentMethod
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        nr = rechnung["invoice_number"]
        with TestingSessionLocal() as db:
            for betrag, referenz in (("33.89", "MANDAT-1"), ("-33.89", "Rücklastschrift MANDAT-1")):
                db.add(Payment(invoice_id=uuid.UUID(rechnung["id"]), payment_date=date.today(),
                               amount=Decimal(betrag), payment_method=PaymentMethod.LASTSCHRIFT,
                               reference=referenz))
            db.commit()

        _, _, zeilen = _d_export(client, zahlungen=True)

        assert sorted(zeilen[2:]) == [
            _d_zeile("33,89", "H", "1800", "10008", nr, "Zahlung Ökoring Testkunde",
                     "Rücklastschrift MANDAT-1"),
            _d_zeile("33,89", "S", "1800", "10008", nr, "Zahlung Ökoring Testkunde", "MANDAT-1"),
        ]

    def test_leergutbeleg_mit_minderung(self, client):
        """Paket 3, Q6: Leergutbeleg (Pfand 19 %) mit negativem Saldo bucht H
        auf das 19-%-Konto des Rahmens — auch mit 8400 aus der SKR03-Zeit."""
        from app.models.invoice import Invoice, InvoiceLine, TaxRate
        rechnung = _d_rechnung(client, _d_kunde(client), [], finalisieren=False)
        with TestingSessionLocal() as db:
            beleg = db.get(Invoice, uuid.UUID(rechnung["id"]))
            beleg.beleg_art = "LEERGUT"
            for nr_pos, (text, menge) in enumerate(
                (("Leergut ausgegeben: IFCO", "1"), ("Leergut zurückgenommen: IFCO", "-4")), start=1
            ):
                zeile = InvoiceLine(
                    invoice_id=beleg.id, position=nr_pos, description=text,
                    quantity=Decimal(menge), unit="STK", unit_price=Decimal("3.00"),
                    discount_percent=Decimal("0"),
                    tax_rate=TaxRate.STANDARD, is_deposit=True, buchungskonto="8400",
                )
                zeile.calculate_line_total()
                db.add(zeile)
            db.commit()
        _d_setze_rahmen(client, "SKR04")
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/finalize")
        assert r.status_code == 200, r.text
        beleg = r.json()
        assert Decimal(str(beleg["total"])) == Decimal("-10.71")

        _, _, zeilen = _d_export(client)

        assert zeilen == [
            _d_zeile("10,71", "H", "10008", "4400", beleg["invoice_number"],
                     "Rechnung 19 % Ökoring Testkunde"),
        ]

    def test_sonderkonto_des_rahmens_bleibt(self, client):
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client), [
            ("Erbsen-Schale", 10, "2.50", "REDUZIERT"),
            ("Kresse Sonderaktion", 1, "10.00", "REDUZIERT", "4337"),
        ])
        nr = rechnung["invoice_number"]

        _, _, zeilen = _d_export(client)

        assert zeilen == [
            _d_zeile("26,75", "S", "10008", "4300", nr, "Rechnung 7 % Ökoring Testkunde"),
            _d_zeile("10,70", "S", "10008", "4337", nr, "Rechnung 7 % Ökoring Testkunde"),
        ]

    def test_sonderkonto_aus_skr03_bricht_den_export_ab(self, client):
        """Ein SKR03-Sonderkonto lässt sich nicht abbilden. Statt es still in
        den SKR04-Bestand zu schreiben, bricht der Export ab und markiert nichts."""
        kunde = _d_kunde(client)
        sonder = _d_rechnung(client, kunde, [("Kresse Sonderaktion", 1, "10.00", "REDUZIERT", "8338")])
        normal = _d_rechnung(client, kunde, _D_GEMISCHT)
        _d_setze_rahmen(client, "SKR04")

        r = _d_export_roh(client)

        assert r.status_code == 409, r.text
        assert r.json()["detail"] == (
            "DATEV-Export abgebrochen, nichts exportiert: Sonderkonten passen nicht "
            f"zum Kontenrahmen SKR04 — {sonder['invoice_number']} Pos. 1 (8338). "
            "Kontierung mit dem Steuerberater klären.")
        assert _d_export_roh(client, download=True).status_code == 409
        assert _d_exportiert(sonder["id"]) is False
        assert _d_exportiert(normal["id"]) is False


class TestDExportSkr03:
    """Regression: ausdrücklich SKR03 = Bestand (8300/8400, Bank 1200, Kasse 1000)."""

    def test_spaltengenau_mit_zahlungen(self, client):
        _d_setze_rahmen(client, "SKR03")
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        nr = rechnung["invoice_number"]
        _d_zahlung(client, rechnung, "20.00", referenz="Überweisung 1")
        _d_zahlung(client, rechnung, "13.89", methode="BAR")

        _, _, zeilen = _d_export(client, zahlungen=True)

        assert zeilen[:2] == [
            _d_zeile("26,75", "S", "10008", "8300", nr, "Rechnung 7 % Ökoring Testkunde"),
            _d_zeile("7,14", "S", "10008", "8400", nr, "Rechnung 19 % Ökoring Testkunde"),
        ]
        assert sorted(zeilen[2:]) == sorted([
            _d_zeile("20,00", "S", "1200", "10008", nr, "Zahlung Ökoring Testkunde", "Überweisung 1"),
            _d_zeile("13,89", "S", "1000", "10008", nr, "Zahlung Ökoring Testkunde"),
        ])


_D_GRUND = "Kontierung SKR04 vom Steuerberater noch nicht bestätigt"


def _d_sperren(client, grund):
    r = client.patch("/api/v1/admin/settings", json={"DATEV_EXPORT_SPERRE": grund})
    assert r.status_code == 200, r.text


def _d_als(*rollen):
    """Login mit genau diesen Rollen; das client-Fixture räumt auf."""
    from app.api.deps import get_current_user
    from app.main import app

    async def override():
        return {"id": "123e4567-e89b-12d3-a456-426614174000", "username": "d",
                "email": "d@example.com", "roles": list(rollen)}
    app.dependency_overrides[get_current_user] = override


class TestDSperre:
    """Bis der Steuerberater die Kontierung bestätigt, bleibt der Export zu."""

    def test_gesperrt_409_und_nichts_markiert(self, client):
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        _d_sperren(client, _D_GRUND)

        for download in (False, True):
            r = _d_export_roh(client, download=download)
            assert r.status_code == 409, r.text
            assert r.json()["detail"] == f"DATEV-Export gesperrt: {_D_GRUND}"
        assert _d_exportiert(rechnung["id"]) is False

    def test_nach_freigabe_wieder_frei(self, client):
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        _d_sperren(client, _D_GRUND)
        _d_sperren(client, "")

        _, _, zeilen = _d_export(client)

        assert len(zeilen) == 2
        assert _d_exportiert(rechnung["id"]) is True

    def test_sperre_gilt_auch_im_service(self, client):
        from app.services.datev_service import DatevExportAbgelehnt, DatevService
        _d_sperren(client, _D_GRUND)
        with TestingSessionLocal() as db:
            with pytest.raises(DatevExportAbgelehnt, match="DATEV-Export gesperrt"):
                DatevService(db).export_invoices_csv(date.today(), date.today())


class TestDEinstellungenFuerDenDialog:
    """GET /invoices/datev-export/einstellungen — Rahmen, Konten, Sperre."""

    _URL = "/api/v1/invoices/datev-export/einstellungen"

    def test_ohne_eintrag_skr03_und_frei(self, client):
        r = client.get(self._URL)
        assert r.status_code == 200, r.text
        assert r.json() == {
            "kontenrahmen": "SKR03",
            "konten": [
                {"bezeichnung": "Erlöse 7 %", "konto": "8300"},
                {"bezeichnung": "Erlöse 19 %", "konto": "8400"},
                {"bezeichnung": "Erlöse steuerfrei", "konto": "8100"},
                {"bezeichnung": "Bank (Zahlungen außer bar)", "konto": "1200"},
                {"bezeichnung": "Kasse (Barzahlungen)", "konto": "1000"},
            ],
            "sperrgrund": None,
        }

    def test_skr04_gesperrt(self, client):
        _d_setze_rahmen(client, "SKR04")
        _d_sperren(client, _D_GRUND)

        daten = client.get(self._URL).json()

        assert daten["kontenrahmen"] == "SKR04"
        assert [k["konto"] for k in daten["konten"]] == ["4300", "4400", "4100", "1800", "1600"]
        assert daten["sperrgrund"] == _D_GRUND

    def test_buchhaltung_liest_den_dialog_nicht_die_admin_einstellungen(self, client):
        """Darum ein eigener Endpunkt unter /invoices: /admin/settings ist nur
        für admin. Die Halle sieht weder Rechnungen noch DATEV."""
        _d_als("accounting")
        assert client.get(self._URL).status_code == 200
        assert client.get("/api/v1/admin/settings").status_code == 403
        _d_als("production_staff")
        assert client.get(self._URL).status_code == 403
# ============================================================================
# Abschnitt F — Firmendaten in den Einstellungen speichern auf dem Server
# (Spec 2026-10-08, „Offen (niedrig, 09.10.)" Punkte 1 und 2)
#
# Briefkopf und Fuß der Minga-Belege kommen aus den Belegvorlagen
# (document_templates.texts: header_text, footer_text). pdf_service nimmt je
# Block ENTWEDER den Vorlagentext ODER die Firmendaten (COMPANY_*), nie beide.
# F hält das mit Tests fest, maskiert die Firmendaten im PDF, prüft sie beim
# Speichern und grüßt in Beleg-Mails ohne Firmennamen mit dem Absendernamen.
# Helfer tragen das Präfix _f_, Klassen TestF1…TestF3.
# ============================================================================
import re as _f_re

import pytest

from tests.conftest import TestingSessionLocal
from tests.test_documents_preise import _pdf_text as _f_pdf_roh

_F_FIRMA = {
    "COMPANY_NAME": "Testfarm GmbH",
    "COMPANY_ADDRESS_LINE1": "Feldweg 1",
    "COMPANY_ADDRESS_LINE2": "80000 Muenchen",
    "COMPANY_USTID": "DE123456789",
    "COMPANY_STEUERNR": "143/163/41625",
    "COMPANY_PHONE": "+49 89 1234",
    "COMPANY_EMAIL": "info@testfarm.example",
    "COMPANY_WEBSITE": "www.testfarm.example",
    "COMPANY_BANK_NAME": "Volksbank Test",
    "COMPANY_IBAN": "DE89370400440532013000",
    "COMPANY_BIC": "COBADEFFXXX",
}
# Wie die Minga-Vorlagen: Briefkopf eine Zeile, Fuß mit Bank, Geschäftsführung,
# HRB und Öko-Kontrollnummer (Felder, die COMPANY_* gar nicht kennt).
_F_VORLAGE = {
    "header_text": "Testfarm GmbH · Feldweg 1 · 80000 Muenchen",
    "footer_text": (
        "Volksbank Test - IBAN DE89370400440532013000 - BIC COBADEFFXXX\n"
        "Geschaeftsfuehrung: Erika Muster | HRB 123456 | DE-OEKO-001"
    ),
}


@pytest.fixture
def _f_ohne_umgebung(monkeypatch):
    """Firmendaten und Absendername nur aus der Test-DB, nie vom Rechner."""
    for schluessel in (*_F_FIRMA, "EMAILS_FROM_NAME"):
        monkeypatch.delenv(schluessel, raising=False)


def _f_setze_db(**werte):
    """Setzt Einstellungen direkt in der DB (ohne die Prüfung von PATCH)."""
    from app.services.settings_service import set_setting
    with TestingSessionLocal() as db:
        for schluessel, wert in werte.items():
            set_setting(db, schluessel, wert)
        db.commit()


def _f_vorlage(client, belegart, texte=_F_VORLAGE):
    r = client.patch(f"/api/v1/document-templates/{belegart}", json={"texts": dict(texte)})
    assert r.status_code == 200, r.text


def _f_bestellung(client):
    r = client.post("/api/v1/sales/customers", json={"name": "Oekoring Handels GmbH", "typ": "HANDEL"})
    assert r.status_code in (200, 201), r.text
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": r.json()["id"],
        "requested_delivery_date": "2026-03-05",
        "lines": [{"product_name": "Erbsen-Schale", "quantity": 10, "unit": "STK",
                   "unit_price": 2.50, "tax_rate": "REDUZIERT"}],
    })
    assert r.status_code == 201, r.text
    bestellung = r.json()
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/confirm")
    assert r.status_code == 200, r.text
    return bestellung


def _f_rechnung(client):
    r = client.post(f"/api/v1/invoices/from-order/{_f_bestellung(client)['id']}")
    assert r.status_code == 201, r.text
    return r.json()


def _f_ab(client):
    r = client.post(f"/api/v1/sales/orders/{_f_bestellung(client)['id']}/confirmations", json={})
    assert r.status_code == 201, r.text
    return r.json()


def _f_rechnungs_pdf(client, rechnung) -> bytes:
    r = client.get(f"/api/v1/invoices/{rechnung['id']}/pdf")
    assert r.status_code == 200, r.text
    return r.content


def _f_text(pdf: bytes) -> str:
    """Alle Textstücke eines ReportLab-PDFs, mit Leerzeichen verbunden."""
    roh = _f_pdf_roh(pdf).decode("latin-1", errors="ignore")
    return " ".join(_f_re.findall(r"\((.*?)\) Tj", roh))


@pytest.fixture
def _f_mails(monkeypatch):
    """Beleg-Mails abfangen (belegversand.send_email), SMTP 'konfiguriert'."""
    from app.services.email_service import VersandErgebnis
    monkeypatch.setenv("SMTP_HOST", "smtp.farm.example")
    monkeypatch.setenv("SMTP_USER", "versand@farm.example")
    gesendet = []

    def senden(**kw):
        gesendet.append(kw)
        return VersandErgebnis(message_id=f"<f{len(gesendet)}@test.example>")

    monkeypatch.setattr("app.services.belegversand.send_email", senden)
    return gesendet


def _f_ab_senden(client, ab):
    return client.patch(f"/api/v1/sales/confirmations/{ab['id']}/send",
                        json={"to": ["einkauf@oekoring.example"]})


@pytest.mark.usefixtures("_f_ohne_umgebung")
class TestF1PdfBriefkopf:
    """Belegvorlage hat Vorrang; ohne Vorlagentext Firmendaten je Block einmal."""

    def test_mit_vorlage_bleibt_das_pdf_bytegleich(self, client):
        _f_vorlage(client, "RECHNUNG")
        rechnung = _f_rechnung(client)
        vorher = _f_rechnungs_pdf(client, rechnung)

        r = client.patch("/api/v1/admin/settings", json=_F_FIRMA)
        assert r.status_code == 200, r.text
        nachher = _f_rechnungs_pdf(client, rechnung)

        assert nachher == vorher
        text = _f_text(nachher)
        assert text.count("Testfarm GmbH") == 1, text
        assert text.count("DE89370400440532013000") == 1, text
        assert "Erika Muster" in text and "DE-OEKO-001" in text
        assert "DE123456789" not in text and "Minga Greens" not in text

    def test_ohne_vorlagentext_kopf_und_fuss_aus_den_firmendaten(self, client):
        rechnung = _f_rechnung(client)
        r = client.patch("/api/v1/admin/settings", json=_F_FIRMA)
        assert r.status_code == 200, r.text

        text = _f_text(_f_rechnungs_pdf(client, rechnung))

        # Kopf: Name, Straße, Ort. Fuß: Name, „Straße · Ort", Kontakt, Steuer, Bank.
        assert text.count("Testfarm GmbH") == 2, text
        assert text.count("Feldweg 1") == 2, text
        assert text.count("80000 Muenchen") == 2, text
        assert text.count("DE123456789") == 1, text
        assert text.count("DE89370400440532013000") == 1, text
        assert "Minga Greens" not in text

    def test_ab_nach_dem_setzen_der_firmendaten_erneut_sendbar(self, client, _f_mails):
        """Der Versandnachweis vergleicht die PDF-Prüfsumme (Paket 3, Q2): mit
        Vorlagentext ändern die Firmendaten das PDF nicht, also kein 409."""
        _f_vorlage(client, "AUFTRAGSBESTAETIGUNG")
        ab = _f_ab(client)
        assert _f_ab_senden(client, ab).status_code == 200

        assert client.patch("/api/v1/admin/settings", json=_F_FIRMA).status_code == 200
        r = _f_ab_senden(client, ab)

        assert r.status_code == 200, r.text
        erste, zweite = r.json()["dispatches"][:2]
        assert erste["attachment_sha256"] == zweite["attachment_sha256"]
        assert len(_f_mails) == 2

    def test_sonderzeichen_in_den_firmendaten_erscheinen_im_pdf(self, client):
        rechnung = _f_rechnung(client)
        _f_setze_db(COMPANY_NAME="Huber & Soehne <Bio> GmbH",
                    COMPANY_EMAIL="Servus <servus@farm.example>",
                    COMPANY_WEBSITE="feld>wald.example")

        text = _f_text(_f_rechnungs_pdf(client, rechnung))

        # ReportLab schreibt maskierte Zeichen als eigene Textstücke; _f_text
        # verbindet sie mit Leerzeichen — deshalb ohne Leerzeichen vergleichen.
        ohne_leer = text.replace(" ", "")
        assert "Huber&Soehne<Bio>GmbH" in ohne_leer, text
        assert "E-Mail:Servus<servus@farm.example>" in ohne_leer, text
        # ">" bleibt unmaskiert: ReportLab druckt es richtig, und als ein
        # Textstück wie vor F bleiben die PDF-Bytes solcher Werte gleich.
        assert "feld>wald.example" in text, text
def _f_als(rollen):
    from app.api.deps import get_current_user
    from app.main import app

    async def override():
        return {"id": "123e4567-e89b-12d3-a456-426614174077", "username": "f",
                "email": "f@farm.example", "roles": rollen}
    app.dependency_overrides[get_current_user] = override


@pytest.mark.usefixtures("_f_ohne_umgebung")
class TestF2FirmendatenSpeichern:
    """PATCH /admin/settings prüft die Firmendaten (Karte „Firmendaten")."""

    def _werte(self, client):
        r = client.get("/api/v1/admin/settings")
        assert r.status_code == 200, r.text
        return {s["key"]: s for s in r.json()}

    def test_alle_felder_speichern_normalisiert(self, client):
        r = client.patch("/api/v1/admin/settings", json={
            **_F_FIRMA,
            "COMPANY_NAME": "  Testfarm GmbH ",
            "COMPANY_IBAN": "de89 3704 0044 0532 0130 00",
            "COMPANY_BIC": "cobadeffxxx",
        })

        assert r.status_code == 200, r.text
        werte = self._werte(client)
        assert {k: werte[k]["value"] for k in _F_FIRMA} == _F_FIRMA
        assert {werte[k]["source"] for k in _F_FIRMA} == {"db"}
        # Labels wie in der Karte — sie stehen in den 422-Meldungen.
        assert [werte[k]["label"] for k in list(_F_FIRMA)[:5]] == [
            "Firmenname", "Straße und Hausnummer", "PLZ und Ort", "USt-IdNr.", "Steuernummer"]

    def test_falsche_iban_422_und_nichts_gespeichert(self, client):
        r = client.patch("/api/v1/admin/settings", json={
            "COMPANY_NAME": "Testfarm GmbH", "COMPANY_IBAN": "DE89370400440532013001"})

        assert r.status_code == 422, r.text
        assert r.json()["detail"] == "IBAN: IBAN-Prüfziffer stimmt nicht"
        assert self._werte(client)["COMPANY_NAME"]["source"] != "db"

    def test_falsche_bic_422(self, client):
        r = client.patch("/api/v1/admin/settings", json={"COMPANY_BIC": "COBA"})
        assert r.status_code == 422, r.text
        assert r.json()["detail"].startswith("BIC: BIC hat kein gültiges Format")

    @pytest.mark.parametrize("wert,meldung", [
        ("Testfarm\nGmbH", "nur eine Zeile"),
        ("x" * 201, "höchstens 200 Zeichen"),
        ("   ", "nur Leerzeichen"),
    ], ids=["zeilenumbruch", "zu_lang", "nur_leerzeichen"])
    def test_unbrauchbarer_firmenname_422(self, client, wert, meldung):
        r = client.patch("/api/v1/admin/settings", json={"COMPANY_NAME": wert})
        assert r.status_code == 422, r.text
        assert r.json()["detail"].startswith(f"Firmenname: {meldung}"), r.text

    def test_leerer_wert_loescht_wie_bisher(self, client):
        assert client.patch("/api/v1/admin/settings", json={"COMPANY_NAME": "Testfarm GmbH"}).status_code == 200
        assert client.patch("/api/v1/admin/settings", json={"COMPANY_NAME": ""}).status_code == 200
        assert self._werte(client)["COMPANY_NAME"]["has_value"] is False

    @pytest.mark.parametrize("rolle", ["sales", "accounting", "production_planner", "production_staff"])
    def test_nur_admin(self, client, rolle):
        _f_als([rolle])
        assert client.get("/api/v1/admin/settings").status_code == 403
        r = client.patch("/api/v1/admin/settings", json={"COMPANY_NAME": "Testfarm GmbH"})
        assert r.status_code == 403, r.text
@pytest.mark.usefixtures("_f_ohne_umgebung")
class TestF3MailGruss:
    """Grußformel: Firmenname, sonst Absendername (EMAILS_FROM_NAME), sonst „Ihr Team"."""

    def test_ohne_firmenname_gruesst_der_absendername(self, client, _f_mails):
        _f_setze_db(EMAILS_FROM_NAME="Testfarm Versand")
        assert _f_ab_senden(client, _f_ab(client)).status_code == 200
        assert _f_mails[0]["body"].endswith("Mit freundlichen Grüßen\nTestfarm Versand")

    def test_rechnungsmail_gruesst_den_absendernamen(self, client, _f_mails):
        _f_setze_db(EMAILS_FROM_NAME="Testfarm Versand")
        rechnung = _f_rechnung(client)
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/send",
                        json={"to": ["rechnung@oekoring.example"]})
        assert r.status_code == 200, r.text
        assert _f_mails[0]["body"].rstrip().endswith("Mit freundlichen Grüßen\nTestfarm Versand")

    def test_firmenname_vor_dem_absendernamen(self, client, _f_mails):
        _f_setze_db(EMAILS_FROM_NAME="Testfarm Versand", COMPANY_NAME="Testfarm GmbH")
        assert _f_ab_senden(client, _f_ab(client)).status_code == 200
        assert _f_mails[0]["body"].endswith("Mit freundlichen Grüßen\nTestfarm GmbH")

    def test_ohne_beides_ihr_team(self, client, _f_mails):
        assert _f_ab_senden(client, _f_ab(client)).status_code == 200
        assert _f_mails[0]["body"].endswith("Mit freundlichen Grüßen\nIhr Team")

    def test_betreff_ohne_firmenname_ohne_zusatz(self, client, _f_mails):
        """Der Absendername steht schon im Von-Feld — der Betreff bekommt
        seinen Zusatz weiter nur vom Firmennamen."""
        _f_setze_db(EMAILS_FROM_NAME="Testfarm Versand")
        ab = _f_ab(client)
        assert _f_ab_senden(client, ab).status_code == 200
        assert _f_mails[0]["subject"] == f"Auftragsbestätigung {ab['confirmation_number']}"


# ---------------------------------------- Abschnitt O: Belegordner (Frontend)

def _o_node(script):
    """Führt `script` mit Node im Ordner frontend aus, mit Attrappen für den
    gewählten Ordner (File System Access API), IndexedDB, window und document.

    Wie die Paket-3-Abnahme (_abnahme_frontend): TypeScript übersetzt das
    typescript-Paket des Frontends, relative Importe kommen aus den echten
    Dateien (belegordner.ts → dateiname.ts, belegpfad.ts). Ein Browser ist
    nicht nötig; die echte API prüft die Abnahme in Chrome.
    """
    import os
    import subprocess
    from pathlib import Path
    vorspann = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
function laden(datei, globals) {
    const code = ts.transpileModule(fs.readFileSync(datei, 'utf8'), {
        compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
    }).outputText;
    const exports = {};
    const ladenImport = (name) => {
        if (!name.startsWith('.')) return require(name);
        const basis = path.resolve(path.dirname(datei), name);
        const ziel = [basis + '.ts', basis + '.tsx'].find((k) => fs.existsSync(k));
        assert.ok(ziel, name);
        return laden(ziel, globals);
    };
    vm.runInNewContext(code, { exports, require: ladenImport, ...globals }, { filename: datei });
    return exports;
}
// Objekte aus dem vm-Kontext haben andere Prototypen: über JSON vergleichen
const gleich = (ist, soll) => assert.deepEqual(JSON.parse(JSON.stringify(ist ?? null)), soll);
const fehler = (name) => Object.assign(new Error(name), { name });
class Datei {
    constructor(name) { this.kind = 'file'; this.name = name; this.inhalt = null; }
    async createWritable() {
        const datei = this;
        let puffer = null;
        return {
            async write(b) { puffer = typeof b === 'string' ? b : await b.text(); },
            async close() { datei.inhalt = puffer; },
            async abort() {},
        };
    }
}
class Ordner {
    constructor(name) {
        this.kind = 'directory'; this.name = name; this.eintraege = new Map();
        this.erlaubnis = 'granted'; this.protokoll = [];
    }
    async getDirectoryHandle(name, o = {}) {
        let e = this.eintraege.get(name);
        if (!e) { if (!o.create) throw fehler('NotFoundError'); e = new Ordner(name); this.eintraege.set(name, e); }
        if (e.kind !== 'directory') throw fehler('TypeMismatchError');
        return e;
    }
    async getFileHandle(name, o = {}) {
        let e = this.eintraege.get(name);
        if (!e) { if (!o.create) throw fehler('NotFoundError'); e = new Datei(name); this.eintraege.set(name, e); }
        if (e.kind !== 'file') throw fehler('TypeMismatchError');
        return e;
    }
    async queryPermission() { return this.erlaubnis; }
    async requestPermission() {
        // wie Chromium: nur im Stand „fragen“ kommt eine Frage, sonst sofort der Stand
        if (this.erlaubnis !== 'prompt') return this.erlaubnis;
        this.protokoll.push('Freigabe angefragt');
        if (this.ohneKlick) throw fehler('SecurityError');
        this.erlaubnis = this.antwort || 'granted';
        return this.erlaubnis;
    }
    inhalt(pfad) {
        let h = this;
        for (const teil of pfad.split('/')) h = h && h.eintraege.get(teil);
        return h ? h.inhalt : undefined;
    }
}
function attrappeIndexedDB() {
    const daten = new Map();
    const spaeter = (r, tun) => { setTimeout(() => { r.result = tun(); if (r.onsuccess) r.onsuccess(); }, 0); return r; };
    const speicher = {
        get: (k) => spaeter({}, () => daten.get(k)),
        put: (v, k) => spaeter({}, () => { daten.set(k, v); return k; }),
        delete: (k) => spaeter({}, () => { daten.delete(k); }),
    };
    const db = { createObjectStore() {}, transaction: () => ({ objectStore: () => speicher }), close() {} };
    return {
        open() {
            const r = {};
            setTimeout(() => { r.result = db; if (r.onupgradeneeded) r.onupgradeneeded(); if (r.onsuccess) r.onsuccess(); }, 0);
            return r;
        },
    };
}
function umgebung(o = {}) {
    const w = { wurzel: new Ordner('Belege'), rueckfragen: [], antworten: [], downloads: [], meldungen: [] };
    const window = {
        isSecureContext: true,
        confirm: (text) => { w.rueckfragen.push(text); return w.antworten.length ? w.antworten.shift() : true; },
        URL: { createObjectURL: () => 'blob:o', revokeObjectURL() {} },
    };
    if (!o.ohneApi) window.showDirectoryPicker = async () => w.wurzel;
    const document = { createElement: () => { const a = { click() { w.downloads.push(a.download); } }; return a; } };
    w.bo = laden('src/services/belegordner.ts', { window, document, indexedDB: attrappeIndexedDB(), Blob });
    w.toast = {
        success: (m) => w.meldungen.push(['success', m]),
        warning: (m) => w.meldungen.push(['warning', m]),
    };
    w.kopf = (n) => ({ 'content-disposition': `attachment; filename="${n}"; filename*=UTF-8''${encodeURIComponent(n)}` });
    w.re = (inhalt, nummer = 'RE-2026-00006') => w.bo.belegHerunterladen(
        { art: 'Rechnungen', datum: '2026-10-09', ersatzname: 'Ersatz.pdf' },
        async () => ({ data: inhalt, headers: w.kopf(nummer + '.pdf') }), w.toast);
    return w;
}
"""
    ergebnis = subprocess.run(
        ["node", "-e", vorspann + "(async () => {\n" + script
         + "\n})().catch((e) => { console.error(e); process.exitCode = 1; });"],
        cwd=Path(__file__).resolve().parents[2] / "frontend",
        env={**os.environ, "TZ": "UTC"}, capture_output=True, text=True, timeout=60,
    )
    assert ergebnis.returncode == 0, ergebnis.stdout + ergebnis.stderr


class TestOBelegordner:
    """Gernot 09.10.: Belege direkt in einen gewählten Ordner, sortiert nach
    <Belegart>/<JJJJ-MM>/<Belegnummer>, statt im Download-Ordner. Ohne Ordner,
    ohne Freigabe, ohne API oder bei Schreibfehlern: normaler Download."""

    def test_ohne_ordner_normaler_download_ohne_meldung(self):
        _o_node("""
const w = umgebung();
gleich(await w.bo.belegordnerName(), null);
gleich(await w.re('PDF'), { ort: 'download', dateiname: 'RE-2026-00006.pdf' });
gleich(w.downloads, ['RE-2026-00006.pdf']);
gleich(w.meldungen, []);
""")

    def test_ablage_nach_belegart_und_monat_mit_meldung(self):
        _o_node("""
const w = umgebung();
gleich(await w.bo.belegordnerWaehlen(), 'Belege');
gleich(await w.bo.belegordnerName(), 'Belege');
gleich(await w.re('PDF-1'), { ort: 'ordner', pfad: 'Belege/Rechnungen/2026-10/RE-2026-00006.pdf' });
gleich(w.wurzel.inhalt('Rechnungen/2026-10/RE-2026-00006.pdf'), 'PDF-1');
// Zeitstempel ohne Zone = UTC: 31.10. 23:30 UTC ist in Berlin schon November
gleich(await w.bo.belegHerunterladen(
    { art: 'Auftragsbestätigungen', datum: '2026-10-31T23:30:00.123456', ersatzname: 'AB-20261101-0001.pdf' },
    async () => ({ data: 'AB' }), w.toast),
  { ort: 'ordner', pfad: 'Belege/Auftragsbestätigungen/2026-11/AB-20261101-0001.pdf' });
gleich(w.downloads, []);
gleich(w.meldungen, [
    ['success', 'Gespeichert in Belege/Rechnungen/2026-10/RE-2026-00006.pdf'],
    ['success', 'Gespeichert in Belege/Auftragsbestätigungen/2026-11/AB-20261101-0001.pdf'],
]);
""")

    def test_vorhandener_beleg_nur_nach_rueckfrage_ersetzen_sonst_daneben(self):
        _o_node("""
const w = umgebung();
await w.bo.belegordnerWaehlen();
await w.re('PDF-1');
gleich(w.rueckfragen, []);
w.antworten.push(true);   // OK = ersetzen
gleich(await w.re('PDF-2'), { ort: 'ordner', pfad: 'Belege/Rechnungen/2026-10/RE-2026-00006.pdf' });
gleich(w.wurzel.inhalt('Rechnungen/2026-10/RE-2026-00006.pdf'), 'PDF-2');
w.antworten.push(false);  // Abbrechen = daneben speichern
gleich(await w.re('PDF-3'), { ort: 'ordner', pfad: 'Belege/Rechnungen/2026-10/RE-2026-00006 (1).pdf' });
gleich(w.wurzel.inhalt('Rechnungen/2026-10/RE-2026-00006.pdf'), 'PDF-2');
gleich(w.wurzel.inhalt('Rechnungen/2026-10/RE-2026-00006 (1).pdf'), 'PDF-3');
gleich(w.rueckfragen.length, 2);
gleich(w.rueckfragen[1], '„RE-2026-00006.pdf" liegt schon in Belege/Rechnungen/2026-10.\\n\\n'
    + 'OK: ersetzen\\nAbbrechen: daneben als „RE-2026-00006 (1).pdf" speichern');
""")

    def test_exporte_bekommen_ohne_rueckfrage_einen_zusatz(self):
        _o_node("""
const w = umgebung();
await w.bo.belegordnerWaehlen();
const sepa = (inhalt) => w.bo.belegHerunterladen(
    { art: 'Lastschriften', datum: '2026-10-09', ersatzname: 'Lastschrift-Einreichung_2026-10-09.csv', mime: 'text/csv' },
    async () => ({ data: inhalt }), w.toast);
gleich(await sepa('a;b'), { ort: 'ordner', pfad: 'Belege/Lastschriften/2026-10/Lastschrift-Einreichung_2026-10-09.csv' });
gleich(await sepa('c;d'), { ort: 'ordner', pfad: 'Belege/Lastschriften/2026-10/Lastschrift-Einreichung_2026-10-09 (1).csv' });
gleich(w.wurzel.inhalt('Lastschriften/2026-10/Lastschrift-Einreichung_2026-10-09.csv'), 'a;b');
gleich(w.rueckfragen, []);
""")

    def test_freigabe_vor_dem_laden_sonst_download_mit_hinweis(self):
        _o_node("""
// Freigabe je Sitzung: erst fragen (frischer Klick), dann beim Server laden
const w = umgebung();
await w.bo.belegordnerWaehlen();
w.wurzel.erlaubnis = 'prompt';
gleich(await w.bo.belegordnerErlaubnis(), 'prompt');
const e = await w.bo.belegHerunterladen({ art: 'Mahnungen', datum: '2026-10-09', ersatzname: 'M.pdf' },
    async () => { w.wurzel.protokoll.push('geladen'); return { data: 'M' }; }, w.toast);
gleich(w.wurzel.protokoll, ['Freigabe angefragt', 'geladen']);
gleich(e, { ort: 'ordner', pfad: 'Belege/Mahnungen/2026-10/M.pdf' });

// Ohne Freigabe: Download mit Hinweis. Zwei Fälle mit verschiedenem Ausweg (O-E5a):
// ohneKlick (SecurityError) bzw. weggeklickt: Stand bleibt „fragen“, der Knopf
// in den Einstellungen hilft. abgelehnt: Chrome fragt in dieser Sitzung nicht
// mehr, auch nicht über den Knopf.
const hinweise = {
    ohneKlick: 'Kein Zugriff auf den Belegordner „Belege" — RE-2026-00006.pdf liegt im Download-Ordner. '
        + 'Zugriff erlauben: Einstellungen → Belegordner.',
    weggeklickt: 'Kein Zugriff auf den Belegordner „Belege" — RE-2026-00006.pdf liegt im Download-Ordner. '
        + 'Zugriff erlauben: Einstellungen → Belegordner.',
    abgelehnt: 'Zugriff auf den Belegordner „Belege" abgelehnt — RE-2026-00006.pdf liegt im Download-Ordner. '
        + 'Wieder erlauben: alle Tabs dieser Seite schließen und neu öffnen '
        + 'oder Symbol links in der Adresszeile → Website-Einstellungen.',
};
for (const fall of ['ohneKlick', 'weggeklickt', 'abgelehnt']) {
    const v = umgebung();
    await v.bo.belegordnerWaehlen();
    v.wurzel.erlaubnis = 'prompt';
    if (fall === 'ohneKlick') v.wurzel.ohneKlick = true;
    else v.wurzel.antwort = fall === 'abgelehnt' ? 'denied' : 'prompt';
    gleich(await v.re('PDF'), { ort: 'download', dateiname: 'RE-2026-00006.pdf', hinweis: hinweise[fall] });
    gleich(v.downloads, ['RE-2026-00006.pdf']);
    gleich(v.meldungen.map((m) => m[0]), ['warning']);
    // Der Knopf „Zugriff erlauben“ (Einstellungen, frischer Klick)
    v.wurzel.ohneKlick = false; v.wurzel.antwort = 'granted';
    if (fall === 'abgelehnt') {
        gleich(await v.bo.belegordnerErlaubnis(), 'denied');
        gleich(await v.bo.belegordnerFreigeben(), false);
        gleich(v.wurzel.protokoll, ['Freigabe angefragt']);   // keine zweite Frage
        gleich(v.bo.ZUGRIFF_WIEDER_ERLAUBEN, hinweise.abgelehnt.split('Download-Ordner. ')[1]);
    } else {
        gleich(await v.bo.belegordnerErlaubnis(), 'prompt');
        gleich(await v.bo.belegordnerFreigeben(), true);
        gleich(v.wurzel.protokoll, ['Freigabe angefragt', 'Freigabe angefragt']);
    }
}
""")

    def test_schreibfehler_faellt_auf_download_zurueck(self):
        _o_node("""
const w = umgebung();
await w.bo.belegordnerWaehlen();
await w.wurzel.getFileHandle('Packlisten', { create: true });   // Datei statt Ordner
const e = await w.bo.belegHerunterladen(
    { art: 'Packlisten', datum: '2026-10-09T08:00:00', ersatzname: 'PL-20261009-0001.pdf' },
    async () => ({ data: 'PL' }), w.toast);
gleich(e, {
    ort: 'download', dateiname: 'PL-20261009-0001.pdf',
    hinweis: 'Belegordner „Belege" nicht beschreibbar (TypeMismatchError) — PL-20261009-0001.pdf liegt im Download-Ordner.',
});
gleich(w.downloads, ['PL-20261009-0001.pdf']);
""")

    def test_laden_ohne_ergebnis_oder_mit_fehler(self):
        _o_node("""
const w = umgebung();
await w.bo.belegordnerWaehlen();
gleich(await w.bo.belegHerunterladen({ art: 'Mahnungen', ersatzname: 'M.pdf' }, async () => null, w.toast), null);
gleich([w.downloads, w.meldungen, [...w.wurzel.eintraege.keys()]], [[], [], []]);
await assert.rejects(
    w.bo.belegHerunterladen({ art: 'Rechnungen', ersatzname: 'x.pdf' }, async () => { throw new Error('500 vom Server'); }, w.toast),
    /500 vom Server/);
""")

    def test_ohne_api_und_nach_zuruecksetzen_normaler_download(self):
        _o_node("""
// Safari/Firefox: keine API — nichts zu wählen, Download wie bisher
const ohne = umgebung({ ohneApi: true });
gleich(ohne.bo.belegordnerMoeglich(), false);
gleich(await ohne.bo.belegordnerWaehlen(), null);
gleich(await ohne.re('PDF'), { ort: 'download', dateiname: 'RE-2026-00006.pdf' });
gleich(ohne.meldungen, []);

const w = umgebung();
gleich(w.bo.belegordnerMoeglich(), true);
await w.bo.belegordnerWaehlen();
await w.bo.belegordnerZuruecksetzen();
gleich(await w.bo.belegordnerName(), null);
gleich(await w.re('PDF'), { ort: 'download', dateiname: 'RE-2026-00006.pdf' });
gleich(w.wurzel.eintraege.size, 0);
""")
