"""Tests für die SEO/GEO-Sammler."""
from datetime import date

import pytest

from app.core import seo_store
from app.services import seo_geo
from app.services.geo_prompts import PROMPTS


@pytest.fixture(autouse=True)
def saubere_umgebung(tmp_path, monkeypatch):
    """Frische DB, keine Zugangsdaten aus der echten Umgebung."""
    monkeypatch.setenv("SEO_DB_PATH", str(tmp_path / "seo.db"))
    monkeypatch.setenv("RATGEBER_DB_PATH", str(tmp_path / "ratgeber.db"))
    for var in ("GEMINI_API_KEY", "GSC_SERVICE_ACCOUNT_JSON", "GSC_SITE_URL",
                "GEO_BUDGET_DAY", "GEO_BUDGET_MONTH"):
        monkeypatch.delenv(var, raising=False)


def test_promptbibliothek_ist_vollstaendig_und_eindeutig():
    ids = [p["id"] for p in PROMPTS]
    assert len(ids) == 28
    assert len(set(ids)) == 28
    assert {p["art"] for p in PROMPTS} == {"discovery", "marke"}
    assert sum(1 for p in PROMPTS if p["art"] == "marke") == 8
    # Discovery-Prompts dürfen die Marke nicht nennen — sonst misst die
    # Discovery-Quote keine Entdeckung, sondern Markenbekanntheit.
    for p in PROMPTS:
        if p["art"] == "discovery":
            assert "novaerp" not in p["text"].lower(), p["id"]
        assert p["text"].strip().endswith("?")


# --- GEO-Messung -------------------------------------------------------------


def _antwort_mit(domain):
    return {"candidates": [{"groundingMetadata": {"groundingChunks": [
        {"web": {"uri": f"https://{domain}/x", "title": domain}}]}}]}


def test_geo_ohne_key_ist_inaktiv():
    assert seo_geo.measure_geo(date(2026, 8, 21))["status"] == "inaktiv"


def test_geo_misst_zitate_und_zaehlt_verbrauch(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    aufrufe = []

    def fake_post(url, **kwargs):
        aufrufe.append(url)
        return _antwort_mit("novaerp.de" if len(aufrufe) == 1 else "sap.com")

    ergebnis = seo_geo.measure_geo(date(2026, 8, 21), post=fake_post)
    assert ergebnis == {"status": "ok", "gemessen": 28, "uebersprungen": 0}
    z = seo_store.geo_summary(days=1, heute=date(2026, 8, 21))
    assert z["discovery"]["laeufe"] + z["marke"]["laeufe"] == 28
    assert z["discovery"]["zitiert"] == 1  # nur der erste Prompt traf novaerp.de
    assert seo_store.grounding_spent("2026-08-21") == (28, 28)


def test_tagesriegel_stoppt_vor_dem_request(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("GEO_BUDGET_DAY", "5")
    aufrufe = []

    def fake_post(url, **kwargs):
        aufrufe.append(url)
        return _antwort_mit("sap.com")

    ergebnis = seo_geo.measure_geo(date(2026, 8, 21), post=fake_post)
    assert len(aufrufe) == 5
    assert ergebnis == {"status": "ok", "gemessen": 5, "uebersprungen": 23}
    assert any("Kostenriegel" in e["nachricht"]
               for e in seo_store.changelog_entries())


def test_monatsriegel_greift_ohne_einen_einzigen_request(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("GEO_BUDGET_MONTH", "10")
    seo_store.grounding_increment("2026-08-01", 10)

    def explodiert(url, **kwargs):
        raise AssertionError("Bei erschöpftem Monatsbudget darf kein Request rausgehen")

    ergebnis = seo_geo.measure_geo(date(2026, 8, 21), post=explodiert)
    assert ergebnis == {"status": "ok", "gemessen": 0, "uebersprungen": 28}


def test_budget_status_meldet_verbrauch_und_grenzen():
    seo_store.grounding_increment("2026-08-21", 7)
    status = seo_geo.budget_status(heute=date(2026, 8, 21))
    assert status == {"heute": 7, "monat": 7, "budget_tag": 50, "budget_monat": 4500}
