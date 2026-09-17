"""Gernot-Feedback vom 17.09.2026 — Bestellerfassung.

(1) Hinterlegte Sonderpreise wurden in der Bestellung nicht angezeigt und
    nicht übernommen (AB-20260917-0001, Kunde Ferdinand Bierbichler).
"""
from decimal import Decimal

import pytest


def _kunde(client, name="Ferdinand Bierbichler GmbH & Co. KG"):
    # Pflichtfeld heißt "typ" (CustomerType: GASTRO | HANDEL | GEWERBE | PRIVAT).
    # Ein Feld "kundengruppe" gibt es nicht — der Endpunkt antwortet dann mit 422.
    r = client.post("/api/v1/sales/customers", json={
        "name": name, "typ": "GASTRO",
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _produkt(client, name, sku, preis, **extra):
    from app.models.unit import UnitOfMeasure, UnitCategory
    from tests.conftest import TestingSessionLocal

    with TestingSessionLocal() as db:
        unit = db.query(UnitOfMeasure).filter_by(code="STK").first()
        if unit is None:
            unit = UnitOfMeasure(code="STK", name="Stück", category=UnitCategory.COUNT)
            db.add(unit)
            db.commit()
        unit_id = str(unit.id)

    r = client.post("/api/v1/products", json={
        "name": name, "sku": sku, "base_price": str(preis),
        "category": "MICROGREEN", "base_unit_id": unit_id, **extra,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _sonderpreis(client, kunde, produkt, preis):
    r = client.post(f"/api/v1/sales/customers/{kunde['id']}/prices", json={
        "product_id": produkt["id"], "unit_price": str(preis),
        "valid_from": "2026-09-03",
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


class TestSonderpreisInBestellung:
    """Punkt 1: Sonderpreis schlägt Listenpreis und Varianten-Override."""

    def test_sonderpreis_schlaegt_basispreis(self, client):
        kunde = _kunde(client)
        produkt = _produkt(client, "BIO Gourmetmix (VPE 6)", "MG-11002", Decimal("12.99"))
        _sonderpreis(client, kunde, produkt, Decimal("12.49"))

        r = client.post("/api/v1/sales/orders", json={
            "customer_id": kunde["id"],
            "requested_delivery_date": "2026-09-18",
            "lines": [{
                "product_id": produkt["id"], "quantity": 2,
                "unit": "STK", "unit_price": 0, "product_name": produkt["name"],
            }],
        })
        assert r.status_code == 201, r.text
        assert Decimal(str(r.json()["lines"][0]["unit_price"])) == Decimal("12.49")

    def test_sonderpreis_schlaegt_varianten_override(self, client):
        """Regression: der Varianten-Zweig hat den Sonderpreis überschrieben."""
        kunde = _kunde(client)
        produkt = _produkt(client, "BIO Kiste | Erbse", "MG-12005", Decimal("12.49"))
        _sonderpreis(client, kunde, produkt, Decimal("11.99"))

        rv = client.post(f"/api/v1/products/{produkt['id']}/variants", json={
            "name_suffix": "VPE 6", "price_override": "12.49",
            "packaging_unit_id": produkt["base_unit_id"],
        })
        assert rv.status_code in (200, 201), rv.text
        variante = rv.json()

        r = client.post("/api/v1/sales/orders", json={
            "customer_id": kunde["id"],
            "requested_delivery_date": "2026-09-18",
            "lines": [{
                "product_id": produkt["id"],
                "product_variant_id": variante["id"],
                "quantity": 2, "unit": "STK", "unit_price": 0,
                "product_name": produkt["name"],
            }],
        })
        assert r.status_code == 201, r.text
        assert Decimal(str(r.json()["lines"][0]["unit_price"])) == Decimal("11.99")

    def test_expliziter_preis_bleibt_unangetastet(self, client):
        """Ein bewusst gesetzter Preis darf nicht wegoptimiert werden."""
        kunde = _kunde(client)
        produkt = _produkt(client, "BIO Genussmix (VPE 6)", "MG-11001", Decimal("11.99"))
        _sonderpreis(client, kunde, produkt, Decimal("11.99"))

        r = client.post("/api/v1/sales/orders", json={
            "customer_id": kunde["id"],
            "requested_delivery_date": "2026-09-18",
            "lines": [{
                "product_id": produkt["id"], "quantity": 1,
                "unit": "STK", "unit_price": "9.50", "product_name": produkt["name"],
            }],
        })
        assert r.status_code == 201, r.text
        assert Decimal(str(r.json()["lines"][0]["unit_price"])) == Decimal("9.50")

    def test_mitgesendeter_preis_ueberlebt_die_variante(self, client):
        """DER Test, der zählt.

        Nach Task 2 schickt das Frontend immer einen konkreten Preis — nämlich
        den bereits aufgelösten Sonderpreis. Der Varianten-Zweig darf ihn dann
        NICHT mehr überschreiben. Ohne diesen Test bleiben die drei Tests
        darüber grün, während Gernots Bug in der echten Oberfläche weiterlebt,
        weil dort nie ein Preis von 0 ankommt.
        """
        kunde = _kunde(client)
        produkt = _produkt(client, "BIO Kiste | Erbse", "MG-12005", Decimal("12.49"))
        _sonderpreis(client, kunde, produkt, Decimal("11.99"))

        rv = client.post(f"/api/v1/products/{produkt['id']}/variants", json={
            "name_suffix": "VPE 6", "price_override": "12.49",
            "packaging_unit_id": produkt["base_unit_id"],
        })
        assert rv.status_code in (200, 201), rv.text

        r = client.post("/api/v1/sales/orders", json={
            "customer_id": kunde["id"],
            "requested_delivery_date": "2026-09-18",
            "lines": [{
                "product_id": produkt["id"],
                "product_variant_id": rv.json()["id"],
                "quantity": 2, "unit": "STK",
                "unit_price": "11.99",          # <- so verhält sich das neue Frontend
                "product_name": produkt["name"],
            }],
        })
        assert r.status_code == 201, r.text
        assert Decimal(str(r.json()["lines"][0]["unit_price"])) == Decimal("11.99")
