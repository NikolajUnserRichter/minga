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
