"""Tests für die Druck-Warteschlange.

Der ERP-Server steht im Rechenzentrum, der Etikettendrucker im Hofnetz — ein
direkter Druck vom Server aus ist damit ausgeschlossen. Das ERP legt den
fertigen Auftrag hier ab, ein kleiner Agent im Hofnetz holt ihn und schickt ihn
an den Drucker. Diese Tests decken die Übergabe zwischen beiden ab.
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app

UI = "/api/v1/print-jobs"
AGENT = "/api/v1/print-agent"
SCHLUESSEL = "test-print-agent-key-123"


@pytest.fixture
def agent_kopf(monkeypatch):
    """Setzt den Agent-Schlüssel und liefert den passenden Header."""
    monkeypatch.setenv("PRINT_AGENT_KEY", SCHLUESSEL)
    return {"X-Print-Agent-Key": SCHLUESSEL}


@pytest.fixture
def aussaat(client, sample_seed):
    """Eine Aussaat von heute — sonst gibt es nichts zu etikettieren."""
    charge = client.post("/api/v1/seeds/batches", json={
        "seed_id": sample_seed["id"],
        "charge_nummer": "DRUCK-1",
        "menge_gramm": 1000,
        "lieferdatum": date.today().isoformat(),
    })
    assert charge.status_code in (200, 201), charge.text

    r = client.post("/api/v1/production/grow-batches", json={
        "seed_batch_id": charge.json()["id"],
        "tray_anzahl": 4,
        "aussaat_datum": date.today().isoformat(),
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def auftrag_anlegen(client, **params):
    """Reiht den Etikettenbogen des heutigen Tages in die Warteschlange ein."""
    return client.post(f"{UI}/aussaat-etiketten", params={
        "datum": date.today().isoformat(), **params
    })


class TestAuftragEinreihen:
    """Das ERP legt den Auftrag ab — mit fertigem PDF."""

    def test_auftrag_traegt_das_fertige_dokument(self, client, aussaat):
        r = auftrag_anlegen(client)

        assert r.status_code == 201, r.text
        auftrag = r.json()
        assert auftrag["status"] == "OFFEN"
        assert auftrag["dateiname"].endswith(".pdf")
        # Die Bytes gehören nicht in die Liste — nur ihre Größe verrät,
        # dass wirklich ein PDF hinterlegt ist.
        assert auftrag["groesse_bytes"] > 0
        assert "dokument" not in auftrag

    def test_ohne_aussaat_kein_auftrag(self, client):
        r = auftrag_anlegen(client)
        assert r.status_code == 404, r.text

    def test_unbekanntes_format_wird_abgelehnt(self, client, aussaat):
        r = auftrag_anlegen(client, format="gibts-nicht")
        assert r.status_code == 400, r.text

    def test_kopien_und_drucker_werden_uebernommen(self, client, aussaat):
        r = auftrag_anlegen(client, kopien=3, drucker="Rollendrucker Halle")
        assert r.status_code == 201, r.text
        assert r.json()["kopien"] == 3
        assert r.json()["drucker"] == "Rollendrucker Halle"

    def test_liste_zeigt_offene_auftraege(self, client, aussaat):
        auftrag_anlegen(client)
        r = client.get(UI, params={"status": "OFFEN"})
        assert r.status_code == 200, r.text
        assert len(r.json()) == 1


class TestAgentZugang:
    """Der Agent kommt nur mit eigenem Schlüssel rein."""

    def test_ohne_schluessel_kein_zugriff(self, client, agent_kopf):
        assert client.get(f"{AGENT}/jobs").status_code == 401

    def test_falscher_schluessel_wird_abgewiesen(self, client, agent_kopf):
        r = client.get(f"{AGENT}/jobs", headers={"X-Print-Agent-Key": "falsch"})
        assert r.status_code == 401

    def test_ohne_konfiguration_ist_der_zugang_zu(self, client, monkeypatch):
        # Kein PRINT_AGENT_KEY gesetzt → die Schnittstelle bleibt geschlossen,
        # statt versehentlich offen zu stehen.
        monkeypatch.delenv("PRINT_AGENT_KEY", raising=False)
        r = client.get(f"{AGENT}/jobs", headers={"X-Print-Agent-Key": SCHLUESSEL})
        assert r.status_code == 503


class TestAgentAbarbeiten:
    """Holen, drucken, zurückmelden."""

    def test_offene_auftraege_abholen(self, client, aussaat, agent_kopf):
        auftrag_anlegen(client)
        r = client.get(f"{AGENT}/jobs", headers=agent_kopf)

        assert r.status_code == 200, r.text
        assert len(r.json()) == 1
        assert r.json()[0]["status"] == "OFFEN"

    def test_uebernehmen_sperrt_gegen_den_zweiten_agenten(self, client, aussaat, agent_kopf):
        auftrag = auftrag_anlegen(client).json()

        erste = client.post(f"{AGENT}/jobs/{auftrag['id']}/claim", headers=agent_kopf)
        assert erste.status_code == 200, erste.text
        assert erste.json()["status"] == "IN_ARBEIT"

        # Zweiter Agent (oder ein Neustart mitten im Lauf) darf denselben
        # Auftrag nicht ein zweites Mal drucken.
        zweite = client.post(f"{AGENT}/jobs/{auftrag['id']}/claim", headers=agent_kopf)
        assert zweite.status_code == 409, zweite.text

    def test_uebernommener_auftrag_taucht_nicht_mehr_in_der_liste_auf(self, client, aussaat, agent_kopf):
        auftrag = auftrag_anlegen(client).json()
        client.post(f"{AGENT}/jobs/{auftrag['id']}/claim", headers=agent_kopf)

        r = client.get(f"{AGENT}/jobs", headers=agent_kopf)
        assert r.json() == []

    def test_dokument_kommt_als_pdf(self, client, aussaat, agent_kopf):
        auftrag = auftrag_anlegen(client).json()

        r = client.get(f"{AGENT}/jobs/{auftrag['id']}/document", headers=agent_kopf)

        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")

    def test_erfolg_melden(self, client, aussaat, agent_kopf):
        auftrag = auftrag_anlegen(client).json()
        client.post(f"{AGENT}/jobs/{auftrag['id']}/claim", headers=agent_kopf)

        r = client.post(f"{AGENT}/jobs/{auftrag['id']}/complete", headers=agent_kopf)

        assert r.status_code == 200, r.text
        assert r.json()["status"] == "GEDRUCKT"
        assert r.json()["erledigt_am"]

    def test_fehler_melden_haelt_den_grund_fest(self, client, aussaat, agent_kopf):
        auftrag = auftrag_anlegen(client).json()
        client.post(f"{AGENT}/jobs/{auftrag['id']}/claim", headers=agent_kopf)

        r = client.post(
            f"{AGENT}/jobs/{auftrag['id']}/fail",
            json={"fehler": "Kein Papier"},
            headers=agent_kopf,
        )

        assert r.status_code == 200, r.text
        assert r.json()["status"] == "FEHLER"
        assert r.json()["fehler"] == "Kein Papier"

    def test_unbekannter_auftrag_gibt_404(self, client, agent_kopf):
        fehlt = "00000000-0000-0000-0000-0000000000ff"
        assert client.post(f"{AGENT}/jobs/{fehlt}/claim", headers=agent_kopf).status_code == 404
        assert client.get(f"{AGENT}/jobs/{fehlt}/document", headers=agent_kopf).status_code == 404


class TestNochmalDrucken:
    """Papierstau, falsche Rolle, Drucker aus — der Auftrag muss zurück."""

    def test_fehlgeschlagener_auftrag_geht_zurueck_in_die_schlange(self, client, aussaat, agent_kopf):
        auftrag = auftrag_anlegen(client).json()
        client.post(f"{AGENT}/jobs/{auftrag['id']}/claim", headers=agent_kopf)
        client.post(f"{AGENT}/jobs/{auftrag['id']}/fail",
                    json={"fehler": "Kein Papier"}, headers=agent_kopf)

        r = client.post(f"{UI}/{auftrag['id']}/requeue")

        assert r.status_code == 200, r.text
        assert r.json()["status"] == "OFFEN"
        assert r.json()["fehler"] is None
        # Und der Agent sieht ihn wieder.
        assert len(client.get(f"{AGENT}/jobs", headers=agent_kopf).json()) == 1

    def test_haengengebliebener_auftrag_geht_auch_zurueck(self, client, aussaat, agent_kopf):
        # Agent abgestürzt nach dem Übernehmen: der Auftrag steht auf
        # IN_ARBEIT und würde sonst für immer liegen bleiben.
        auftrag = auftrag_anlegen(client).json()
        client.post(f"{AGENT}/jobs/{auftrag['id']}/claim", headers=agent_kopf)

        r = client.post(f"{UI}/{auftrag['id']}/requeue")

        assert r.status_code == 200, r.text
        assert r.json()["status"] == "OFFEN"
