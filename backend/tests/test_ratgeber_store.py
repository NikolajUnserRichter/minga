"""Tests für die Ratgeber-Datenschicht."""
import pytest

from app.core import ratgeber


@pytest.fixture(autouse=True)
def eigene_db(tmp_path, monkeypatch):
    """Jeder Test bekommt eine frische Datei — die Datenschicht ist global."""
    monkeypatch.setenv("RATGEBER_DB_PATH", str(tmp_path / "ratgeber.db"))


def _beitrag(slug="erp-einfuehrung", **felder):
    daten = dict(
        slug=slug,
        title="ERP einführen ohne Chaos",
        cluster="Einführung",
        description="Was ein ERP-Projekt in einem KMU wirklich kostet.",
        author="Nikolaj Unser-Richter",
        reading_minutes=7,
        summary="Ein ERP-Projekt scheitert selten an der Software.",
        body="## Vorbereitung\n\nErst Prozesse, dann Software.",
    )
    daten.update(felder)
    return ratgeber.Article(**daten)


def test_speichern_und_lesen_gibt_die_felder_zurueck():
    ratgeber.save(_beitrag())
    geladen = ratgeber.get("erp-einfuehrung")
    assert geladen is not None
    assert geladen.title == "ERP einführen ohne Chaos"
    assert geladen.cluster == "Einführung"
    assert geladen.reading_minutes == 7


def test_neuer_beitrag_ist_ein_entwurf():
    ratgeber.save(_beitrag())
    assert ratgeber.get("erp-einfuehrung").status == "entwurf"
    assert ratgeber.get("erp-einfuehrung").published_at is None


def test_speichern_desselben_slugs_aktualisiert_statt_zu_doppeln():
    ratgeber.save(_beitrag())
    ratgeber.save(_beitrag(title="Neuer Titel"))
    alle = ratgeber.list_all()
    assert len(alle) == 1
    assert alle[0].title == "Neuer Titel"


def test_faq_und_quellen_ueberleben_den_roundtrip():
    ratgeber.save(_beitrag(
        faq=[{"frage": "Wie lange dauert das?", "antwort": "Vier bis acht Wochen."}],
        sources=[{"title": "Statistisches Bundesamt", "url": "https://www.destatis.de"}],
    ))
    geladen = ratgeber.get("erp-einfuehrung")
    assert geladen.faq[0]["frage"] == "Wie lange dauert das?"
    assert geladen.sources[0]["url"] == "https://www.destatis.de"


def test_unbekannter_slug_gibt_none():
    assert ratgeber.get("gibt-es-nicht") is None


def test_loeschen_meldet_erfolg_und_misserfolg():
    ratgeber.save(_beitrag())
    assert ratgeber.delete("erp-einfuehrung") is True
    assert ratgeber.delete("erp-einfuehrung") is False
    assert ratgeber.get("erp-einfuehrung") is None


@pytest.mark.parametrize("boeser_slug", [
    "", "Gross", "mit leerzeichen", "../../etc/passwd", "trailing-", "a" * 90,
])
def test_ungueltige_slugs_werden_abgewiesen(boeser_slug):
    with pytest.raises(ratgeber.SlugFehler):
        ratgeber.save(_beitrag(slug=boeser_slug))


def test_liste_filtert_nach_status():
    ratgeber.save(_beitrag("a"))
    ratgeber.save(_beitrag("b", status="live"))
    assert [x.slug for x in ratgeber.list_all(status="live")] == ["b"]
