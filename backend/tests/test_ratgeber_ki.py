"""Tests für das KI-Redaktionstool des Ratgebers."""
import json
from datetime import date

import pytest

from app.core import ratgeber
from app.services import ratgeber_ki


@pytest.fixture(autouse=True)
def saubere_umgebung(tmp_path, monkeypatch):
    monkeypatch.setenv("RATGEBER_DB_PATH", str(tmp_path / "ratgeber.db"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def _gemini_antwort(artikel: dict) -> dict:
    """Antwort so verpackt, wie generateContent sie liefert."""
    return {"candidates": [{"content": {"parts": [
        {"text": json.dumps(artikel, ensure_ascii=False)}]}}]}


ARTIKEL = {
    "title": "ERP-Einführung im KMU",
    "description": "So gelingt die Einführung.",
    "summary": "Kurz gefasst.",
    "body": "## Anfang\n\nText.",
    "faq": [{"frage": "Wie lange?", "antwort": "Wochen."}],
    "sources": [{"title": "EU-VO 178/2002",
                 "url": "https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:32002R0178"}],
    "cluster": "ERP-Einführung",
    "reading_minutes": 5,
}


def test_slugify_macht_deutsche_themen_zu_slugs():
    assert ratgeber_ki._slugify("ERP-Einführung im KMU") == "erp-einfuehrung-im-kmu"
    assert ratgeber_ki._slugify("Größe & Maße (Teil 2)") == "groesse-masse-teil-2"
    # Länge bleibt unter der Slug-Grenze
    assert len(ratgeber_ki._slugify("x" * 300)) <= 80


def test_ohne_key_klare_fehlermeldung():
    with pytest.raises(ratgeber_ki.KeinSchluessel):
        ratgeber_ki.generate_article("ERP-Einführung im KMU")


def test_generierung_speichert_entwurf(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    anfragen = []

    def fake_post(url, json_body=None, **kw):
        anfragen.append(json_body)
        return _gemini_antwort(ARTIKEL)

    beitrag = ratgeber_ki.generate_article(
        "ERP-Einführung im KMU", cluster="ERP-Einführung", post=fake_post)
    assert beitrag.status == "entwurf"
    assert beitrag.slug == "erp-einfuehrung-im-kmu"
    assert beitrag.title == "ERP-Einführung im KMU"
    assert ratgeber.get(beitrag.slug).faq[0]["frage"] == "Wie lange?"
    # Das Thema steht im Prompt, und es wird OHNE Grounding generiert —
    # das Grounding-Kontingent gehört der GEO-Messung.
    prompt = anfragen[0]["contents"][0]["parts"][0]["text"]
    assert "ERP-Einführung im KMU" in prompt
    assert "tools" not in anfragen[0]


def test_markdown_zaun_um_das_json_wird_toleriert(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    verpackt = json.dumps(ARTIKEL, ensure_ascii=False)

    def fake_post(url, json_body=None, **kw):
        return {"candidates": [{"content": {"parts": [
            {"text": f"```json\n{verpackt}\n```"}]}}]}

    beitrag = ratgeber_ki.generate_article("ERP-Einführung im KMU", post=fake_post)
    assert beitrag.title == "ERP-Einführung im KMU"


def test_kaputte_antwort_wirft_generierungsfehler(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")

    def fake_post(url, json_body=None, **kw):
        return {"candidates": [{"content": {"parts": [{"text": "kein json"}]}}]}

    with pytest.raises(ratgeber_ki.GenerierungFehlgeschlagen):
        ratgeber_ki.generate_article("ERP-Einführung im KMU", post=fake_post)
