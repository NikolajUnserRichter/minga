"""Tests für den SEO/GEO-Messdatenspeicher."""
from datetime import date

import pytest

from app.core import seo_store


@pytest.fixture(autouse=True)
def eigene_db(tmp_path, monkeypatch):
    """Jeder Test bekommt eine frische Datei — der Speicher ist global."""
    monkeypatch.setenv("SEO_DB_PATH", str(tmp_path / "seo.db"))


def test_gsc_zeilen_roundtrip_und_idempotenz():
    n = seo_store.record_gsc_rows("2026-08-18", [
        {"page": "https://novaerp.de/", "query": "erp kmu",
         "clicks": 3, "impressions": 80, "position": 6.4},
        {"page": "https://novaerp.de/ratgeber/erp-einfuehrung",
         "query": "erp einführung", "clicks": 1, "impressions": 40, "position": 9.1},
    ])
    assert n == 2
    # Zweiter Import desselben Tages überschreibt statt zu doppeln.
    seo_store.record_gsc_rows("2026-08-18", [
        {"page": "https://novaerp.de/", "query": "erp kmu",
         "clicks": 5, "impressions": 90, "position": 6.0},
    ])
    z = seo_store.gsc_summary(days=28, heute=date(2026, 8, 21))
    assert z["totals"] == {"clicks": 6, "impressions": 130}


def test_gsc_summary_ignoriert_alte_tage():
    seo_store.record_gsc_rows("2026-05-01", [
        {"page": "https://novaerp.de/", "query": "alt",
         "clicks": 99, "impressions": 999, "position": 1.0},
    ])
    seo_store.record_gsc_rows("2026-08-20", [
        {"page": "https://novaerp.de/", "query": "neu",
         "clicks": 2, "impressions": 10, "position": 3.0},
    ])
    z = seo_store.gsc_summary(days=28, heute=date(2026, 8, 21))
    assert z["totals"]["clicks"] == 2
    assert [t["day"] for t in z["per_day"]] == ["2026-08-20"]


def test_top_queries_aggregieren_ueber_seiten():
    seo_store.record_gsc_rows("2026-08-20", [
        {"page": "https://novaerp.de/", "query": "erp kmu",
         "clicks": 3, "impressions": 80, "position": 6.0},
        {"page": "https://novaerp.de/preise", "query": "erp kmu",
         "clicks": 2, "impressions": 50, "position": 8.0},
        {"page": "https://novaerp.de/", "query": "erp einführung",
         "clicks": 1, "impressions": 40, "position": 9.0},
    ])
    top = seo_store.gsc_top_queries(days=28, heute=date(2026, 8, 21))
    assert top[0]["query"] == "erp kmu"
    assert top[0]["clicks"] == 5
    assert top[0]["impressions"] == 130


def test_changelog_neueste_zuerst():
    seo_store.log_change("test", "erster")
    seo_store.log_change("test", "zweiter")
    eintraege = seo_store.changelog_entries()
    assert [e["nachricht"] for e in eintraege][:2] == ["zweiter", "erster"]
    assert eintraege[0]["quelle"] == "test"


# --- GEO-Läufe, Grounding, KI-Verweise --------------------------------------


def test_geo_laeufe_werden_nach_art_getrennt():
    seo_store.record_geo_run("2026-08-21", "erp-kmu", "discovery",
                             zitiert=True, domains=["novaerp.de"])
    seo_store.record_geo_run("2026-08-21", "erp-lager", "discovery",
                             zitiert=False, domains=["sap.com"])
    seo_store.record_geo_run("2026-08-21", "marke-was-ist", "marke",
                             zitiert=True, domains=["novaerp.de"])
    z = seo_store.geo_summary(days=7, heute=date(2026, 8, 21))
    assert z["discovery"] == {"laeufe": 2, "zitiert": 1, "quote": 0.5}
    assert z["marke"]["quote"] == 1.0


def test_unbekannte_art_wird_abgewiesen():
    with pytest.raises(ValueError):
        seo_store.record_geo_run("2026-08-21", "x", "gemischt",
                                 zitiert=False, domains=[])


def test_grounding_zaehler_tag_und_monat():
    seo_store.grounding_increment("2026-08-20", 3)
    seo_store.grounding_increment("2026-08-21", 2)
    seo_store.grounding_increment("2026-08-21")
    assert seo_store.grounding_spent("2026-08-21") == (3, 6)
    # Monatswechsel beginnt bei null.
    assert seo_store.grounding_spent("2026-09-01") == (0, 0)


def test_ai_referrals_pro_tag_ueberschreibbar():
    seo_store.record_ai_referrals("2026-08-21", 2, ["chatgpt.com"])
    seo_store.record_ai_referrals("2026-08-21", 4, ["chatgpt.com", "perplexity.ai"])
    z = seo_store.ai_referrals_summary(days=7, heute=date(2026, 8, 21))
    assert z["gesamt"] == 4
    assert z["per_day"] == [{"day": "2026-08-21", "count": 4}]
