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


# --- Search Console ----------------------------------------------------------


def test_gsc_ohne_zugang_ist_inaktiv():
    assert seo_geo.collect_gsc(date(2026, 8, 18))["status"] == "inaktiv"


def test_gsc_zugang_aus_datei(tmp_path, monkeypatch):
    datei = tmp_path / "sa.json"
    datei.write_text('{"client_email": "a@b", "private_key": "k"}', encoding="utf-8")
    monkeypatch.setenv("GSC_SERVICE_ACCOUNT_JSON", str(datei))
    assert seo_geo._gsc_zugang()["client_email"] == "a@b"


def test_gsc_holt_token_und_speichert_zeilen(monkeypatch):
    monkeypatch.setenv("GSC_SITE_URL", "sc-domain:novaerp.de")
    monkeypatch.setenv(
        "GSC_SERVICE_ACCOUNT_JSON",
        '{"client_email": "seo@p.iam.gserviceaccount.com", "private_key": "test"}',
    )
    # Ein echter RS256-Key hat im Test nichts verloren — die Signatur wird ersetzt.
    monkeypatch.setattr(seo_geo, "_signierte_assertion", lambda zugang: "test-jwt")
    aufrufe = []

    def fake_post(url, json_body=None, data=None, headers=None, **kw):
        aufrufe.append(url)
        if "oauth2" in url:
            assert data["assertion"] == "test-jwt"
            return {"access_token": "zugriff"}
        assert headers["Authorization"] == "Bearer zugriff"
        assert "sc-domain%3Anovaerp.de" in url
        assert json_body["dimensions"] == ["page", "query"]
        return {"rows": [{"keys": ["https://novaerp.de/", "erp kmu"],
                          "clicks": 3, "impressions": 50, "position": 7.2}]}

    ergebnis = seo_geo.collect_gsc(date(2026, 8, 18), post=fake_post)
    assert ergebnis == {"status": "ok", "zeilen": 1}
    assert len(aufrufe) == 2
    z = seo_store.gsc_summary(days=28, heute=date(2026, 8, 21))
    assert z["totals"] == {"clicks": 3, "impressions": 50}


# --- First-Party-Signal und Nachtlauf ----------------------------------------


def test_firstparty_zaehlt_nur_ki_verweise():
    def fake_stats(days=1):
        return {"top_referrers": [
            {"ref": "https://chatgpt.com/", "views": 3},
            {"ref": "https://www.google.com/", "views": 50},
            {"ref": "https://perplexity.ai/search", "views": 2},
        ]}

    ergebnis = seo_geo.collect_firstparty(date(2026, 8, 21), stats_fn=fake_stats)
    assert ergebnis == {"status": "ok", "ki_besuche": 5}
    z = seo_store.ai_referrals_summary(days=7, heute=date(2026, 8, 21))
    assert z["gesamt"] == 5


def test_sammler_status_ohne_zugangsdaten():
    assert seo_geo.sammler_status() == {
        "gsc": False, "geo": False, "firstparty": True}


def test_nightly_isoliert_fehler_einzelner_sammler(monkeypatch):
    def kaputt(tag, post=None):
        raise RuntimeError("GSC explodiert")

    monkeypatch.setattr(seo_geo, "collect_gsc", kaputt)
    monkeypatch.setattr(seo_geo, "collect_firstparty",
                        lambda tag, stats_fn=None: {"status": "ok", "ki_besuche": 0})
    ergebnis = seo_geo.nightly(heute=date(2026, 8, 21))
    assert ergebnis["gsc"]["status"] == "fehler"
    assert ergebnis["geo"]["status"] == "inaktiv"  # kein Key in der Testumgebung
    assert ergebnis["firstparty"]["status"] == "ok"
    assert any(e["quelle"] == "nightly" for e in seo_store.changelog_entries())


# --- Vorschläge ---------------------------------------------------------------


def test_vorschlag_fuer_unbedientes_thema():
    seo_store.record_gsc_rows("2026-08-20", [
        {"page": "https://novaerp.de/", "query": "lager software kmu",
         "clicks": 0, "impressions": 120, "position": 18.0},
    ])
    hinweise = seo_geo.suggestions(heute=date(2026, 8, 21))
    assert any(h["art"] == "inhalt" and "lager software kmu" in h["text"]
               for h in hinweise)


def test_kein_vorschlag_wenn_ratgeber_das_thema_traegt():
    from app.core import ratgeber
    ratgeber.save(ratgeber.Article(
        slug="lager-software", title="Lagerverwaltung: die richtige Software für KMU",
        summary="Software-Auswahl fürs Lager.", body="Lager, Software, KMU."))
    ratgeber.publish("lager-software")
    seo_store.record_gsc_rows("2026-08-20", [
        {"page": "https://novaerp.de/", "query": "lager software kmu",
         "clicks": 0, "impressions": 120, "position": 18.0},
    ])
    hinweise = seo_geo.suggestions(heute=date(2026, 8, 21))
    assert not any(h["art"] == "inhalt" for h in hinweise)


def test_vorschlag_bei_schwacher_ctr():
    seo_store.record_gsc_rows("2026-08-20", [
        {"page": "https://novaerp.de/", "query": "erp preise",
         "clicks": 1, "impressions": 200, "position": 4.0},
    ])
    hinweise = seo_geo.suggestions(heute=date(2026, 8, 21))
    assert any(h["art"] == "snippet" and "erp preise" in h["text"]
               for h in hinweise)


def test_geo_null_quote_erzeugt_hinweis():
    for i in range(20):
        seo_store.record_geo_run("2026-08-21", "erp-kmu-allgemein", "discovery",
                                 zitiert=False, domains=["sap.com"])
    hinweise = seo_geo.suggestions(heute=date(2026, 8, 21))
    assert any(h["art"] == "geo" for h in hinweise)
