"""Tests für den Ratgeber-Renderer."""
from app.services.ratgeber_render import render_markdown


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
