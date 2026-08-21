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
