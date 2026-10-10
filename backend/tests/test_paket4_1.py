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
