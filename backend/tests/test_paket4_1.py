"""Paket 4.1 — Restpunkte aus der Paket-4-Abnahme (10.10.2026).

Gemeinsame Testdatei aller Abschnitte. Klassen und Helfer tragen ein
Abschnitts-Präfix (TestP41V…/_p41v_, TestP41Z…/_p41z_, TestP41R…/_p41r_,
TestP41D…/_p41d_): ein gleichnamiger Helfer würde still ersetzt. Jeder
Abschnitt bringt seine Importe selbst mit. Keine autouse-Fixture.
"""


# ============================================================
# R — Cent-Rundung in der Anlage „Enthaltene Lieferscheine“
# ============================================================

import random as _p41r_random
from decimal import Decimal as _P41R_Decimal
from fractions import Fraction as _P41R_Fraction


def _p41r_euro(text):
    return _P41R_Decimal(text)


def _p41r_verteilen(anteile, rang=None):
    """auf_cent_verteilen mit Rang = Schlüssel. Import im Test: Vor R.1 gibt es
    die Funktion nicht, die gemeinsame Datei bleibt trotzdem sammelbar."""
    from app.services.invoice_service import auf_cent_verteilen
    return auf_cent_verteilen(anteile, rang or {k: k for k in anteile})


class TestP41RCentVerteilung:
    """Größte-Reste-Verfahren: exakte Anteile → Cent, Summe bleibt exakt."""

    def test_exakte_centbetraege_unveraendert(self):
        ergebnis = _p41r_verteilen({"a": _P41R_Fraction("25"), "b": _P41R_Fraction("12.5")})

        assert ergebnis == {"a": _p41r_euro("25.00"), "b": _p41r_euro("12.50")}
        assert str(ergebnis["a"]) == "25.00"

    def test_restcent_an_den_groessten_rest(self):
        # 0,9975 + 0,3325 = 1,33: abgerundet 0,99 + 0,33, der fehlende Cent
        # geht an den größeren Rest (0,75 Cent gegen 0,25 Cent).
        ergebnis = _p41r_verteilen({"a": _P41R_Fraction("0.9975"), "b": _P41R_Fraction("0.3325")})

        assert ergebnis == {"a": _p41r_euro("1.00"), "b": _p41r_euro("0.33")}

    def test_gleicher_rest_kleinerer_rang_zuerst(self):
        anteile = {"x": _P41R_Fraction("1.005"), "y": _P41R_Fraction("1.005")}

        assert _p41r_verteilen(anteile, {"x": 2, "y": 1}) == {"x": _p41r_euro("1.00"), "y": _p41r_euro("1.01")}
        assert _p41r_verteilen(anteile, {"x": 1, "y": 2}) == {"x": _p41r_euro("1.01"), "y": _p41r_euro("1.00")}

    def test_negative_anteile(self):
        ergebnis = _p41r_verteilen({
            "a": _P41R_Fraction("1.005"), "b": _P41R_Fraction("-0.0025"), "c": _P41R_Fraction("0.0075"),
        })

        assert ergebnis == {"a": _p41r_euro("1.00"), "b": _p41r_euro("0.00"), "c": _p41r_euro("0.01")}

    def test_feste_zufallstabelle(self):
        """1000 Fälle aus festem Startwert (Hypothesis ist nicht installiert):
        Summe exakt, jeder Betrag weniger als 1 Cent vom Anteil, Ergebnis
        unabhängig von der Reihenfolge der Eingabe."""
        zufall = _p41r_random.Random(20261010)
        for fall in range(1000):
            n = zufall.randint(1, 7)
            ziel = _P41R_Fraction(zufall.randint(-500, 500_000), 100)
            teile = [_P41R_Fraction(zufall.randint(-10_000, 100_000_000), 10 ** zufall.randint(2, 7))
                     for _ in range(n - 1)]
            anteile = {f"LS-{i:04d}": t for i, t in enumerate(teile, 1)}
            anteile[f"LS-{n:04d}"] = ziel - sum(teile, _P41R_Fraction(0))

            ergebnis = _p41r_verteilen(anteile)
            umgekehrt = _p41r_verteilen(dict(reversed(list(anteile.items()))))

            assert _P41R_Fraction(sum(ergebnis.values(), _P41R_Decimal(0))) == ziel, fall
            assert all(abs(_P41R_Fraction(ergebnis[k]) - anteile[k]) < _P41R_Fraction(1, 100)
                       for k in anteile), fall
            assert all(ergebnis[k].as_tuple().exponent == -2 for k in anteile), fall
            assert umgekehrt == ergebnis, fall


import base64 as _p41r_base64
import re as _p41r_re
import zlib as _p41r_zlib

import pytest as _p41r_pytest

_P41R_MAERZ = {"period_from": "2026-03-01", "period_to": "2026-03-31"}


def _p41r_kunde(client, name="Gasthaus Rundung", **extra):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "GASTRO", **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _p41r_bestellung(client, kunde, tag, zeilen):
    """Bestellung im März 2026; zeilen = [(Text, Menge, Einzelpreis, Positionsrabatt %)], 7 %."""
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"], "requested_delivery_date": f"2026-03-{tag:02d}",
        "lines": [{"product_name": text, "quantity": menge, "unit": "STK", "unit_price": preis,
                   "discount_percent": rabatt, "tax_rate": "REDUZIERT"}
                  for text, menge, preis, rabatt in zeilen],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _p41r_lieferung(client, kunde, tag, zeilen):
    bestellung = _p41r_bestellung(client, kunde, tag, zeilen)
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes", json={})
    assert r.status_code == 201, r.text
    return bestellung, r.json()["delivery_note_number"]


def _p41r_sammelrechnung(client, kunde, lieferungen):
    """Je Eintrag eine Bestellung mit Lieferschein (2., 9., 16. … März), dann
    der Sammellauf für den März. Gibt Rechnung (Entwurf) und LS-Nummern in
    Anlagereihenfolge zurück."""
    nummern = [_p41r_lieferung(client, kunde, 2 + 7 * i, zeilen)[1] for i, zeilen in enumerate(lieferungen)]
    r = client.post("/api/v1/invoices/batch-run/commit", json={**_P41R_MAERZ, "customer_ids": [kunde["id"]]})
    assert r.status_code == 201, r.text
    rechnungen = r.json()["rechnungen"]
    assert len(rechnungen) == 1, rechnungen
    return rechnungen[0], nummern


def _p41r_anlage(client, rechnung):
    """Netto je Lieferschein aus GET /invoices/{id}/delivery-notes (dieselbe
    Funktion wie die PDF-Anlage), nach Lieferscheinnummer."""
    r = client.get(f"/api/v1/invoices/{rechnung['id']}/delivery-notes")
    assert r.status_code == 200, r.text
    return {ls["delivery_note_number"]: _P41R_Decimal(str(ls["betrag_netto"])).quantize(_P41R_Decimal("0.01"))
            for ls in r.json()}


def _p41r_rechnung(client, rechnung):
    r = client.get(f"/api/v1/invoices/{rechnung['id']}")
    assert r.status_code == 200, r.text
    return r.json()


def _p41r_dec(wert):
    return _P41R_Decimal(str(wert)).quantize(_P41R_Decimal("0.01"))


def _p41r_pdf_text(pdf_bytes):
    """Text grob aus dem PDF (ReportLab: Flate bzw. ASCII85+Flate), wie
    tests/test_documents_preise.py::_pdf_text."""
    teile, pos = [pdf_bytes], 0
    while True:
        start = pdf_bytes.find(b"stream", pos)
        if start == -1:
            break
        start = pdf_bytes.find(b"\n", start) + 1
        ende = pdf_bytes.find(b"endstream", start)
        if ende == -1:
            break
        stueck = pdf_bytes[start:ende].strip()
        for entpacken in (lambda d: _p41r_zlib.decompress(d),
                          lambda d: _p41r_zlib.decompress(_p41r_base64.a85decode(d, adobe=True))):
            try:
                teile.append(entpacken(stueck))
                break
            except Exception:
                continue
        pos = ende + 1
    return b"\n".join(teile)


def _p41r_pdf_anlage(client, rechnung):
    """Zeilen der PDF-Tabelle „Enthaltene Lieferscheine“: {LS-Nummer: Betrag}."""
    r = client.get(f"/api/v1/invoices/{rechnung['id']}/pdf")
    assert r.status_code == 200, r.text
    text = _p41r_pdf_text(r.content)
    abschnitt = text[text.index(b"(Enthaltene Lieferscheine) Tj"):]
    nummern = _p41r_re.findall(rb"\((LS-[0-9-]+)\) Tj", abschnitt)
    betraege = _p41r_re.findall(rb"\((-?[0-9]+\.[0-9]{2}) EUR\) Tj", abschnitt)
    assert len(nummern) == len(betraege) > 0, abschnitt
    return {n.decode(): _P41R_Decimal(b.decode()) for n, b in zip(nummern, betraege)}


_P41R_SORTEN = [(f"Sorte {i:02d}", 1, "0.3333", 0) for i in range(1, 21)]

# (Lieferungen, Netto der Positionen, Anlage je Lieferschein in LS-Reihenfolge)
_P41R_FAELLE = {
    # Befund Paket-4-Abnahme: Netto 2,01, Anlage bisher 1,01 + 1,01 = 2,02
    "preis_1_005_zweimal": ([[("Erbsen", 1, "1.005", 0)], [("Erbsen", 1, "1.005", 0)]],
                            "2.01", ["1.01", "1.00"]),
    # Netto 0,67, bisher 0,33 + 0,33 = 0,66
    "preis_0_3333_zweimal": ([[("Erbsen", 1, "0.3333", 0)], [("Erbsen", 1, "0.3333", 0)]],
                             "0.67", ["0.34", "0.33"]),
    # Positionsrabatt 33,33 %: Netto 1,33, bisher 0,67 + 0,67 = 1,34
    "rabatt_33_33_zweimal": ([[("Erbsen", 1, "1.00", "33.33")], [("Erbsen", 1, "1.00", "33.33")]],
                             "1.33", ["0.67", "0.66"]),
    # drei Lieferscheine, Netto 3,02 (3 × 1,005 = 3,015), bisher 3 × 1,01 = 3,03
    "preis_1_005_dreimal": ([[("Erbsen", 1, "1.005", 0)]] * 3, "3.02", ["1.01", "1.01", "1.00"]),
    # 20 Positionen mit je einem Restcent: verteilt je Rechnung, nicht je
    # Position — sonst bekäme der erste Lieferschein alle 20 (6,80 + 6,60).
    # Bisher 6,67 + 6,67 = 13,34 gegen 13,40.
    "zwanzig_sorten_0_3333": ([_P41R_SORTEN, _P41R_SORTEN], "13.40", ["6.70", "6.70"]),
    # Centpreis mit Bruchmenge (Menge Numeric(10,3)): je Lieferschein
    # 0,125 × 2,50 = 0,3125; Position 0,25 × 2,50 = 0,625 → 0,63.
    # Bisher 0,31 + 0,31 = 0,62.
    "bruchmenge_centpreis": ([[("Erbsen", "0.125", "2.50", 0)], [("Erbsen", "0.125", "2.50", 0)]],
                             "0.63", ["0.32", "0.31"]),
    # Wächter: ungleiche Mengen, Rest schon bisher stimmig
    "mengen_3_und_1_zu_0_3333": ([[("Erbsen", 3, "0.3333", 0)], [("Erbsen", 1, "0.3333", 0)]],
                                 "1.33", ["1.00", "0.33"]),
    # Wächter: Centpreise mit ganzen Mengen — Anlage genau wie bisher
    "centpreise": ([[("Erbsen", 10, "2.50", 0)], [("Erbsen", 5, "2.50", 0), ("Erbsen", 3, "3.00", 0)]],
                   "46.50", ["25.00", "21.50"]),
}


class TestP41RAnlageSammelrechnung:
    """Die Anlage „Enthaltene Lieferscheine“ summiert sich exakt zum Netto
    der Positionen; jeder Lieferschein liegt weniger als 1 Cent neben seinem
    Anteil. Feste Tabelle mit den Beispielen der Paket-4-Abnahme."""

    @_p41r_pytest.mark.parametrize("fall", list(_P41R_FAELLE))
    def test_anlage_summiert_zum_positionsnetto(self, client, fall):
        lieferungen, netto, erwartet = _P41R_FAELLE[fall]
        kunde = _p41r_kunde(client)
        rechnung, nummern = _p41r_sammelrechnung(client, kunde, lieferungen)

        detail = _p41r_rechnung(client, rechnung)
        anlage = _p41r_anlage(client, rechnung)

        assert _p41r_dec(detail["subtotal"]) == _p41r_euro(netto)
        assert sum(_p41r_dec(l["line_total"]) for l in detail["lines"]) == _p41r_euro(netto)
        assert anlage == {nr: _p41r_euro(b) for nr, b in zip(nummern, erwartet)}
        assert sum(anlage.values()) == _p41r_euro(netto)


class TestP41RAnlageRandfaelle:
    """PDF, Rechnungsrabatt, Positionen ohne Lieferschein, Rechnung aus
    Bestellung, Stornorechnung."""

    def test_pdf_anlage_summiert_zum_netto(self, client):
        kunde = _p41r_kunde(client)
        lieferungen, netto, erwartet = _P41R_FAELLE["preis_1_005_zweimal"]
        rechnung, nummern = _p41r_sammelrechnung(client, kunde, lieferungen)

        anlage = _p41r_pdf_anlage(client, rechnung)

        assert anlage == {nr: _p41r_euro(b) for nr, b in zip(nummern, erwartet)}
        assert sum(anlage.values()) == _p41r_dec(_p41r_rechnung(client, rechnung)["subtotal"])

    def test_rechnungsrabatt_bleibt_ausserhalb_der_anlage(self, client):
        """Kundenrabatt 3 % (im PDF z. B. „Jahresbonus und Verpackungspauschale“):
        die Anlage zeigt die Lieferungen vor dem Rechnungsrabatt und summiert
        sich zur Zwischensumme = Netto + Rabatt."""
        kunde = _p41r_kunde(client, discount_percent=3)
        lieferungen, _, erwartet = _P41R_FAELLE["preis_1_005_zweimal"]
        rechnung, nummern = _p41r_sammelrechnung(client, kunde, lieferungen)

        detail = _p41r_rechnung(client, rechnung)
        anlage = _p41r_anlage(client, rechnung)

        assert (_p41r_dec(detail["subtotal"]), _p41r_dec(detail["discount_amount"])) == (
            _p41r_euro("1.95"), _p41r_euro("0.06"))
        assert anlage == {nr: _p41r_euro(b) for nr, b in zip(nummern, erwartet)}
        assert sum(anlage.values()) == _p41r_dec(detail["subtotal"]) + _p41r_dec(detail["discount_amount"])

    def test_position_ohne_lieferschein_nicht_in_der_anlage(self, client):
        """Wächter: eine von Hand ergänzte Position gehört zu keinem Lieferschein."""
        kunde = _p41r_kunde(client)
        rechnung, nummern = _p41r_sammelrechnung(client, kunde, [
            [("Erbsen", 10, "2.50", 0)], [("Erbsen", 5, "2.50", 0)]])
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/lines", json={
            "description": "Verpackungspauschale", "quantity": 1, "unit": "STK",
            "unit_price": "5.00", "tax_rate": "REDUZIERT"})
        assert r.status_code in (200, 201), r.text

        assert _p41r_dec(_p41r_rechnung(client, rechnung)["subtotal"]) == _p41r_euro("42.50")
        assert _p41r_anlage(client, rechnung) == {
            nummern[0]: _p41r_euro("25.00"), nummern[1]: _p41r_euro("12.50")}

    def test_rechnung_aus_bestellung_unveraendert(self, client):
        """Wächter: ohne invoice_line_sources zählt die Summe der Positionen."""
        kunde = _p41r_kunde(client)
        bestellung, nummer = _p41r_lieferung(client, kunde, 2, [("Erbsen", 2, "1.005", 0)])
        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")
        assert r.status_code == 201, r.text

        assert _p41r_anlage(client, r.json()) == {nummer: _p41r_euro("2.01")}

    def test_stornorechnung_ohne_anlage(self, client):
        """Wächter: die Stornorechnung (negative Positionen) hat keine
        Lieferscheine und keine Herkunft je Lieferschein."""
        kunde = _p41r_kunde(client)
        lieferungen, _, _ = _P41R_FAELLE["preis_1_005_zweimal"]
        rechnung, _ = _p41r_sammelrechnung(client, kunde, lieferungen)
        assert client.post(f"/api/v1/invoices/{rechnung['id']}/finalize").status_code == 200
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/cancel", json={
            "reason": "Preisfehler", "reason_code": "PREISFEHLER"})
        assert r.status_code == 200, r.text
        storno_id = r.json()["credit_note"]["id"]

        assert _p41r_anlage(client, {"id": storno_id}) == {}


# ============================================================
# Abschnitt D — Berliner Datum in Belegnummern (Paket 4.1)
# ============================================================
import importlib as _p41d_importlib
from datetime import date as _p41d_date, datetime as _p41d_datetime, timezone as _p41d_timezone

#: Module, deren date.today() eine Nummer oder ihr Datum bestimmte — dort
#: liefert die Testuhr den UTC-Tag wie der Container (python:3.11-slim ohne TZ).
_P41D_DATE_MODULE = (
    "app.services.lieferschein_service", "app.api.v1.documents", "app.api.v1.sales",
    "app.services.shopify_service", "app.services.inventory_service",
    "app.services.invoice_service", "app.tasks.subscription_tasks",
)
#: Module, deren datetime.now(...) einen Berliner Tag, eine Nummer oder das
#: gedruckte Bestelldatum liefert (models.order: Standard von Order.order_date).
_P41D_DATETIME_MODULE = (
    "app.services.order_status_service", "app.services.invoice_service",
    "app.services.procurement_service", "app.models.order",
)


def _p41d_uhr(monkeypatch, utc):
    """Server wie in Produktion (Prozess-Zeitzone UTC) zum Zeitpunkt `utc`:
    date.today() ist der UTC-Tag, datetime.now(tz) der Zeitpunkt in tz,
    datetime.now() naive UTC. Muster: TestNacharbeitPacktagBerlin
    (test_gernot_261008_paket2.py), TestAbnahmeSepaBerlin (paket3).
    raising=False: ein Modul, das `date` oder `datetime` nach Abschnitt D
    nicht mehr importiert (documents.py, procurement_service.py), bekommt
    den Namen nur für die Dauer des Tests."""
    zeitpunkt = _p41d_datetime.fromisoformat(utc)

    class _P41DUhr(_p41d_datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return zeitpunkt.astimezone(_p41d_timezone.utc).replace(tzinfo=None)
            return zeitpunkt.astimezone(tz)

    class _P41DServertag(_p41d_date):
        @classmethod
        def today(cls):
            return zeitpunkt.astimezone(_p41d_timezone.utc).date()

    for name in _P41D_DATETIME_MODULE:
        monkeypatch.setattr(_p41d_importlib.import_module(name), "datetime", _P41DUhr, raising=False)
    for name in _P41D_DATE_MODULE:
        monkeypatch.setattr(_p41d_importlib.import_module(name), "date", _P41DServertag, raising=False)


#: 00:30 in München am 10.10.2026 (Sommerzeit, UTC+2) — UTC noch 09.10.
_P41D_HALB_EINS = "2026-10-09T22:30:00+00:00"
#: 23:30 in München am 09.10.2026 — derselbe Tag in UTC und Berlin.
_P41D_HALB_ZWOELF = "2026-10-09T21:30:00+00:00"
#: 02:30 in München am 10.10.2026 — UTC ist auch schon der 10.10.
_P41D_HALB_DREI = "2026-10-10T00:30:00+00:00"


def _p41d_kunde(client, name="Dorint Hotels Betriebs GmbH"):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "GASTRO"})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _p41d_bestellung(client, kunde, liefertag):
    """Bestätigte Bestellung mit einer Freitextposition (10 × 2,50 € zu 7 %)."""
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"], "requested_delivery_date": liefertag,
        "lines": [{"product_name": "Erbsen-Schale", "quantity": 10, "unit": "STK",
                   "unit_price": "2.50", "tax_rate": "REDUZIERT"}],
    })
    assert r.status_code == 201, r.text
    bestellung = r.json()
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/confirm")
    assert r.status_code == 200, r.text
    return r.json()


def _p41d_ausliefern(client, bestellung):
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/status", json={"status": "GELIEFERT"})
    assert r.status_code == 200, r.text
    return r.json()


def _p41d_lieferscheine(client, bestellung):
    r = client.get(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes")
    assert r.status_code == 200, r.text
    return [(ls["delivery_note_number"], ls["packing_list"]["packing_list_number"],
             ls["actual_delivery_date"]) for ls in r.json()]


def _p41d_pdf_daten(client, url):
    """Alle Daten TT.MM.JJJJ im Text eines Beleg-PDFs, in Druckreihenfolge."""
    import re
    from tests.test_documents_preise import _pdf_text
    r = client.get(url)
    assert r.status_code == 200, r.text
    return re.findall(r"\d\d\.\d\d\.\d{4}", _pdf_text(r.content).decode("latin-1", errors="ignore"))


class TestP41DLieferscheinnummerBerlin:
    """Lieferschein, Packliste und Auftragsbestätigung heißen nach dem
    Berliner Anlagetag. Der Container läuft in UTC: zwischen 0 und 2 Uhr
    (Sommerzeit; Winterzeit 0–1 Uhr) hieß der automatische Lieferschein nach
    dem Vortag, während actual_delivery_date schon den Berliner Tag trug."""

    def test_ausliefern_um_halb_eins(self, client, monkeypatch):
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)
        bestellung = _p41d_bestellung(client, _p41d_kunde(client), "2026-10-10")

        geliefert = _p41d_ausliefern(client, bestellung)

        assert geliefert["actual_delivery_date"] == "2026-10-10"
        assert _p41d_lieferscheine(client, bestellung) == [
            ("LS-20261010-0001", "PL-20261010-0001", "2026-10-10")]

    def test_neuer_lieferschein_um_halb_eins(self, client, monkeypatch):
        """„Neuer LS“ im Belegdialog und „Packliste“ im Tagesplan."""
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)
        bestellung = _p41d_bestellung(client, _p41d_kunde(client), "2026-10-10")

        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes", json={})

        assert r.status_code == 201, r.text
        assert (r.json()["delivery_note_number"], r.json()["packing_list"]["packing_list_number"]) == (
            "LS-20261010-0001", "PL-20261010-0001")

    def test_auftragsbestaetigung_um_halb_eins(self, client, monkeypatch):
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)
        bestellung = _p41d_bestellung(client, _p41d_kunde(client), "2026-10-12")

        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/confirmations", json={})

        assert r.status_code == 201, r.text
        assert r.json()["confirmation_number"] == "AB-20261010-0001"

    def test_belegdatum_im_pdf_um_halb_eins(self, client, monkeypatch):
        """AB, Lieferschein und Packliste drucken „Datum:“ (Bestelldatum,
        Order.order_date, naiv in UTC gespeichert) und „Lieferdatum:“. Um 00:30
        stand sonst neben AB-/LS-/PL-20261010-… der 09.10.2026."""
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)
        bestellung = _p41d_bestellung(client, _p41d_kunde(client), "2026-10-12")
        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/confirmations", json={})
        assert r.status_code == 201, r.text
        ab = r.json()
        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes", json={})
        assert r.status_code == 201, r.text
        ls = r.json()

        daten = [_p41d_pdf_daten(client, url) for url in (
            f"/api/v1/sales/confirmations/{ab['id']}/pdf",
            f"/api/v1/sales/delivery-notes/{ls['id']}/pdf",
            f"/api/v1/sales/delivery-notes/{ls['id']}/packing-list/pdf")]

        assert daten == [["10.10.2026", "12.10.2026"]] * 3

    def test_neuer_tag_beginnt_um_mitternacht_in_berlin(self, client, monkeypatch):
        """23:30 und 00:30 Berliner Zeit: zwei Tage, zwei Nummernkreise."""
        kunde = _p41d_kunde(client)
        _p41d_uhr(monkeypatch, _P41D_HALB_ZWOELF)
        abend = _p41d_bestellung(client, kunde, "2026-10-09")
        _p41d_ausliefern(client, abend)
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)
        nacht = _p41d_bestellung(client, kunde, "2026-10-10")
        _p41d_ausliefern(client, nacht)

        assert [_p41d_lieferscheine(client, b)[0][0] for b in (abend, nacht)] == [
            "LS-20261009-0001", "LS-20261010-0001"]

    def test_nach_zwei_uhr_wie_bisher(self, client, monkeypatch):
        """Wächter: ab 2 Uhr sind UTC- und Berliner Tag gleich."""
        _p41d_uhr(monkeypatch, _P41D_HALB_DREI)
        bestellung = _p41d_bestellung(client, _p41d_kunde(client), "2026-10-10")

        _p41d_ausliefern(client, bestellung)

        assert _p41d_lieferscheine(client, bestellung) == [
            ("LS-20261010-0001", "PL-20261010-0001", "2026-10-10")]


def _p41d_einheit():
    from app.models.unit import UnitCategory, UnitOfMeasure
    from tests.conftest import TestingSessionLocal
    with TestingSessionLocal() as db:
        einheit = db.query(UnitOfMeasure).filter_by(code="STK").first()
        if einheit is None:
            einheit = UnitOfMeasure(code="STK", name="Stück", category=UnitCategory.COUNT)
            db.add(einheit)
            db.commit()
        return str(einheit.id)


def _p41d_bestellnummern():
    from app.models.order import Order
    from tests.conftest import TestingSessionLocal
    with TestingSessionLocal() as db:
        return sorted((o.order_number, o.requested_delivery_date.isoformat()) for o in db.query(Order))


class TestP41DBestellnummerBerlin:
    """BE-Nummern (Bestellung, Abo-Lauf, Shopify-Import) nach dem Berliner Tag."""

    def test_bestellung_um_halb_eins(self, client, monkeypatch):
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)

        bestellung = _p41d_bestellung(client, _p41d_kunde(client), "2026-10-10")

        assert bestellung["order_number"] == "BE-20261010-0001"

    def test_neuer_tag_beginnt_um_mitternacht_in_berlin(self, client, monkeypatch):
        kunde = _p41d_kunde(client)
        _p41d_uhr(monkeypatch, _P41D_HALB_ZWOELF)
        _p41d_bestellung(client, kunde, "2026-10-12")
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)
        _p41d_bestellung(client, kunde, "2026-10-12")

        assert [nummer for nummer, _ in _p41d_bestellnummern()] == ["BE-20261009-0001", "BE-20261010-0001"]

    def test_abo_lauf_um_halb_eins(self, client, monkeypatch):
        """„Heute verarbeiten“ um 00:30: Liefertag und Nummer tragen denselben Tag."""
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)
        kunde = _p41d_kunde(client, "LfA Förderbank Bayern")
        r = client.post("/api/v1/products", json={
            "name": "Erbse", "sku": "P41D-ABO", "base_price": "3.50",
            "category": "MICROGREEN", "base_unit_id": _p41d_einheit()})
        assert r.status_code in (200, 201), r.text
        r = client.post("/api/v1/sales/subscriptions", json={
            "kunde_id": kunde["id"], "product_id": r.json()["id"], "menge": 2, "einheit": "STUECK",
            "intervall": "TAEGLICH", "liefertage": [], "gueltig_von": "2026-10-10"})
        assert r.status_code == 201, r.text

        r = client.post("/api/v1/sales/subscriptions/process-today")

        assert r.status_code == 200, r.text
        assert r.json()["details"]["erstellt"] == 1
        assert _p41d_bestellnummern() == [("BE-20261010-0001", "2026-10-10")]

    def test_shopify_nummer_um_halb_eins(self, client, monkeypatch):
        from app.services.shopify_service import _next_order_number
        from tests.conftest import TestingSessionLocal
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)

        with TestingSessionLocal() as db:
            assert _next_order_number(db) == "BE-20261010-0001"

    def test_nach_zwei_uhr_wie_bisher(self, client, monkeypatch):
        """Wächter."""
        _p41d_uhr(monkeypatch, _P41D_HALB_DREI)

        bestellung = _p41d_bestellung(client, _p41d_kunde(client), "2026-10-10")

        assert bestellung["order_number"] == "BE-20261010-0001"


#: 00:30 in München am 01.01.2027 (Winterzeit, UTC+1) — UTC noch 31.12.2026.
_P41D_NEUJAHR_HALB_EINS = "2026-12-31T23:30:00+00:00"
#: 23:30 in München am 31.12.2026 — UTC 22:30, dasselbe Jahr.
_P41D_SILVESTER_HALB_ZWOELF = "2026-12-31T22:30:00+00:00"


class TestP41DJahreswechselEinkaufInventur:
    """EK- und INV-Nummern tragen das Jahr; maßgeblich ist der Berliner Tag."""

    def test_einkaufsnummer_am_neujahrstag(self, client, monkeypatch):
        from app.services.procurement_service import ProcurementService
        from tests.conftest import TestingSessionLocal
        _p41d_uhr(monkeypatch, _P41D_NEUJAHR_HALB_EINS)

        with TestingSessionLocal() as db:
            assert ProcurementService(db)._next_po_number() == "EK-2027-0001"

    def test_inventur_am_neujahrstag(self, client, monkeypatch):
        _p41d_uhr(monkeypatch, _P41D_NEUJAHR_HALB_EINS)

        r = client.post("/api/v1/inventory/counts")

        assert r.status_code == 201, r.text
        assert (r.json()["count_number"], r.json()["count_date"]) == ("INV-2027-0001", "2027-01-01")

    def test_silvester_halb_zwoelf_im_alten_jahr(self, client, monkeypatch):
        """Wächter: 23:30 Berliner Zeit ist in UTC derselbe Tag."""
        from app.services.procurement_service import ProcurementService
        from tests.conftest import TestingSessionLocal
        _p41d_uhr(monkeypatch, _P41D_SILVESTER_HALB_ZWOELF)

        r = client.post("/api/v1/inventory/counts")

        assert r.status_code == 201, r.text
        assert (r.json()["count_number"], r.json()["count_date"]) == ("INV-2026-0001", "2026-12-31")
        with TestingSessionLocal() as db:
            assert ProcurementService(db)._next_po_number() == "EK-2026-0001"


def _p41d_rechnungsentwurf(client, kunde, datum="2026-12-31", faellig="2027-01-14"):
    r = client.post("/api/v1/invoices", json={
        "customer_id": kunde["id"], "invoice_date": datum, "due_date": faellig,
        "lines": [{"description": "Erbsen-Schale", "quantity": 10, "unit": "STK",
                   "unit_price": "2.50", "tax_rate": "REDUZIERT"}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _p41d_festschreiben(client, rechnung):
    r = client.post(f"/api/v1/invoices/{rechnung['id']}/finalize")
    assert r.status_code == 200, r.text
    return r.json()


class TestP41DRechnungsjahrBerlin:
    """Wächter (seit P4-B.2 richtig, invoice_service._heute_berlin): RE-Jahr
    und Rechnungsdatum nach dem Berliner Tag des Festschreibens."""

    def test_festschreiben_um_halb_eins_am_neujahrstag(self, client, monkeypatch):
        _p41d_uhr(monkeypatch, _P41D_NEUJAHR_HALB_EINS)
        entwurf = _p41d_rechnungsentwurf(client, _p41d_kunde(client))

        rechnung = _p41d_festschreiben(client, entwurf)

        assert (rechnung["invoice_number"], rechnung["invoice_date"], rechnung["due_date"]) == (
            "RE-2027-00001", "2027-01-01", "2027-01-15")

    def test_festschreiben_um_halb_zwoelf_an_silvester(self, client, monkeypatch):
        _p41d_uhr(monkeypatch, _P41D_SILVESTER_HALB_ZWOELF)
        entwurf = _p41d_rechnungsentwurf(client, _p41d_kunde(client))

        rechnung = _p41d_festschreiben(client, entwurf)

        assert (rechnung["invoice_number"], rechnung["invoice_date"]) == ("RE-2026-00001", "2026-12-31")

    def test_storno_nach_mitternacht_im_neuen_jahr(self, client, monkeypatch):
        """Die Stornorechnung bekommt Nummer und Datum des Neujahrstags; das
        Original behält RE-2026-00001 vom 31.12. (GoBD)."""
        _p41d_uhr(monkeypatch, _P41D_SILVESTER_HALB_ZWOELF)
        original = _p41d_festschreiben(client, _p41d_rechnungsentwurf(client, _p41d_kunde(client)))
        _p41d_uhr(monkeypatch, _P41D_NEUJAHR_HALB_EINS)

        r = client.post(f"/api/v1/invoices/{original['id']}/cancel",
                        json={"reason": "Menge falsch", "create_credit_note": True})

        assert r.status_code == 200, r.text
        storno, gutschrift = r.json()["invoice"], r.json()["credit_note"]
        assert (storno["invoice_number"], storno["invoice_date"]) == ("RE-2026-00001", "2026-12-31")
        assert (gutschrift["invoice_number"], gutschrift["invoice_date"]) == ("RE-2027-00001", "2027-01-01")

    def test_neujahrslieferung_von_der_bestellung_bis_zur_rechnung(self, client, monkeypatch):
        """Alle Nummern einer Lieferung um 00:30 am 01.01.2027 tragen den Neujahrstag."""
        _p41d_uhr(monkeypatch, _P41D_NEUJAHR_HALB_EINS)
        bestellung = _p41d_bestellung(client, _p41d_kunde(client), "2027-01-01")
        _p41d_ausliefern(client, bestellung)
        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")
        assert r.status_code == 201, r.text

        rechnung = _p41d_festschreiben(client, r.json())

        assert bestellung["order_number"] == "BE-20270101-0001"
        assert _p41d_lieferscheine(client, bestellung) == [
            ("LS-20270101-0001", "PL-20270101-0001", "2027-01-01")]
        assert (rechnung["invoice_number"], rechnung["invoice_date"]) == ("RE-2027-00001", "2027-01-01")


# =============================================================================
# Abschnitt V — Bestellverlauf in der Oberfläche (Paket-4-Abnahme, „offen“)
# Präfixe: Klassen TestP41V…, Helfer _p41v_…, Konstanten _P41V_…
# =============================================================================
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.api.deps import get_current_user
from app.main import app
from tests.conftest import TestingSessionLocal

_P41V_USER_ID = "123e4567-e89b-12d3-a456-426614174000"


def _p41v_als(*rollen, name="p41v"):
    """Login mit genau diesen Rollen und diesem Benutzernamen (Muster _p4d_als).
    Das client-Fixture setzt das Login beim nächsten Test neu."""
    async def override():
        return {"id": _P41V_USER_ID, "username": name, "email": "p41v@example.com",
                "roles": list(rollen)}
    app.dependency_overrides[get_current_user] = override


def _p41v_verwaltung():
    """Standard-Login des client-Fixtures (conftest.py): admin + Planung, testuser."""
    _p41v_als("admin", "production_planner", name="testuser")


def _p41v_bestellung(client):
    """Bestätigte Bestellung mit zwei freien Positionen, angelegt von der Verwaltung."""
    _p41v_verwaltung()
    r = client.post("/api/v1/sales/customers", json={
        "name": f"Verlaufskunde {uuid.uuid4().hex[:6]}", "typ": "GASTRO"})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": r.json()["id"],
        "requested_delivery_date": (date.today() + timedelta(days=3)).isoformat(),
        "lines": [
            {"product_name": "Erbsen-Schale", "quantity": 4, "unit": "STK",
             "unit_price": "4.50", "tax_rate": "REDUZIERT"},
            {"product_name": "Radieschen-Schale", "quantity": 2, "unit": "STK",
             "unit_price": "3.20", "tax_rate": "REDUZIERT"},
        ],
    })
    assert r.status_code == 201, r.text
    r = client.post(f"/api/v1/sales/orders/{r.json()['id']}/confirm")
    assert r.status_code == 200, r.text
    return r.json()


def _p41v_verlauf(client, order):
    r = client.get(f"/api/v1/sales/orders/{order['id']}/audit-log")
    assert r.status_code == 200, r.text
    return r.json()


def _p41v_eintrag(verlauf, aktion):
    treffer = [e for e in verlauf if e["action"] == aktion]
    assert len(treffer) == 1, treffer
    return treffer[0]


def _p41v_aenderungen(client, order):
    """Je eine Änderung an Kopf und Positionen der bestätigten Bestellung —
    UPDATE, ADD_LINE, UPDATE_LINE, DELETE_LINE (sales.py, _create_audit_log)."""
    basis = f"/api/v1/sales/orders/{order['id']}"
    erste, zweite = order["lines"][0], order["lines"][1]
    r = client.patch(basis, json={"notes": "Tor 2", "change_reason": "Kunde rief an"})
    assert r.status_code == 200, r.text
    r = client.post(f"{basis}/lines", json={
        "product_name": "Senf-Schale", "quantity": 1, "unit": "STK", "unit_price": "2.80"})
    assert r.status_code == 201, r.text
    r = client.patch(f"{basis}/lines/{erste['id']}", json={"quantity": 6})
    assert r.status_code == 200, r.text
    r = client.delete(f"{basis}/lines/{zweite['id']}")
    assert r.status_code == 204, r.text


class TestP41VVerlaufWer:
    """Gernot sieht im Verlauf, wer etwas geändert hat. Statuswechsel und Importe
    speichern den Benutzernamen schon (order_status_service.setze_status,
    imports); Änderungen an Kopf und Positionen (sales._create_audit_log) bisher
    nur die Benutzer-ID — die Oberfläche hätte keinen Namen."""

    @pytest.mark.parametrize("aktion", ["UPDATE", "ADD_LINE", "UPDATE_LINE", "DELETE_LINE"])
    def test_aenderung_nennt_den_benutzer(self, client, aktion):
        order = _p41v_bestellung(client)
        _p41v_als("admin", name="gernot")
        _p41v_aenderungen(client, order)

        eintrag = _p41v_eintrag(_p41v_verlauf(client, order), aktion)

        assert eintrag["user_name"] == "gernot"
        assert eintrag["user_id"] == _P41V_USER_ID

    def test_statuswechsel_und_grund_wie_bisher(self, client):
        """Wächter: CONFIRM trug den Namen schon, UPDATE den Änderungsgrund."""
        order = _p41v_bestellung(client)
        _p41v_aenderungen(client, order)
        verlauf = _p41v_verlauf(client, order)

        bestaetigt = _p41v_eintrag(verlauf, "CONFIRM")
        assert bestaetigt["user_name"] == "testuser"
        assert (bestaetigt["old_values"], bestaetigt["new_values"]) == (
            {"status": "ENTWURF"}, {"status": "BESTAETIGT"})
        assert _p41v_eintrag(verlauf, "UPDATE")["reason"] == "Kunde rief an"

    def test_geaenderte_position_nennt_nummer_und_produkt(self, client):
        """UPDATE_LINE trug nur Menge, Preis, Steuersatz und Rabatt — welche
        Position, stand nirgends (line_id setzt _create_audit_log nicht)."""
        order = _p41v_bestellung(client)
        _p41v_aenderungen(client, order)

        eintrag = _p41v_eintrag(_p41v_verlauf(client, order), "UPDATE_LINE")

        assert eintrag["new_values"].get("position") == 1
        assert eintrag["new_values"].get("product") == "Erbsen-Schale"
        assert Decimal(eintrag["old_values"]["quantity"]) == 4
        assert Decimal(eintrag["new_values"]["quantity"]) == 6


def _p41v_halle_aendert_preis(client):
    """Bestätigte Bestellung; die Halle ändert Menge, Preis und Rabatt der ersten
    Position (per API erlaubt, Paket 3 Q4.8, Frage 4 offen) und packt sie."""
    order = _p41v_bestellung(client)
    _p41v_als("production_staff", name="halle")
    r = client.patch(f"/api/v1/sales/orders/{order['id']}/lines/{order['lines'][0]['id']}",
                     json={"quantity": 6, "unit_price": "3.80", "discount_percent": 10})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/sales/orders/{order['id']}/status", json={"status": "IN_PRODUKTION"})
    assert r.status_code == 200, r.text
    return order


def _p41v_datenkorrektur(order):
    """Eintrag wie aus einem Korrektur-Runbook. Prod (10.10.): RECHNUNG_ZUGEORDNET,
    Name „Systemkorrektur“ mit user_id, alt NULL, neu {"invoice": "RE-…"}. Hier
    bewusst mit erfundenen Schlüsseln auf beiden Seiten (alt invoice_id, neu
    invoice_id/rechnung/betrag): Der Filter muss jeden Schlüssel außerhalb der
    Positivliste wegnehmen, auch in old_values."""
    from app.models.order import OrderAuditLog
    with TestingSessionLocal() as db:
        db.add(OrderAuditLog(
            order_id=uuid.UUID(order["id"]), user_id=None, user_name="Systemkorrektur",
            action="RECHNUNG_ZUGEORDNET",
            old_values={"invoice_id": None},
            new_values={"invoice_id": str(uuid.uuid4()), "rechnung": "RE-2026-09999",
                        "betrag": "123.45"},
            reason="Rechnung zugeordnet (Datenkorrektur)"))
        db.commit()


class TestP41VVerlaufRechte:
    """Den Verlauf lesen alle Rollen des Auftragsrouters (main.py, _deps_auftraege),
    auch die Halle. Logins ohne Konditionssicht (rollen.sieht_konditionen, P4-D.2)
    bekommen nur die Werte aus sales.VERLAUF_WERTE_FUER_ALLE: Preise, Rabatte,
    Steuersätze, Beträge und unbekannte Schlüssel fallen weg, und
    werte_ausgeblendet sagt der Oberfläche, dass etwas fehlt."""

    def test_halle_sieht_menge_aber_keinen_preis_und_rabatt(self, client):
        order = _p41v_halle_aendert_preis(client)

        eintrag = _p41v_eintrag(_p41v_verlauf(client, order), "UPDATE_LINE")

        assert set(eintrag["old_values"]) == {"quantity"}
        assert set(eintrag["new_values"]) == {"position", "product", "quantity"}
        assert eintrag["werte_ausgeblendet"] is True
        assert eintrag["user_name"] == "halle"

    def test_halle_sieht_statuswechsel_vollstaendig(self, client):
        order = _p41v_halle_aendert_preis(client)

        verlauf = _p41v_verlauf(client, order)

        for aktion, alt, neu in (("CONFIRM", "ENTWURF", "BESTAETIGT"),
                                 ("STATUS_CHANGE", "BESTAETIGT", "IN_PRODUKTION")):
            eintrag = _p41v_eintrag(verlauf, aktion)
            assert (eintrag["old_values"], eintrag["new_values"]) == ({"status": alt}, {"status": neu})
            assert eintrag["werte_ausgeblendet"] is False

    def test_halle_sieht_keine_werte_aus_datenkorrekturen(self, client):
        order = _p41v_bestellung(client)
        _p41v_datenkorrektur(order)
        _p41v_als("production_staff", name="halle")

        eintrag = _p41v_eintrag(_p41v_verlauf(client, order), "RECHNUNG_ZUGEORDNET")

        assert (eintrag["old_values"], eintrag["new_values"]) == ({}, {})
        assert eintrag["werte_ausgeblendet"] is True
        assert eintrag["user_name"] == "Systemkorrektur"
        assert eintrag["reason"] == "Rechnung zugeordnet (Datenkorrektur)"

    @pytest.mark.parametrize("rollen", [
        ("admin",), ("sales",), ("accounting",), ("production_planner",),
        ("production_staff", "sales"),  # Zusatzrolle: hat_rolle prüft „mindestens eine“
    ])
    def test_rollen_mit_konditionssicht_sehen_preis_und_rabatt(self, client, rollen):
        order = _p41v_halle_aendert_preis(client)
        _p41v_als(*rollen)

        eintrag = _p41v_eintrag(_p41v_verlauf(client, order), "UPDATE_LINE")

        assert Decimal(eintrag["old_values"]["unit_price"]) == Decimal("4.50")
        assert Decimal(eintrag["new_values"]["unit_price"]) == Decimal("3.80")
        assert Decimal(eintrag["new_values"]["discount_percent"]) == 10
        assert eintrag.get("werte_ausgeblendet", False) is False


class TestP41VVerlaufAnzeige:
    """Aufbereitung des Verlaufs (frontend/src/services/bestellverlauf.ts): die
    Node-Prüfung läuft im Vollauf mit (wie TestP4CBelegstatusAnzeige)."""

    def test_node_pruefung(self):
        import os
        import subprocess
        from pathlib import Path
        r = subprocess.run(
            ["node", "tests/unit/bestellverlauf.check.ts"],
            cwd=Path(__file__).resolve().parents[2] / "frontend",
            env={**os.environ, "TZ": "UTC"}, capture_output=True, text=True, timeout=60,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert r.stdout.strip() == "bestellverlauf.check: 45 Fälle ok"
