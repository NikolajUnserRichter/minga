"""
Tests: Gernot-Feedback vom 17.08.2026 (Backend-Anteil).

Jeder Test bildet EINEN belegten Root Cause ab:
(2a) Abo-Liste expandiert product_name nicht → UUID statt Produktname
(3a) Rechnungs-PDF druckt keine Empfängeranschrift (Legacy-Adressfeld ignoriert)
(6c) Saatgut-Bestandsliste liefert seed_name/location_name nicht
(8b) Tagesplan zeigt manuell angelegte Wachstumschargen nicht
(9)  Packtag ist nicht spezifizierbar (Same-Day statt Vortag)
(10) Verpackungsplan löst Bundles nicht in Komponenten auf
"""
import zlib
from datetime import date, timedelta

import pytest


def pdf_text(raw: bytes) -> str:
    """Extrahiert Text aus einem ReportLab-PDF (ASCII85 + Flate)."""
    from tests.test_documents_preise import _pdf_text

    return _pdf_text(raw).decode("latin-1", errors="ignore")


@pytest.fixture()
def base_unit(client):
    """Basiseinheit 'G' — Produktanlage verlangt sie, es gibt keinen API-Weg dorthin."""
    from app.models.unit import UnitOfMeasure, UnitCategory
    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    try:
        if not db.query(UnitOfMeasure).filter_by(code="G").first():
            db.add(UnitOfMeasure(code="G", name="Gramm", symbol="g",
                                 category=UnitCategory.WEIGHT, is_base_unit=True))
            db.commit()
    finally:
        db.close()


@pytest.fixture()
def seed(client):
    r = client.post("/api/v1/seeds", json={
        "name": "Gartenkresse",
        "keimdauer_tage": 3,
        "wachstumsdauer_tage": 3,
        "erntefenster_min_tage": 6,
        "erntefenster_optimal_tage": 7,
        "erntefenster_max_tage": 8,
        "ertrag_gramm_pro_tray": 350,
        "verlustquote_prozent": 5.0,
    })
    assert r.status_code == 201, r.text
    return r.json()


class TestAboProduktname:
    """(2a) Produkt-Abos zeigten die UUID, weil nur seed_name expandiert wurde."""

    def test_liste_zeigt_produktnamen(self, client, base_unit):
        kunde = client.post("/api/v1/sales/customers", json={
            "name": "Allianz ONE Business Solutions", "typ": "GEWERBE",
        }).json()
        produkt = client.post("/api/v1/products", json={
            "sku": "GM-KAR", "name": "Genussmix Karton",
            "category": "BUNDLE", "base_price": 12.50,
        }).json()
        r = client.post("/api/v1/sales/subscriptions", json={
            "kunde_id": kunde["id"],
            "product_id": produkt["id"],
            "menge": 12,
            "einheit": "STUECK",
            "intervall": "WOECHENTLICH",
            "liefertage": [0],
            "gueltig_von": date.today().isoformat(),
        })
        assert r.status_code == 201, r.text

        items = client.get("/api/v1/sales/subscriptions").json()["items"]
        assert len(items) == 1
        assert items[0]["product_name"] == "Genussmix Karton"


class TestRechnungsadresse:
    """(3a) § 14 UStG verlangt die vollständige Anschrift des Empfängers."""

    def _rechnung_pdf(self, client, kunde_id):
        order = client.post("/api/v1/sales/orders", json={
            "customer_id": kunde_id,
            "requested_delivery_date": date.today().isoformat(),
            "lines": [{"product_name": "Kresse", "quantity": 2, "unit": "STK",
                       "unit_price": 3.0, "tax_rate": "REDUZIERT"}],
        }).json()
        inv = client.post(f"/api/v1/invoices/from-order/{order['id']}")
        assert inv.status_code in (200, 201), inv.text
        pdf = client.get(f"/api/v1/invoices/{inv.json()['id']}/pdf")
        assert pdf.status_code == 200, pdf.text
        return pdf_text(pdf.content)

    def test_strukturierte_adresse_wird_gedruckt(self, client):
        kunde = client.post("/api/v1/sales/customers", json={
            "name": "Firma Klara Düran", "typ": "GASTRO",
        }).json()
        client.post(f"/api/v1/sales/customers/{kunde['id']}/addresses", json={
            "address_type": "BOTH", "strasse": "Musterweg", "hausnummer": "5",
            "plz": "80331", "ort": "München", "is_default": True,
        })
        text = self._rechnung_pdf(client, kunde["id"])
        assert "Musterweg" in text
        assert "80331" in text

    def test_legacy_freitextadresse_wird_gedruckt(self, client):
        """34 von 40 Produktionskunden haben NUR dieses Feld befüllt."""
        kunde = client.post("/api/v1/sales/customers", json={
            "name": "Fruchthof Nagel", "typ": "HANDEL",
            "adresse": "Großmarkthalle 12, 81371 München",
        }).json()
        text = self._rechnung_pdf(client, kunde["id"])
        # ReportLab kodiert Umlaute oktal (M\374nchen) — ASCII-sicher prüfen.
        assert "markthalle" in text
        assert "81371" in text


class TestLagerverwaltungSpalten:
    """(6c) Sorte und Lagerort blieben in der Bestandsliste leer."""

    def test_liste_zeigt_sorte_und_lagerort(self, client, seed):
        loc = client.post("/api/v1/inventory/locations", json={
            "code": "TK1", "name": "Trockenlager", "location_type": "LAGER",
        }).json()
        r = client.post("/api/v1/inventory/seeds/receive", params={
            "seed_id": seed["id"], "batch_number": "2593440281.023025",
            "quantity": 100000, "unit": "G", "location_id": loc["id"],
        })
        assert r.status_code == 201, r.text

        payload = client.get("/api/v1/inventory/seeds").json()
        items = payload["items"] if isinstance(payload, dict) else payload
        assert len(items) == 1
        assert items[0]["seed_name"] == "Gartenkresse"
        assert items[0]["location_name"] == "Trockenlager"


class TestTagesplanAussaat:
    """(8b) Manuell angelegte Chargen tauchten im Tagesplan nicht auf."""

    def test_manuelle_charge_erscheint_unter_aussaat(self, client, seed):
        batch = client.post("/api/v1/seeds/batches", json={
            "seed_id": seed["id"], "charge_nummer": "GK-001", "menge_gramm": 5000,
        }).json()
        r = client.post("/api/v1/production/grow-batches", json={
            "seed_batch_id": batch["id"],
            "tray_anzahl": 4,
            "aussaat_datum": date.today().isoformat(),
        })
        assert r.status_code == 201, r.text

        plan = client.get("/api/v1/production/day-plan",
                          params={"target_date": date.today().isoformat()}).json()
        namen = [a["seed_name"] for a in plan["aussaat"]]
        assert "Gartenkresse" in namen
        assert any(a["trays"] == 4 for a in plan["aussaat"])


class TestPacktag:
    """(9) Verpackt wird am Vortag — der Packtag muss steuerbar sein."""

    def _order(self, client, liefertag, **extra):
        kunde = client.post("/api/v1/sales/customers", json={
            "name": f"Kunde {liefertag}", "typ": "GASTRO",
        }).json()
        payload = {
            "customer_id": kunde["id"],
            "requested_delivery_date": liefertag.isoformat(),
            "lines": [{"product_name": "Kresse", "quantity": 2, "unit": "STK",
                       "unit_price": 3.0, "tax_rate": "REDUZIERT"}],
        }
        payload.update(extra)
        r = client.post("/api/v1/sales/orders", json=payload)
        assert r.status_code == 201, r.text
        return r.json()

    def _plan(self, client, tag):
        return client.get("/api/v1/production/day-plan",
                          params={"target_date": tag.isoformat()}).json()

    def test_verpacken_am_vortag_nicht_am_liefertag(self, client):
        """Ex-Bug: dieselbe Bestellung stand an beiden Tagen unter 'Verpacken'."""
        morgen = date.today() + timedelta(days=1)
        self._order(client, morgen)

        heute_plan = self._plan(client, date.today())
        assert len(heute_plan["verpacken"]) == 1
        assert heute_plan["ausliefern"] == []

        morgen_plan = self._plan(client, morgen)
        assert morgen_plan["verpacken"] == [], "am Liefertag ist bereits verpackt"
        assert len(morgen_plan["ausliefern"]) == 1

    def test_same_day_bestellung_wird_heute_verpackt(self, client):
        """Der Vortag liegt in der Vergangenheit — die Packarbeit darf nicht verschwinden."""
        heute = date.today()
        self._order(client, heute)
        plan = self._plan(client, heute)
        assert len(plan["ausliefern"]) == 1
        assert len(plan["verpacken"]) == 1

    def test_expliziter_packtag_schlaegt_default(self, client):
        liefertag = date.today() + timedelta(days=3)
        self._order(client, liefertag, packing_date=date.today().isoformat())
        plan = client.get("/api/v1/production/day-plan",
                          params={"target_date": date.today().isoformat()}).json()
        assert len(plan["verpacken"]) == 1

    def test_abo_bestellung_faellt_nicht_aus_dem_tagesplan(self, client):
        """Abo-Bestellungen liefern am selben Tag — ohne Packtag-Regel wäre
        ihr Packtag gestern und die Packarbeit unsichtbar."""
        from uuid import UUID

        from sqlalchemy import select

        from app.models.customer import Customer
        from app.models.order import Order, OrderStatus
        from app.tasks.subscription_tasks import _create_order_from_subscription
        from tests.conftest import TestingSessionLocal

        kunde = client.post("/api/v1/sales/customers", json={
            "name": "Abo-Kunde", "typ": "GASTRO",
        }).json()

        db = TestingSessionLocal()
        try:
            class _FakeSub:
                """Minimal-Abo — der Task liest nur diese Felder."""
                id = "abo-1"
                kunde_id = UUID(kunde["id"])
                seed_id = None
                seed = None
                menge = 2
                einheit = "STUECK"

            sub = _FakeSub()
            sub.kunde = db.get(Customer, UUID(kunde["id"]))
            _create_order_from_subscription(db, sub)
            db.commit()

            order = db.execute(
                select(Order).where(Order.status == OrderStatus.ENTWURF)
            ).scalars().first()
            assert order is not None
            assert order.effective_packing_date == date.today()
        finally:
            db.close()

        plan = self._plan(client, date.today())
        assert len(plan["verpacken"]) == 1, "Abo-Bestellung muss im Packen-Block stehen"

    def test_abo_lauf_rechnet_mit_produktpreis(self, client, base_unit, seed):
        """Ex-Bug: `Heute verarbeiten` brach mit Decimal * float ab, sobald das
        Abo-Produkt einen Preis hatte — es entstand keine einzige Bestellung."""
        from decimal import Decimal
        from uuid import UUID

        from sqlalchemy import select

        from app.models.customer import Customer
        from app.models.order import Order, OrderLine
        from app.tasks.subscription_tasks import _create_order_from_subscription
        from tests.conftest import TestingSessionLocal

        produkt = client.post("/api/v1/products", json={
            "sku": "ABO-KR", "name": "Kresse Schale", "category": "MICROGREEN",
            "base_price": 4.5, "seed_id": seed["id"],
        })
        assert produkt.status_code == 201, produkt.text

        kunde = client.post("/api/v1/sales/customers", json={
            "name": "Abo-Kunde Preis", "typ": "GASTRO",
        }).json()

        db = TestingSessionLocal()
        try:
            sorten_id = UUID(seed["id"])

            class _FakeSub:
                id = "abo-2"
                kunde_id = UUID(kunde["id"])
                seed_id = sorten_id
                seed = None
                menge = Decimal("2.00")
                einheit = "STUECK"

            sub = _FakeSub()
            sub.kunde = db.get(Customer, UUID(kunde["id"]))
            _create_order_from_subscription(db, sub)
            db.commit()

            line = db.execute(select(OrderLine)).scalars().first()
            assert line is not None
            assert line.unit_price == Decimal("4.50")
            assert line.line_net == Decimal("9.00")

            order = db.get(Order, line.order_id)
            assert order.total_net == Decimal("9.00")
        finally:
            db.close()


class TestWinterzyklus:
    """(5) Winter braucht einen eigenen Parametersatz, kein pauschales '+x Tage'.

    Sonst weiß der Mitarbeiter nicht, ob die Verzögerung bei der Keimung
    oder im Growroom liegt — und damit nicht, wann er was zu tun hat.
    """

    def _seed_mit_winter(self, client):
        r = client.post("/api/v1/seeds", json={
            "name": "Gartenkresse", "keimdauer_tage": 3, "wachstumsdauer_tage": 3,
            "erntefenster_min_tage": 6, "erntefenster_optimal_tage": 7, "erntefenster_max_tage": 8,
            "ertrag_gramm_pro_tray": 350, "verlustquote_prozent": 5.0,
            # Winter: Keimung 2 Tage länger, Wachstum 1 Tag länger
            "winter_keimdauer_tage": 5,
            "winter_wachstumsdauer_tage": 4,
            "winter_erntefenster_min_tage": 8,
            "winter_erntefenster_optimal_tage": 9,
            "winter_erntefenster_max_tage": 11,
        })
        assert r.status_code == 201, r.text
        return r.json()

    def test_sorte_speichert_getrennte_winterparameter(self, client):
        seed = self._seed_mit_winter(client)
        assert seed["winter_keimdauer_tage"] == 5
        assert seed["winter_wachstumsdauer_tage"] == 4
        assert seed["winter_erntefenster_optimal_tage"] == 9

    def test_winterbetrieb_nutzt_den_winter_satz(self, client):
        seed = self._seed_mit_winter(client)
        client.patch("/api/v1/admin/settings", json={"SEASON_MODE": "WINTER"})

        batch = client.post("/api/v1/seeds/batches", json={
            "seed_id": seed["id"], "charge_nummer": "GK-W1", "menge_gramm": 5000,
        }).json()
        aussaat = date.today()
        r = client.post("/api/v1/production/grow-batches", json={
            "seed_batch_id": batch["id"], "tray_anzahl": 4,
            "aussaat_datum": aussaat.isoformat(),
        })
        assert r.status_code == 201, r.text
        gb = r.json()
        assert gb["erwartete_ernte_min"] == (aussaat + timedelta(days=8)).isoformat()
        assert gb["erwartete_ernte_optimal"] == (aussaat + timedelta(days=9)).isoformat()
        assert gb["erwartete_ernte_max"] == (aussaat + timedelta(days=11)).isoformat()
        # Der Mitarbeiter muss sehen, wann die Keimung endet
        assert gb["keimende_datum"] == (aussaat + timedelta(days=5)).isoformat()

    def test_sommerbetrieb_bleibt_beim_standardsatz(self, client):
        seed = self._seed_mit_winter(client)
        client.patch("/api/v1/admin/settings", json={"SEASON_MODE": "SOMMER"})
        batch = client.post("/api/v1/seeds/batches", json={
            "seed_id": seed["id"], "charge_nummer": "GK-S1", "menge_gramm": 5000,
        }).json()
        aussaat = date.today()
        gb = client.post("/api/v1/production/grow-batches", json={
            "seed_batch_id": batch["id"], "tray_anzahl": 4,
            "aussaat_datum": aussaat.isoformat(),
        }).json()
        assert gb["erwartete_ernte_optimal"] == (aussaat + timedelta(days=7)).isoformat()
        assert gb["keimende_datum"] == (aussaat + timedelta(days=3)).isoformat()


class TestChargenParameter:
    """(7) Chargenabweichungen gehören in die Stammdaten der Charge."""

    def test_charge_traegt_eigene_wachstumsparameter(self, client, seed):
        batch = client.post("/api/v1/seeds/batches", json={
            "seed_id": seed["id"], "charge_nummer": "GK-LANGSAM", "menge_gramm": 5000,
            # Diese Charge keimt langsam — einmal an der Charge hinterlegt,
            # nicht bei jedem Aussaatzyklus neu einzutippen.
            "keimdauer_tage": 5,
            "erntefenster_min_tage": 8,
            "erntefenster_optimal_tage": 9,
            "erntefenster_max_tage": 10,
        })
        assert batch.status_code == 201, batch.text
        assert batch.json()["keimdauer_tage"] == 5

        aussaat = date.today()
        gb = client.post("/api/v1/production/grow-batches", json={
            "seed_batch_id": batch.json()["id"], "tray_anzahl": 4,
            "aussaat_datum": aussaat.isoformat(),
        })
        assert gb.status_code == 201, gb.text
        assert gb.json()["erwartete_ernte_optimal"] == (aussaat + timedelta(days=9)).isoformat()
        assert gb.json()["keimende_datum"] == (aussaat + timedelta(days=5)).isoformat()


class TestBundleAufloesung:
    """(10) Der Produktionsmitarbeiter braucht die Komponentenliste."""

    def test_verpackungsplan_loest_bundle_auf(self, client, base_unit):
        erbse = client.post("/api/v1/products", json={
            "sku": "ERB-1", "name": "Erbse", "category": "MICROGREEN", "base_price": 2.0,
        }).json()
        sonne = client.post("/api/v1/products", json={
            "sku": "SON-1", "name": "Sonnenblume", "category": "MICROGREEN", "base_price": 2.0,
        }).json()
        mix = client.post("/api/v1/products", json={
            "sku": "GM-KAR", "name": "Genussmix Karton", "category": "BUNDLE",
            "base_price": 12.0, "is_bundle": True,
        }).json()
        for child in (erbse, sonne):
            r = client.post(f"/api/v1/products/{mix['id']}/bundle-components", json={
                "child_product_id": child["id"], "quantity": 1,
            })
            assert r.status_code in (200, 201), r.text

        kunde = client.post("/api/v1/sales/customers", json={
            "name": "Fruchthof Nagel", "typ": "HANDEL",
        }).json()
        liefertag = date.today() + timedelta(days=1)
        r = client.post("/api/v1/sales/orders", json={
            "customer_id": kunde["id"],
            "requested_delivery_date": liefertag.isoformat(),
            "lines": [
                {"product_id": mix["id"], "product_name": "Genussmix Karton",
                 "quantity": 5, "unit": "KARTON_6", "unit_price": 12.0, "tax_rate": "REDUZIERT"},
                {"product_id": erbse["id"], "product_name": "Erbse",
                 "quantity": 1, "unit": "STUECK", "unit_price": 2.0, "tax_rate": "REDUZIERT"},
            ],
        })
        assert r.status_code == 201, r.text

        plan = client.get("/api/v1/production/packaging-plan",
                          params={"target_date": date.today().isoformat()}).json()
        komponenten = {k["product_name"]: k for k in plan["komponenten"]}
        # 5 Bundles × 1 Erbse + 1 Einzel-Erbse = 6
        assert komponenten["Erbse"]["total_quantity"] == 6
        assert komponenten["Sonnenblume"]["total_quantity"] == 5


class TestZusatzaufgaben:
    """(12) Kistenspülen, Hanfmatten auffüllen, Müllabholung — Aufgaben ohne
    Produktionsbezug ließen sich nirgends erfassen und keinem Tag zuordnen."""

    def test_aufgabe_erscheint_im_tagesplan(self, client):
        heute = date.today()
        r = client.post("/api/v1/staff-tasks", json={
            "titel": "Kisten spülen",
            "datum": heute.isoformat(),
            "employee_name": "Anna",
        })
        assert r.status_code == 201, r.text

        plan = client.get("/api/v1/production/day-plan",
                          params={"target_date": heute.isoformat()}).json()
        titel = [a["titel"] for a in plan["aufgaben"]]
        assert "Kisten spülen" in titel
        assert plan["aufgaben"][0]["employee_name"] == "Anna"
        assert plan["aufgaben"][0]["erledigt"] is False

    def test_woechentliche_serie_erzeugt_termine(self, client):
        """Müllabholplan: einmal anlegen, danach steht er jede Woche im Plan."""
        start = date.today()
        r = client.post("/api/v1/staff-tasks", json={
            "titel": "Müll rausstellen",
            "datum": start.isoformat(),
            "wiederholung": "WOECHENTLICH",
            "wiederholung_bis": (start + timedelta(days=21)).isoformat(),
        })
        assert r.status_code == 201, r.text
        created = r.json()
        assert len(created) == 4, "Start + 3 Wiederholungen"
        assert {t["datum"] for t in created} == {
            (start + timedelta(days=7 * i)).isoformat() for i in range(4)
        }
        assert len({t["serie_id"] for t in created}) == 1

        plan = client.get("/api/v1/production/day-plan",
                          params={"target_date": (start + timedelta(days=14)).isoformat()}).json()
        assert [a["titel"] for a in plan["aufgaben"]] == ["Müll rausstellen"]

    def test_erledigt_wird_mit_zeitstempel_gesetzt(self, client):
        heute = date.today()
        task = client.post("/api/v1/staff-tasks", json={
            "titel": "Hanfmatten auffüllen", "datum": heute.isoformat(),
        }).json()[0]

        r = client.patch(f"/api/v1/staff-tasks/{task['id']}", json={"erledigt": True})
        assert r.status_code == 200, r.text
        assert r.json()["erledigt"] is True
        assert r.json()["erledigt_am"] is not None

        r = client.patch(f"/api/v1/staff-tasks/{task['id']}", json={"erledigt": False})
        assert r.json()["erledigt_am"] is None

    def test_serie_ab_diesem_termin_loeschen(self, client):
        """Vergangene (erledigte) Termine bleiben stehen, künftige verschwinden."""
        start = date.today()
        created = client.post("/api/v1/staff-tasks", json={
            "titel": "Kisten falten",
            "datum": start.isoformat(),
            "wiederholung": "TAEGLICH",
            "wiederholung_bis": (start + timedelta(days=3)).isoformat(),
        }).json()
        dritter = created[2]

        r = client.delete(f"/api/v1/staff-tasks/{dritter['id']}", params={"serie": True})
        assert r.status_code == 204, r.text

        rest = client.get("/api/v1/staff-tasks", params={
            "von_datum": start.isoformat(),
            "bis_datum": (start + timedelta(days=3)).isoformat(),
        }).json()
        assert [t["datum"] for t in rest] == [
            start.isoformat(), (start + timedelta(days=1)).isoformat(),
        ]


class TestDienstplanDruck:
    """(11) Der Dienstplan ließ sich nicht als Aushang ausdrucken."""

    def test_pdf_enthaelt_schichten_und_aufgaben(self, client):
        montag = date.today() - timedelta(days=date.today().weekday())
        client.post("/api/v1/staff-shifts", json={
            "employee_name": "Gernot", "datum": montag.isoformat(),
            "start_time": "06:00", "end_time": "14:00", "aufgabe": "Ernte",
        })
        client.post("/api/v1/staff-tasks", json={
            "titel": "Kisten spuelen", "datum": montag.isoformat(),
        })

        r = client.get("/api/v1/staff-shifts/print", params={
            "von_datum": montag.isoformat(),
            "bis_datum": (montag + timedelta(days=6)).isoformat(),
        })
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:4] == b"%PDF"

        text = pdf_text(r.content)
        assert "Gernot" in text
        assert "06:00" in text
        assert "Kisten spuelen" in text
