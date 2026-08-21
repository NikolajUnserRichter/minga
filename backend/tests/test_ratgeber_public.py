"""Tests für die öffentlichen Ratgeber-Routen."""
import pytest
from fastapi.testclient import TestClient

from app.core import ratgeber
from app.main import app

APEX = {"Host": "novaerp.de"}
TENANT = {"Host": "dev.novaerp.de"}


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setenv("RATGEBER_DB_PATH", str(tmp_path / "ratgeber.db"))
    return TestClient(app)


def _live(slug="erp-einfuehrung", titel="ERP einführen ohne Chaos"):
    ratgeber.save(ratgeber.Article(
        slug=slug, title=titel, cluster="Einführung",
        description="Was ein ERP-Projekt kostet.",
        summary="Scheitert selten an der Software.",
        body="## Vorbereitung\n\nErst Prozesse, dann Software.",
    ))
    return ratgeber.publish(slug)


def test_uebersicht_ist_erreichbar(web):
    _live()
    r = web.get("/ratgeber", headers=APEX)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "ERP einführen ohne Chaos" in r.text


def test_beitrag_wird_serverseitig_ausgeliefert(web):
    _live()
    r = web.get("/ratgeber/erp-einfuehrung", headers=APEX)
    assert r.status_code == 200
    # Ohne JavaScript lesbar — sonst sieht ein Crawler nichts.
    assert "<h1>ERP einführen ohne Chaos</h1>" in r.text
    assert "Erst Prozesse, dann Software." in r.text


def test_entwurf_ist_oeffentlich_nicht_sichtbar(web):
    ratgeber.save(ratgeber.Article(slug="geheim", title="Noch nicht fertig"))
    r = web.get("/ratgeber/geheim", headers=APEX)
    assert r.status_code == 404


def test_unbekannter_beitrag_gibt_404(web):
    r = web.get("/ratgeber/gibt-es-nicht", headers=APEX)
    assert r.status_code == 404


def test_ratgeber_gibt_es_nur_auf_dem_apex(web):
    _live()
    assert web.get("/ratgeber", headers=TENANT).status_code == 404
    assert web.get("/ratgeber/erp-einfuehrung", headers=TENANT).status_code == 404


def test_ungueltiger_slug_wird_abgewiesen(web):
    r = web.get("/ratgeber/Nicht Erlaubt", headers=APEX)
    assert r.status_code == 404


def test_teaser_zeigt_auf_den_folgebeitrag(web):
    _live("lager-optimieren", "Lager optimieren")
    ratgeber.save(ratgeber.Article(
        slug="erp-einfuehrung", title="ERP einführen ohne Chaos",
        teaser_slug="lager-optimieren", status="live",
    ))
    ratgeber.publish("erp-einfuehrung")
    r = web.get("/ratgeber/erp-einfuehrung", headers=APEX)
    assert 'href="/ratgeber/lager-optimieren"' in r.text


def test_teaser_auf_einen_entwurf_wird_nicht_verlinkt(web):
    ratgeber.save(ratgeber.Article(slug="spaeter", title="Kommt noch"))
    _live()
    ratgeber.save(ratgeber.Article(
        slug="erp-einfuehrung", title="ERP einführen ohne Chaos",
        teaser_slug="spaeter", status="live",
    ))
    ratgeber.publish("erp-einfuehrung")
    r = web.get("/ratgeber/erp-einfuehrung", headers=APEX)
    assert "/ratgeber/spaeter" not in r.text
