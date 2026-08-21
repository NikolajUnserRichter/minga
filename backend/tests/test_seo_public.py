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


# --- llms.txt --------------------------------------------------------------


def test_llms_txt_liefert_markdown_mit_kernangaben(web):
    r = web.get("/llms.txt", headers=APEX)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert r.text.startswith("# NovaERP")
    # Verweise müssen absolut auf die Zieldomain zeigen, sonst laufen sie
    # in KI-Antworten ins Leere.
    assert "https://novaerp.de/impressum" in r.text
    assert "https://novaerp.de/datenschutz" in r.text


def test_llms_txt_nennt_die_belegbaren_eckdaten(web):
    r = web.get("/llms.txt", headers=APEX)
    for fakt in ("Falkenstein", "99 €", "299 €", "499 €", "monatlich kündbar"):
        assert fakt in r.text


def test_llms_txt_gibt_es_nur_auf_dem_apex(web):
    r = web.get("/llms.txt", headers=TENANT)
    assert r.status_code == 404


# --- Eine Seite, eine URL --------------------------------------------------


def test_www_wird_dauerhaft_auf_den_apex_geleitet(web):
    r = web.get("/", headers=WWW, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://novaerp.de/"


def test_schraegstrich_variante_wird_normalisiert(web):
    r = web.get("/impressum/", headers=APEX, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://novaerp.de/impressum"


def test_html_endung_wird_normalisiert(web):
    r = web.get("/impressum.html", headers=APEX, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://novaerp.de/impressum"


def test_index_html_zeigt_auf_die_wurzel(web):
    r = web.get("/index.html", headers=APEX, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://novaerp.de/"


def test_kanonische_url_wird_nicht_umgeleitet(web):
    r = web.get("/impressum", headers=APEX, follow_redirects=False)
    assert r.status_code == 200


def test_subdomains_werden_nicht_umgeleitet(web):
    r = web.get("/irgendwas/", headers=TENANT, follow_redirects=False)
    assert r.status_code != 301


# --- 404 und Docroot-Freigabe ----------------------------------------------


def test_unbekannter_apex_pfad_liefert_echtes_404(web):
    r = web.get("/gibt-es-nicht-xyz123", headers=APEX)
    assert r.status_code == 404


def test_404_seite_ist_auf_noindex_gestellt(web):
    r = web.get("/gibt-es-nicht-xyz123", headers=APEX)
    assert "noindex" in r.text


def test_datenbank_im_docroot_wird_nicht_ausgeliefert(web):
    # Liegt tatsächlich dort und wäre sonst als 1,5-MB-Download offen.
    r = web.get("/ruvector.db", headers=APEX)
    assert r.status_code == 404


def test_backup_html_wird_nicht_ausgeliefert(web):
    r = web.get("/index.backup-20260629-220459", headers=APEX)
    assert r.status_code == 404


def test_echte_seiten_werden_weiter_ausgeliefert(web):
    for pfad in ("/", "/impressum", "/og.png", "/shot-dashboard.jpg"):
        assert web.get(pfad, headers=APEX).status_code == 200, pfad


def test_subdomain_behaelt_den_spa_fallback(web):
    # Client-Routing der React-App braucht 200 auf unbekannten Pfaden.
    from app.main import frontend_dist

    if not (frontend_dist / "index.html").exists():
        pytest.skip("React-Build liegt nur im Container vor")
    r = web.get("/produktion/uebersicht", headers=TENANT)
    assert r.status_code == 200
