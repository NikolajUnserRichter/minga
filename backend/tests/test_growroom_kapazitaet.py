"""Growroom-Stellplatzkapazität — Anforderung Gernot vom 17.09.2026.

Kisten belegen Stellplätze erst ab dem Transfer in den Growroom und geben
sie bei Ernte oder Auslagerung wieder frei, auch in Teilmengen.
"""
from datetime import date, timedelta

import pytest


def _sorte(client, name="Erbse"):
    r = client.post("/api/v1/seeds", json={
        "name": name, "keimdauer_tage": 2, "wachstumsdauer_tage": 8,
        "erntefenster_min_tage": 9, "erntefenster_optimal_tage": 11,
        "erntefenster_max_tage": 14, "ertrag_gramm_pro_tray": 350,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _saatgut_charge(client, seed, nummer="CH-1", gramm="5000"):
    """Echte SeedBatch. NICHT /inventory/seeds/receive nehmen — das liefert
    einen Bestandssatz, dessen ID die Aussaat mit 404 'Saatgut-Charge nicht
    gefunden' ablehnt. Pflichtfelder heißen charge_nummer und menge_gramm."""
    r = client.post("/api/v1/seeds/batches", json={
        "seed_id": seed["id"], "charge_nummer": nummer, "menge_gramm": gramm,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _charge(client, trays=20):
    """Aussaat mit `trays` Kisten, Status KEIMUNG.

    `seed_id` statt `seed_batch_id` funktioniert NUR bei Mischsorten — eine
    normale Sorte quittiert das mit 400 "ist keine Mischsorte".
    """
    seed = _sorte(client)
    saatgut = _saatgut_charge(client, seed)
    r = client.post("/api/v1/production/grow-batches", json={
        "seed_batch_id": saatgut["id"],
        "tray_anzahl": trays,
        "aussaat_datum": date.today().isoformat(),
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


class TestKistenFreigabe:
    """Die Ernte gibt Kisten frei — ganz oder teilweise."""

    def test_ernte_ohne_angabe_leert_alle_kisten(self, client):
        charge = _charge(client, trays=20)
        client.post(f"/api/v1/production/grow-batches/{charge['id']}/status/WACHSTUM")

        r = client.post("/api/v1/production/harvests", json={
            "grow_batch_id": charge["id"],
            "ernte_datum": date.today().isoformat(),
            "menge_gramm": "4200",
        })
        assert r.status_code in (200, 201), r.text
        assert r.json()["entleerte_kisten"] == 20

    def test_teilernte_leert_nur_die_angegebenen_kisten(self, client):
        charge = _charge(client, trays=20)
        client.post(f"/api/v1/production/grow-batches/{charge['id']}/status/WACHSTUM")

        r = client.post("/api/v1/production/harvests", json={
            "grow_batch_id": charge["id"],
            "ernte_datum": date.today().isoformat(),
            "menge_gramm": "1680",
            "entleerte_kisten": 8,
        })
        assert r.status_code in (200, 201), r.text
        assert r.json()["entleerte_kisten"] == 8

    def test_zwei_teilernten_rechnen_aufeinander_auf(self, client):
        """Fängt die Lazy-Loading-Falle: wird batch.harvests nicht geladen,
        ergibt die Summe still 0 und die zweite Ernte darf zu viel entnehmen."""
        charge = _charge(client, trays=20)
        client.post(f"/api/v1/production/grow-batches/{charge['id']}/status/WACHSTUM")

        for kisten in (8, 7):
            r = client.post("/api/v1/production/harvests", json={
                "grow_batch_id": charge["id"],
                "ernte_datum": date.today().isoformat(),
                "menge_gramm": "1400", "entleerte_kisten": kisten,
            })
            assert r.status_code in (200, 201), r.text

        # 20 - 8 - 7 = 5 übrig; 6 müssen abgelehnt werden.
        r = client.post("/api/v1/production/harvests", json={
            "grow_batch_id": charge["id"],
            "ernte_datum": date.today().isoformat(),
            "menge_gramm": "1200", "entleerte_kisten": 6,
        })
        assert r.status_code == 400, r.text
        assert "5" in r.json()["detail"]

    def test_charge_bleibt_nach_teilernte_im_growroom(self, client):
        """Regression gegen das unbedingte GEERNTET in create_harvest."""
        charge = _charge(client, trays=20)
        client.post(f"/api/v1/production/grow-batches/{charge['id']}/status/WACHSTUM")
        client.post("/api/v1/production/harvests", json={
            "grow_batch_id": charge["id"],
            "ernte_datum": date.today().isoformat(),
            "menge_gramm": "1680", "entleerte_kisten": 8,
        })

        status = client.get(f"/api/v1/production/grow-batches/{charge['id']}").json()["status"]
        assert status != "GEERNTET", "Teilgeerntete Charge steht weiter im Growroom"

    def test_letzte_kiste_beendet_die_charge(self, client):
        charge = _charge(client, trays=20)
        client.post(f"/api/v1/production/grow-batches/{charge['id']}/status/WACHSTUM")
        for kisten in (8, 12):
            client.post("/api/v1/production/harvests", json={
                "grow_batch_id": charge["id"],
                "ernte_datum": date.today().isoformat(),
                "menge_gramm": "1680", "entleerte_kisten": kisten,
            })

        status = client.get(f"/api/v1/production/grow-batches/{charge['id']}").json()["status"]
        assert status == "GEERNTET"

    def test_mehr_kisten_als_vorhanden_wird_abgelehnt(self, client):
        charge = _charge(client, trays=20)
        client.post(f"/api/v1/production/grow-batches/{charge['id']}/status/WACHSTUM")

        r = client.post("/api/v1/production/harvests", json={
            "grow_batch_id": charge["id"],
            "ernte_datum": date.today().isoformat(),
            "menge_gramm": "4200",
            "entleerte_kisten": 25,
        })
        assert r.status_code == 400, r.text
        assert "20" in r.json()["detail"]
