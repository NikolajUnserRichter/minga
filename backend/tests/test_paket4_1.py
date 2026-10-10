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
