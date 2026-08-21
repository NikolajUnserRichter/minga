"""Tests für das SEO-Fundament der Marketing-Seite (Apex novaerp.de)."""
from app.core import site


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
