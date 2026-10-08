"""Regressionstests für die Abnahme-Befunde aus Paket 1."""

from decimal import Decimal

from app.models.unit import UnitCategory, UnitOfMeasure
from tests.conftest import TestingSessionLocal


def test_product_group_patch_updates_name(client):
    created = client.post(
        "/api/v1/product-groups",
        json={"code": "ABN-GRP", "name": "Alte Gruppe"},
    )
    assert created.status_code == 201, created.text

    response = client.patch(
        f"/api/v1/product-groups/{created.json()['id']}",
        json={"name": "Neue Gruppe"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Neue Gruppe"


def test_grow_plan_patch_updates_name(client):
    created = client.post(
        "/api/v1/grow-plans",
        json={
            "code": "ABN-GP",
            "name": "Alter Plan",
            "germination_days": 2,
            "growth_days": 8,
            "harvest_window_start_days": 9,
            "harvest_window_optimal_days": 11,
            "harvest_window_end_days": 14,
            "expected_yield_grams_per_tray": 350,
            "seed_density_grams_per_tray": 25,
        },
    )
    assert created.status_code == 201, created.text

    response = client.patch(
        f"/api/v1/grow-plans/{created.json()['id']}",
        json={"name": "Neuer Plan"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Neuer Plan"


def test_price_list_patch_updates_name(client):
    created = client.post(
        "/api/v1/price-lists",
        json={"code": "ABN-PL", "name": "Alte Preisliste"},
    )
    assert created.status_code == 201, created.text

    response = client.patch(
        f"/api/v1/price-lists/{created.json()['id']}",
        json={"name": "Neue Preisliste"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Neue Preisliste"


def test_price_list_item_patch_updates_price(client):
    with TestingSessionLocal() as db:
        unit = UnitOfMeasure(
            code="G",
            name="Gramm",
            category=UnitCategory.WEIGHT,
            is_base_unit=True,
        )
        db.add(unit)
        db.commit()
        db.refresh(unit)
        unit_id = str(unit.id)

    product = client.post(
        "/api/v1/products",
        json={
            "sku": "ABN-PROD",
            "name": "Abnahmeprodukt",
            "category": "PACKAGING",
            "base_unit_id": unit_id,
        },
    )
    assert product.status_code == 201, product.text

    price_list = client.post(
        "/api/v1/price-lists",
        json={"code": "ABN-PLI", "name": "Preisliste Position"},
    )
    assert price_list.status_code == 201, price_list.text
    price_list_id = price_list.json()["id"]

    created = client.post(
        f"/api/v1/price-lists/{price_list_id}/items",
        json={
            "price_list_id": price_list_id,
            "product_id": product.json()["id"],
            "price": "2.50",
        },
    )
    assert created.status_code == 201, created.text

    response = client.patch(
        f"/api/v1/price-lists/{price_list_id}/items/{created.json()['id']}",
        json={"price": "3.25"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["price"] == "3.25"


def test_record_payment_uses_invoice_id_from_path(client, sample_customer):
    created = client.post(
        "/api/v1/invoices",
        json={
            "customer_id": sample_customer["id"],
            "invoice_date": "2026-10-08",
        },
    )
    assert created.status_code == 201, created.text
    invoice_id = created.json()["id"]

    line = client.post(
        f"/api/v1/invoices/{invoice_id}/lines",
        json={
            "description": "Abnahmeartikel",
            "quantity": 1,
            "unit": "STK",
            "unit_price": "10.00",
            "tax_rate": "REDUZIERT",
        },
    )
    assert line.status_code == 201, line.text

    finalized = client.post(f"/api/v1/invoices/{invoice_id}/finalize")
    assert finalized.status_code == 200, finalized.text

    response = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={
            "amount": 5.0,
            "payment_date": "2026-10-08",
            "payment_method": "UEBERWEISUNG",
        },
    )

    assert response.status_code == 201, response.text
    invoice = client.get(f"/api/v1/invoices/{invoice_id}")
    assert invoice.status_code == 200, invoice.text
    assert Decimal(invoice.json()["paid_amount"]) == Decimal("5.00")
