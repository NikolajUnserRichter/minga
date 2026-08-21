"""Tests für die Ratgeber-Admin-API."""
import pytest
from fastapi.testclient import TestClient

from app.core import ratgeber
from app.main import app

API = "/api/v1/platform/ratgeber"
SCHLUESSEL = "test-admin-key-123"


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setenv("RATGEBER_DB_PATH", str(tmp_path / "ratgeber.db"))
    monkeypatch.setenv("PLATFORM_ADMIN_KEY", SCHLUESSEL)
    return TestClient(app)


def kopf():
    return {"X-Platform-Admin-Key": SCHLUESSEL}


ENTWURF = {
    "title": "ERP einführen ohne Chaos",
    "cluster": "Einführung",
    "description": "Was ein ERP-Projekt kostet.",
    "author": "Nikolaj Unser-Richter",
    "reading_minutes": 7,
    "summary": "Scheitert selten an der Software.",
    "body": "## Vorbereitung\n\nErst Prozesse, dann Software.",
    "faq": [{"frage": "Wie lange?", "antwort": "Vier bis acht Wochen."}],
    "sources": [{"title": "Destatis", "url": "https://www.destatis.de"}],
}


def test_ohne_key_kein_zugriff(web):
    assert web.get(API).status_code == 401
    assert web.put(f"{API}/x", json=ENTWURF).status_code == 401


def test_falscher_key_wird_abgewiesen(web):
    r = web.get(API, headers={"X-Platform-Admin-Key": "falsch"})
    assert r.status_code == 401


def test_anlegen_lesen_und_auflisten(web):
    r = web.put(f"{API}/erp-einfuehrung", json=ENTWURF, headers=kopf())
    assert r.status_code == 200
    assert r.json()["status"] == "entwurf"

    r = web.get(f"{API}/erp-einfuehrung", headers=kopf())
    assert r.json()["title"] == "ERP einführen ohne Chaos"
    assert r.json()["faq"][0]["frage"] == "Wie lange?"

    r = web.get(API, headers=kopf())
    assert [x["slug"] for x in r.json()["articles"]] == ["erp-einfuehrung"]


def test_ungueltiger_slug_gibt_400(web):
    r = web.put(f"{API}/Gross Und Falsch", json=ENTWURF, headers=kopf())
    assert r.status_code == 400


def test_veroeffentlichen_und_zurueckziehen(web):
    web.put(f"{API}/erp-einfuehrung", json=ENTWURF, headers=kopf())
    r = web.post(f"{API}/erp-einfuehrung/publish", headers=kopf())
    assert r.status_code == 200
    assert r.json()["status"] == "live"
    assert r.json()["published_at"]

    r = web.post(f"{API}/erp-einfuehrung/unpublish", headers=kopf())
    assert r.json()["status"] == "entwurf"


def test_veroeffentlichen_eines_unbekannten_beitrags_gibt_404(web):
    r = web.post(f"{API}/gibt-es-nicht/publish", headers=kopf())
    assert r.status_code == 404


def test_vorschau_rendert_auch_entwuerfe(web):
    web.put(f"{API}/erp-einfuehrung", json=ENTWURF, headers=kopf())
    r = web.get(f"{API}/erp-einfuehrung/preview", headers=kopf())
    assert r.status_code == 200
    assert "<h1>ERP einführen ohne Chaos</h1>" in r.text


def test_loeschen(web):
    web.put(f"{API}/erp-einfuehrung", json=ENTWURF, headers=kopf())
    assert web.delete(f"{API}/erp-einfuehrung", headers=kopf()).status_code == 204
    assert web.get(f"{API}/erp-einfuehrung", headers=kopf()).status_code == 404


def test_warteschlange_sortieren(web):
    for slug in ("a", "b", "c"):
        web.put(f"{API}/{slug}", json={**ENTWURF, "status": "warteschlange"},
                headers=kopf())
    r = web.post(f"{API}/queue", json={"slugs": ["c", "a", "b"]}, headers=kopf())
    assert r.status_code == 200
    assert [x.slug for x in ratgeber.list_all(status="warteschlange")] == ["c", "a", "b"]
