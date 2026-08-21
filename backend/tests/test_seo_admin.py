"""Tests für das SEO/GEO-Admin-Dashboard-API."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

API = "/api/v1/platform/seo"
SCHLUESSEL = "test-admin-key-123"


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setenv("SEO_DB_PATH", str(tmp_path / "seo.db"))
    monkeypatch.setenv("RATGEBER_DB_PATH", str(tmp_path / "ratgeber.db"))
    monkeypatch.setenv("PLATFORM_ADMIN_KEY", SCHLUESSEL)
    for var in ("GEMINI_API_KEY", "GSC_SERVICE_ACCOUNT_JSON", "GSC_SITE_URL",
                "GEO_BUDGET_DAY", "GEO_BUDGET_MONTH"):
        monkeypatch.delenv(var, raising=False)
    return TestClient(app)


def kopf():
    return {"X-Platform-Admin-Key": SCHLUESSEL}


def test_ohne_key_kein_zugriff(web):
    assert web.get(f"{API}/overview").status_code == 401
    assert web.post(f"{API}/run").status_code == 401


def test_overview_liefert_alle_bausteine(web):
    r = web.get(f"{API}/overview", headers=kopf())
    assert r.status_code == 200
    d = r.json()
    assert set(d) >= {"sammler", "gsc", "geo", "grounding",
                      "ai_referrals", "vorschlaege", "protokoll"}
    assert d["sammler"] == {"gsc": False, "geo": False, "firstparty": True}
    assert d["grounding"]["budget_tag"] == 50
    assert d["grounding"]["budget_monat"] == 4500


def test_run_startet_den_nachtlauf(web, monkeypatch):
    from app.services import seo_geo
    monkeypatch.setattr(
        seo_geo, "collect_firstparty",
        lambda tag, stats_fn=None: {"status": "ok", "ki_besuche": 0})
    r = web.post(f"{API}/run", headers=kopf())
    assert r.status_code == 200
    d = r.json()
    assert d["gsc"]["status"] == "inaktiv"
    assert d["geo"]["status"] == "inaktiv"
    assert d["firstparty"]["status"] == "ok"
