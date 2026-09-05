"""Gernots letzte zwei Punkte: Pfand-Kategorie und Einmalrabatt.

Pfand: Pfandkisten sollen als Produkt mit eigener Kategorie anlegbar sein
(regulärer Steuersatz 19 %) und auf der Rechnung ausgewiesen werden.

Einmalrabatt: ein Rabatt auf genau dieser Rechnung — ohne den Kunden-
Stammrabatt anzufassen. Die Falle: der PATCH setzte den Prozentsatz,
rechnete die Summen aber nicht neu.
"""
from datetime import date
from decimal import Decimal

import pytest


@pytest.fixture(autouse=True)
def stueck_einheit(db):
    """Produktanlage verlangt eine Basiseinheit — die Test-DB startet leer."""
    from app.models.unit import UnitOfMeasure, UnitCategory
    db.add(UnitOfMeasure(name="Gramm", code="G", symbol="g",
                         category=UnitCategory.WEIGHT, conversion_factor=1,
                         is_base_unit=True, is_active=True))
    db.commit()


class TestPfandKategorie:
    def test_pfand_produkt_bekommt_19_prozent_und_pfandkennzeichen(self, client):
        r = client.post("/api/v1/products", json={
            "sku": "PFAND-K12", "name": "Pfandkiste 12er",
            "category": "PFAND", "base_price": 4.50, "deposit_value": 4.50,
        })
        assert r.status_code == 201, r.text
        p = r.json()
        assert p["category"] == "PFAND"
        # Pfand ist kein Lebensmittelumsatz: 19 % und als Pfand gekennzeichnet
        assert p["tax_rate"] == "STANDARD"
        assert p["is_deposit"] is True

    def test_explizite_werte_werden_nicht_ueberschrieben(self, client):
        r = client.post("/api/v1/products", json={
            "sku": "PFAND-X", "name": "Sonderpfand",
            "category": "PFAND", "base_price": 2.00,
            "tax_rate": "REDUZIERT", "is_deposit": False,
        })
        assert r.status_code == 201, r.text
        assert r.json()["tax_rate"] == "REDUZIERT"
        assert r.json()["is_deposit"] is False

    def test_pfand_auf_der_rechnung_ausgewiesen(self, client, sample_customer):
        pfand = client.post("/api/v1/products", json={
            "sku": "PFAND-K6", "name": "Pfandkiste 6er",
            "category": "PFAND", "base_price": 3.00, "deposit_value": 3.00,
        }).json()

        rechnung = client.post("/api/v1/invoices", json={
            "customer_id": sample_customer["id"],
            "invoice_date": date.today().isoformat(),
        }).json()
        client.post(f"/api/v1/invoices/{rechnung['id']}/lines", json={
            "description": "Erbsen-Schale", "quantity": 10, "unit": "STK",
            "unit_price": 2.50, "tax_rate": "REDUZIERT",
        })
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/lines", json={
            "description": "Pfandkiste 6er", "quantity": 2, "unit": "STK",
            "unit_price": 3.00, "tax_rate": "STANDARD",
            "product_id": pfand["id"],
        })
        assert r.status_code == 201, r.text

        detail = client.get(f"/api/v1/invoices/{rechnung['id']}").json()
        # 2 × 3,00 € netto = 7,14 € brutto — der Pfandausweis auf der
        # Rechnung ist ein Bruttobetrag (Bestandsverhalten, siehe test_deposit)
        assert Decimal(str(detail["total_deposit"])) == Decimal("7.14")
        pfandzeile = next(l for l in detail["lines"] if l.get("product_id") == pfand["id"])
        assert pfandzeile["tax_rate"] == "STANDARD"

    def test_pfand_kategorie_im_produktfilter(self, client):
        client.post("/api/v1/products", json={
            "sku": "PFAND-F", "name": "Filterpfand",
            "category": "PFAND", "base_price": 1.00,
        })
        r = client.get("/api/v1/products", params={"category": "PFAND"})
        assert r.status_code == 200, r.text
        artikel = r.json()
        artikel = artikel["items"] if isinstance(artikel, dict) else artikel
        assert any(a["sku"] == "PFAND-F" for a in artikel)


class TestEinmalrabatt:
    @pytest.fixture
    def entwurf(self, client, sample_customer):
        rechnung = client.post("/api/v1/invoices", json={
            "customer_id": sample_customer["id"],
            "invoice_date": date.today().isoformat(),
        }).json()
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/lines", json={
            "description": "Erbsen-Schale", "quantity": 10, "unit": "STK",
            "unit_price": 10.00, "tax_rate": "REDUZIERT",
        })
        assert r.status_code == 201, r.text
        return rechnung

    def test_rabatt_rechnet_die_summen_neu(self, client, entwurf):
        """Die eigentliche Lücke: der PATCH setzte den Prozentsatz, die
        Summen blieben aber auf dem alten Stand."""
        r = client.patch(f"/api/v1/invoices/{entwurf['id']}",
                         json={"discount_percent": 10})
        assert r.status_code == 200, r.text

        detail = client.get(f"/api/v1/invoices/{entwurf['id']}").json()
        # 100 € − 10 % = 90 € netto, + 7 % USt = 96,30 €
        assert Decimal(str(detail["discount_amount"])) == Decimal("10.00")
        assert Decimal(str(detail["subtotal"])) == Decimal("90.00")
        assert Decimal(str(detail["total"])) == Decimal("96.30")

    def test_rabatt_wieder_entfernen(self, client, entwurf):
        client.patch(f"/api/v1/invoices/{entwurf['id']}", json={"discount_percent": 10})
        client.patch(f"/api/v1/invoices/{entwurf['id']}", json={"discount_percent": 0})

        detail = client.get(f"/api/v1/invoices/{entwurf['id']}").json()
        assert Decimal(str(detail["subtotal"])) == Decimal("100.00")
        assert Decimal(str(detail["total"])) == Decimal("107.00")

    def test_rabatt_nur_auf_entwuerfe(self, client, entwurf):
        client.post(f"/api/v1/invoices/{entwurf['id']}/finalize")
        r = client.patch(f"/api/v1/invoices/{entwurf['id']}",
                         json={"discount_percent": 50})
        assert r.status_code == 400, r.text
