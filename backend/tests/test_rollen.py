"""Rollen-Durchsetzung an den API-Routern.

Anlass: Für den Tablet-Rollout in der Produktion bekommen Mitarbeiter eigene
Logins. Bis hierher war ``require_role`` zwar vorhanden, aber an KEINEM
Endpunkt verdrahtet — jedes Login mit Schreibrolle kam überall hin, auch an
Rechnungen, Preise und Kundendaten.

Geprüft wird grob auf Router-Ebene: welche Rolle erreicht welchen Bereich.
Lesen und Schreiben sind bewusst noch nicht getrennt.
"""
from datetime import date

import pytest

from app.api.deps import get_current_user
from app.main import app

ALLE_ROLLEN = ["admin", "sales", "production_planner", "production_staff", "accounting"]


def _als(rollen: list[str]):
    """Hängt den Test-Client an ein Login mit genau diesen Rollen."""
    async def override():
        return {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "username": "test", "email": "test@example.com",
            "roles": rollen,
        }
    app.dependency_overrides[get_current_user] = override


@pytest.fixture
def als_rolle(client):
    """Client, dessen Rolle je Test gesetzt wird; danach zurück auf Vollzugriff."""
    yield _als
    _als(ALLE_ROLLEN)


HEUTE = date.today().isoformat()

# Bereiche, die der Tablet-Nutzer in der Produktion braucht …
PRODUKTION = [
    ("GET", f"/api/v1/production/day-plan?target_date={HEUTE}"),
    ("GET", "/api/v1/production/grow-batches"),
    ("GET", "/api/v1/inventory/seeds"),
    ("GET", "/api/v1/seeds"),
    ("GET", "/api/v1/staff-shifts"),
]
# … und die, die ihn nichts angehen.
KAUFMAENNISCH = [
    ("GET", "/api/v1/invoices"),
    ("GET", "/api/v1/sales/customers"),
    ("GET", "/api/v1/analytics/revenue"),
    ("GET", "/api/v1/admin/settings"),
]


def _status(client, methode, pfad):
    """Statuscode — hier zählt nur, ob die Rolle durchkommt.

    Ein Endpunkt darf auf der leeren Test-DB auch scheitern (z.B. weil
    /analytics/revenue Postgres-Syntax nutzt); das ist ein anderer Fehler und
    für die Berechtigungsfrage einerlei.
    """
    try:
        return client.request(methode, pfad).status_code
    except Exception:
        return 500


class TestProduktionsMitarbeiter:
    """production_staff — Tablet in der Halle."""

    def test_darf_in_die_produktion(self, client, als_rolle):
        als_rolle(["production_staff"])
        for methode, pfad in PRODUKTION:
            code = _status(client, methode, pfad)
            assert code != 403, f"{pfad} sollte für die Produktion offen sein, war {code}"

    def test_kommt_nicht_an_rechnungen_preise_kunden(self, client, als_rolle):
        als_rolle(["production_staff"])
        for methode, pfad in KAUFMAENNISCH:
            assert _status(client, methode, pfad) == 403, f"{pfad} muss gesperrt sein"

    def test_packliste_bleibt_erreichbar(self, client, als_rolle):
        """Der Packlisten-Knopf im Tagesplan geht über die Belegkette —
        ohne diesen Zugang wäre das Verpacken am Tablet nicht möglich."""
        als_rolle(["production_staff"])
        code = _status(client, "GET", "/api/v1/sales/delivery-notes/"
                                      "00000000-0000-0000-0000-0000000000ff/pdf")
        assert code != 403, f"Belegkette muss für die Produktion offen sein, war {code}"


class TestVertrieb:
    def test_darf_kunden_und_rechnungen(self, client, als_rolle):
        als_rolle(["sales"])
        for pfad in ["/api/v1/sales/customers", "/api/v1/invoices"]:
            assert _status(client, "GET", pfad) != 403, pfad

    def test_nicht_in_die_produktionssteuerung(self, client, als_rolle):
        als_rolle(["sales"])
        assert _status(client, "GET", f"/api/v1/production/day-plan?target_date={HEUTE}") == 403

    def test_nicht_in_die_einstellungen(self, client, als_rolle):
        als_rolle(["sales"])
        assert _status(client, "GET", "/api/v1/admin/settings") == 403


class TestBuchhaltung:
    def test_darf_rechnungen_und_auswertungen(self, client, als_rolle):
        als_rolle(["accounting"])
        for pfad in ["/api/v1/invoices", "/api/v1/analytics/revenue"]:
            assert _status(client, "GET", pfad) != 403, pfad

    def test_nicht_in_die_produktionssteuerung(self, client, als_rolle):
        als_rolle(["accounting"])
        assert _status(client, "GET", "/api/v1/production/grow-batches") == 403


class TestProduktionsplanung:
    def test_darf_produktion_und_prognosen(self, client, als_rolle):
        als_rolle(["production_planner"])
        for pfad in [f"/api/v1/production/day-plan?target_date={HEUTE}",
                     "/api/v1/forecasting/forecasts"]:
            assert _status(client, "GET", pfad) != 403, pfad

    def test_nicht_an_rechnungen(self, client, als_rolle):
        als_rolle(["production_planner"])
        assert _status(client, "GET", "/api/v1/invoices") == 403


class TestAdmin:
    def test_kommt_ueberall_hin(self, client, als_rolle):
        als_rolle(["admin"])
        for methode, pfad in PRODUKTION + KAUFMAENNISCH:
            code = _status(client, methode, pfad)
            assert code != 403, f"Admin darf {pfad}, war {code}"


class TestOhneRolle:
    def test_login_ohne_rolle_kommt_nirgends_hin(self, client, als_rolle):
        """Ein frisch angelegter Keycloak-User ohne Rollenzuweisung darf
        nichts — sonst wäre ein Zuweisungsfehler ein stiller Vollzugriff."""
        als_rolle([])
        for methode, pfad in PRODUKTION + KAUFMAENNISCH:
            assert _status(client, methode, pfad) == 403, pfad
