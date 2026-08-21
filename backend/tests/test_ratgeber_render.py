"""Tests für den Ratgeber-Renderer."""
import json
import re

import pytest

from app.core.ratgeber import Article
from app.services.ratgeber_render import (
    article_graph,
    render_article_page,
    render_markdown,
)


def test_ueberschriften_werden_zu_h2_und_h3():
    html = render_markdown("## Vorbereitung\n\n### Details")
    assert "<h2>Vorbereitung</h2>" in html
    assert "<h3>Details</h3>" in html


def test_absaetze_werden_umschlossen():
    html = render_markdown("Erster Absatz.\n\nZweiter Absatz.")
    assert "<p>Erster Absatz.</p>" in html
    assert "<p>Zweiter Absatz.</p>" in html


def test_liste_wird_zu_ul():
    html = render_markdown("- Prozesse\n- Daten\n- Schulung")
    assert html.count("<li>") == 3
    assert "<ul>" in html and "</ul>" in html
    assert "<li>Prozesse</li>" in html


def test_fett_und_links():
    html = render_markdown("Siehe **hier** die [Doku](https://novaerp.de/agb).")
    assert "<strong>hier</strong>" in html
    assert '<a href="https://novaerp.de/agb">Doku</a>' in html


def test_html_im_redaktionstext_wird_escaped():
    html = render_markdown("Ein <script>alert(1)</script> Versuch.")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_javascript_url_wird_nicht_verlinkt():
    html = render_markdown("[klick](javascript:alert(1))")
    assert "javascript:" not in html
    assert "klick" in html


def test_leerer_text_gibt_leeren_string():
    assert render_markdown("") == ""


# --- Beitragsseite ---------------------------------------------------------

LD_BLOCK = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)


@pytest.fixture
def beitrag():
    return Article(
        slug="erp-einfuehrung",
        title="ERP einführen ohne Chaos",
        cluster="Einführung",
        description="Was ein ERP-Projekt in einem KMU wirklich kostet.",
        author="Nikolaj Unser-Richter",
        reading_minutes=7,
        summary="Ein ERP-Projekt scheitert selten an der Software.",
        body="## Vorbereitung\n\nErst Prozesse, dann Software.",
        faq=[{"frage": "Wie lange dauert das?", "antwort": "Vier bis acht Wochen."}],
        sources=[{"title": "Destatis", "url": "https://www.destatis.de"}],
        status="live",
        published_at="2026-08-21",
    )


def test_graph_enthaelt_article_faq_und_breadcrumb(beitrag):
    typen = {k["@type"] for k in article_graph(beitrag)}
    assert {"Article", "FAQPage", "BreadcrumbList"} <= typen


def test_article_knoten_traegt_datum_autor_und_publisher(beitrag):
    knoten = [k for k in article_graph(beitrag) if k["@type"] == "Article"][0]
    assert knoten["headline"] == "ERP einführen ohne Chaos"
    assert knoten["datePublished"] == "2026-08-21"
    assert knoten["author"]["name"] == "Nikolaj Unser-Richter"
    assert knoten["publisher"] == {"@id": "https://novaerp.de/#org"}
    assert knoten["mainEntityOfPage"] == "https://novaerp.de/ratgeber/erp-einfuehrung"


def test_ohne_faq_kein_faq_knoten(beitrag):
    beitrag.faq = []
    typen = {k["@type"] for k in article_graph(beitrag)}
    assert "FAQPage" not in typen


def test_seite_bringt_canonical_kurzfassung_und_quellen(beitrag):
    html = render_article_page(beitrag)
    assert '<link rel="canonical" href="https://novaerp.de/ratgeber/erp-einfuehrung"' in html
    assert "Ein ERP-Projekt scheitert selten an der Software." in html
    assert 'href="https://www.destatis.de"' in html
    assert "<h1>ERP einführen ohne Chaos</h1>" in html
    assert "7 Min" in html


def test_seiten_schema_ist_valides_json(beitrag):
    html = render_article_page(beitrag)
    bloecke = [json.loads(b) for b in LD_BLOCK.findall(html)]
    assert bloecke and "@graph" in bloecke[0]


def test_titel_mit_sonderzeichen_bricht_das_markup_nicht():
    boese = Article(slug="x", title='Titel mit " und <b>', status="live")
    html = render_article_page(boese)
    assert "<b>" not in html.split("<body")[0]
    assert json.loads(LD_BLOCK.findall(html)[0])  # JSON bleibt lesbar


def test_teaser_verlinkt_den_folgebeitrag(beitrag):
    nachfolger = Article(slug="lager-optimieren", title="Lager optimieren",
                         summary="Weniger Kapital im Regal.", status="live")
    html = render_article_page(beitrag, nachfolger=nachfolger)
    assert 'href="/ratgeber/lager-optimieren"' in html
    assert "Lager optimieren" in html
