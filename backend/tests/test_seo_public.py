"""Tests für das SEO-Fundament der Marketing-Seite (Apex novaerp.de)."""
import re

import pytest
from fastapi.testclient import TestClient

from app.core import site
from app.main import app

APEX = {"Host": "novaerp.de"}
WWW = {"Host": "www.novaerp.de"}
TENANT = {"Host": "dev.novaerp.de"}


@pytest.fixture(scope="module")
def web():
    """Client für die öffentlichen Seiten — braucht keine DB-Fixtures."""
    return TestClient(app)


def test_apex_erkennt_root_und_www():
    assert site.is_apex_host("novaerp.de")
    assert site.is_apex_host("www.novaerp.de")


def test_apex_erkennt_admin_und_tenants_nicht():
    assert not site.is_apex_host("admin.novaerp.de")
    assert not site.is_apex_host("demo.novaerp.de")
    assert site.is_admin_host("admin.novaerp.de")
    assert site.is_www_host("www.novaerp.de")
    assert not site.is_www_host("novaerp.de")


def test_canonical_origin_zeigt_auf_die_zieldomain():
    assert site.canonical_origin() == "https://novaerp.de"


def test_marketing_dir_enthaelt_die_startseite():
    assert (site.marketing_dir() / "index.html").is_file()


# --- robots.txt ------------------------------------------------------------


def test_robots_gibt_apex_frei_und_nennt_die_sitemap(web):
    r = web.get("/robots.txt", headers=APEX)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "User-agent: *" in r.text
    assert "Sitemap: https://novaerp.de/sitemap.xml" in r.text


def test_robots_erlaubt_die_ki_crawler(web):
    r = web.get("/robots.txt", headers=APEX)
    for agent in ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"):
        assert f"User-agent: {agent}" in r.text


def test_robots_haelt_api_und_statistik_aus_dem_index(web):
    r = web.get("/robots.txt", headers=APEX)
    assert "Disallow: /api/" in r.text
    assert "Disallow: /stats.html" in r.text


def test_robots_sperrt_tenant_subdomains_komplett(web):
    r = web.get("/robots.txt", headers=TENANT)
    assert r.status_code == 200
    assert r.text.strip() == "User-agent: *\nDisallow: /"
    assert "Sitemap:" not in r.text


# --- sitemap.xml -----------------------------------------------------------


def test_sitemap_listet_alle_statischen_seiten(web):
    r = web.get("/sitemap.xml", headers=APEX)
    assert r.status_code == 200
    assert "xml" in r.headers["content-type"]
    assert r.text.startswith('<?xml version="1.0" encoding="UTF-8"?>')

    locs = re.findall(r"<loc>(.*?)</loc>", r.text)
    assert locs == [
        "https://novaerp.de/",
        "https://novaerp.de/impressum",
        "https://novaerp.de/datenschutz",
        "https://novaerp.de/agb",
    ]


def test_sitemap_nennt_weder_statistik_noch_subdomains(web):
    r = web.get("/sitemap.xml", headers=APEX)
    assert "stats" not in r.text
    assert "dev.novaerp.de" not in r.text


def test_sitemap_gibt_es_nur_auf_dem_apex(web):
    r = web.get("/sitemap.xml", headers=TENANT)
    assert r.status_code == 404
