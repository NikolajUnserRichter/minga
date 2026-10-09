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
