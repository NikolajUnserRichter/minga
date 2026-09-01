"""Gernot-Feedback vom 24.08. — Tagesplan-Lücken.

(2) Bei einer Misch-Aussaat stand im Tagesplan nur der Mischname; wer mischen
    soll, muss aber sehen, welche Einzelsorten mit wie viel Gramm reingehören.
(3) Beim Verpacken stand die Bestellung ohne Positionen und ohne Weg zur
    Packliste — der Mitarbeiter musste in die Bestellungen wechseln.
"""
from datetime import date, timedelta

import pytest


def _sorte(client, name, **extra):
    r = client.post("/api/v1/seeds", json={
        "name": name, "keimdauer_tage": 2, "wachstumsdauer_tage": 8,
        "erntefenster_min_tage": 9, "erntefenster_optimal_tage": 11,
        "erntefenster_max_tage": 14, "ertrag_gramm_pro_tray": 350, **extra,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _bestand(client, location, seed, charge, gramm):
    r = client.post("/api/v1/inventory/seeds/receive", params={
        "seed_id": seed["id"], "batch_number": charge,
        "quantity": gramm, "unit": "G", "location_id": location["id"],
    })
    assert r.status_code == 201, r.text
    return r.json()


class TestTagesplanMischung:
    """Punkt 2: Einzelsorten der Mischkisten im Tagesplan."""

    def _mix_aussaeen(self, client, sample_location, trays=4):
        komponenten = []
        for nr, gramm in [(1, 20), (2, 30)]:
            sorte = _sorte(client, f"Komponente {nr}")
            _bestand(client, sample_location, sorte, f"KOMP-{nr}", 1000)
            komponenten.append((sorte, gramm))
        mix = _sorte(client, "Brotzeitmix", is_mix=True, mix_components=[
            {"seed_id": s["id"], "gramm_pro_tray": g} for s, g in komponenten
        ])

        r = client.post("/api/v1/production/grow-batches", json={
            "seed_id": mix["id"], "tray_anzahl": trays,
            "aussaat_datum": date.today().isoformat(),
        })
        assert r.status_code in (200, 201), r.text
        return mix

    def test_mischaussaat_listet_einzelsorten(self, client, sample_location):
        self._mix_aussaeen(client, sample_location, trays=4)

        plan = client.get("/api/v1/production/day-plan",
                          params={"target_date": date.today().isoformat()}).json()

        zeile = next(a for a in plan["aussaat"] if a["seed_name"] == "Brotzeitmix")
        komponenten = {k["seed_name"]: k for k in zeile["mix_components"]}
        assert set(komponenten) == {"Komponente 1", "Komponente 2"}
        # 4 Kisten × 20 g bzw. 30 g — der Mitarbeiter sieht die Gesamtmenge
        assert komponenten["Komponente 1"]["gramm_gesamt"] == 80
        assert komponenten["Komponente 2"]["gramm_gesamt"] == 120

    def test_normale_aussaat_bleibt_ohne_komponenten(self, client, sample_seed):
        charge = client.post("/api/v1/seeds/batches", json={
            "seed_id": sample_seed["id"], "charge_nummer": "NORM-1",
            "menge_gramm": 1000, "lieferdatum": date.today().isoformat(),
        })
        assert charge.status_code in (200, 201), charge.text

        r = client.post("/api/v1/production/grow-batches", json={
            "seed_batch_id": charge.json()["id"], "tray_anzahl": 2,
            "aussaat_datum": date.today().isoformat(),
        })
        assert r.status_code in (200, 201), r.text

        plan = client.get("/api/v1/production/day-plan",
                          params={"target_date": date.today().isoformat()}).json()
        zeile = next(a for a in plan["aussaat"] if a["seed_name"] == sample_seed["name"])
        assert zeile["mix_components"] == []


class TestTagesplanVerpacken:
    """Punkt 3: Positionen + Packlisten-Zugriff direkt aus dem Tagesplan."""

    @pytest.fixture
    def bestellung_heute_packen(self, client, sample_customer):
        """Lieferung morgen → Packtag heute."""
        morgen = (date.today() + timedelta(days=1)).isoformat()
        r = client.post("/api/v1/sales/orders", json={
            "customer_id": sample_customer["id"],
            "requested_delivery_date": morgen,
            "lines": [
                {"product_name": "Erbsen-Schale", "quantity": 10, "unit": "STK",
                 "unit_price": 2.50, "tax_rate": "REDUZIERT"},
                {"product_name": "Sonnenblumen-Schale", "quantity": 4, "unit": "STK",
                 "unit_price": 3.00, "tax_rate": "REDUZIERT"},
            ],
        })
        assert r.status_code == 201, r.text
        return r.json()

    def test_verpacken_zeile_traegt_positionen(self, client, bestellung_heute_packen):
        plan = client.get("/api/v1/production/day-plan",
                          params={"target_date": date.today().isoformat()}).json()

        assert len(plan["verpacken"]) == 1
        zeile = plan["verpacken"][0]
        # Ohne die ID kann die Oberfläche keine Packliste anfordern
        assert zeile["order_id"] == bestellung_heute_packen["id"]
        namen = [l["product_name"] for l in zeile["lines"]]
        assert namen == ["Erbsen-Schale", "Sonnenblumen-Schale"]
        assert zeile["lines"][0]["quantity"] == 10
        assert zeile["lines"][0]["unit"] == "STK"

    def test_packliste_aus_der_bestellung_erreichbar(self, client, bestellung_heute_packen):
        """Der Weg, den der Packlisten-Knopf im Tagesplan geht:
        Lieferschein anlegen (Items 1:1 aus der Bestellung) → Packlisten-PDF."""
        order_id = bestellung_heute_packen["id"]

        note = client.post(f"/api/v1/sales/orders/{order_id}/delivery-notes", json={})
        assert note.status_code == 201, note.text

        pdf = client.get(f"/api/v1/sales/delivery-notes/{note.json()['id']}/packing-list/pdf")
        assert pdf.status_code == 200, pdf.text
        assert pdf.content.startswith(b"%PDF")
