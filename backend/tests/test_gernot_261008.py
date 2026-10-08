"""Gernot-Feedback vom 07./08.10.2026 — Paket 1 (Steuer und Rechnung).

Gemeinsame Testdatei der Abschnitte S1–S6. Helfer und Klassen tragen ein
Abschnitts-Präfix (_s1_/TestS1, _s2_/TestS2, _s3_/TestS3, _datev_/TestDatev,
_s5_/TestS5, _s6_/TestS6): ein gleichnamiger Helfer würde still ersetzt.
"""
import csv
import io
import re
import uuid
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import TestingSessionLocal
from tests.test_documents_preise import _pdf_text


# ============================================================
# S1 — Steuersatz kommt aus dem Produkt (A3)
#
# Pfandkisten liefen mit 7 % statt 19 %: das Bestellformular schickte fest
# REDUZIERT, das Schema setzte REDUZIERT als Default, die Rechnung aus der
# Bestellung übernahm den Satz der Bestellposition.
# ============================================================

_S1_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _s1_einheit():
    """Basiseinheit 'G' — Produktanlage und Produktimport verlangen sie."""
    from app.models.unit import UnitOfMeasure, UnitCategory
    with TestingSessionLocal() as db:
        unit = db.query(UnitOfMeasure).filter_by(code="G").first()
        if unit is None:
            unit = UnitOfMeasure(code="G", name="Gramm", symbol="g",
                                 category=UnitCategory.WEIGHT, is_base_unit=True)
            db.add(unit)
            db.commit()
        return str(unit.id)


def _s1_produkt(client, sku, name, preis, **extra):
    r = client.post("/api/v1/products", json={
        "sku": sku, "name": name, "base_price": str(preis),
        "category": "MICROGREEN", "base_unit_id": _s1_einheit(), **extra,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _s1_pfandkiste(client, sku="PFAND-IFCO", **extra):
    """Pfandkiste wie in Gernots Stamm: Kategorie PFAND → 19 % + Pfandkennzeichen."""
    return _s1_produkt(client, sku, "IFCO-Kiste", "3.00",
                       category="PFAND", deposit_value="3.00", **extra)


def _s1_variante(client, produkt):
    r = client.post(f"/api/v1/products/{produkt['id']}/variants", json={
        "name_suffix": "6er Stapel", "packaging_unit_id": produkt["base_unit_id"],
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _s1_kunde(client, name="Ökoring Test", **extra):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "HANDEL", **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _s1_zeile(produkt=None, menge=2, preis="3.00", **extra):
    zeile = {
        "product_name": produkt["name"] if produkt else "Kresse (Freitext)",
        "quantity": menge, "unit": "STK", "unit_price": preis,
    }
    if produkt:
        zeile["product_id"] = produkt["id"]
    zeile.update(extra)
    return zeile


def _s1_bestellung(client, kunde, zeilen, liefertag="2026-10-09"):
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"], "requested_delivery_date": liefertag, "lines": zeilen,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _s1_altstand(order_id):
    """Stellt den Stand vor dem Fix her: jede Produktposition auf 7 %, Beträge
    und Summen passend dazu — so sehen Gernots offene Bestellungen aus."""
    from app.api.v1.sales import _calculate_line_amounts, _calculate_order_totals
    from app.models.enums import TaxRate
    from app.models.order import Order
    with TestingSessionLocal() as db:
        order = db.get(Order, uuid.UUID(order_id))
        for line in order.lines:
            if line.product_id or line.product_variant_id:
                line.tax_rate = TaxRate.REDUZIERT
                _calculate_line_amounts(line)
        _calculate_order_totals(order)
        db.commit()


def _s1_altbestellung(client, kunde, pfand, liefertag="2026-10-09"):
    """Offene Bestellung wie vor dem Fix: Kresse 7 %, Pfandkiste fälschlich 7 %."""
    order = _s1_bestellung(client, kunde, [
        _s1_zeile(None, menge=10, preis="2.50", tax_rate="REDUZIERT"),
        _s1_zeile(pfand, menge=2, preis="3.00"),
    ], liefertag=liefertag)
    _s1_altstand(order["id"])
    return client.get(f"/api/v1/sales/orders/{order['id']}").json()


def _s1_pfandzeile(client, order_id):
    order = client.get(f"/api/v1/sales/orders/{order_id}").json()
    return next(z for z in order["lines"] if z["product_id"])


def _s1_rechnung_aus(client, order):
    r = client.post(f"/api/v1/invoices/from-order/{order['id']}")
    assert r.status_code in (200, 201), r.text
    return r.json()


def _s1_rechnungszeilen(invoice_id):
    """Rechnungszeilen direkt aus der DB — is_deposit steht nicht in der API-Antwort."""
    from app.models.invoice import InvoiceLine
    with TestingSessionLocal() as db:
        return [{
            "product_id": l.product_id,
            "tax_rate": l.tax_rate.value,
            "is_deposit": l.is_deposit,
            "discount_percent": Decimal(str(l.discount_percent)),
        } for l in db.query(InvoiceLine)
            .filter_by(invoice_id=uuid.UUID(invoice_id))
            .order_by(InvoiceLine.position)]


def _s1_produktimport(client, *zeilen):
    """Produktimport mit der Kopfzeile des echten Templates; je Zeile nur die
    angegebenen Spalten befüllt, alle anderen Zellen leer."""
    from openpyxl import Workbook, load_workbook
    tpl = client.get("/api/v1/imports/template/products").content
    header = [c.value for c in load_workbook(io.BytesIO(tpl))["Daten"][1]]
    spalten = [str(h).rstrip(" *") for h in header]
    wb = Workbook()
    ws = wb.active
    ws.title = "Daten"
    ws.append(header)
    for werte in zeilen:
        zeile = [""] * len(header)
        for spalte, wert in werte.items():
            zeile[spalten.index(spalte)] = wert
        ws.append(zeile)
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post("/api/v1/imports/products",
                    files={"file": ("products.xlsx", buf.getvalue(), _S1_XLSX)})
    assert r.status_code == 200, r.text
    return r.json()


def _s1_produkt_orm(db, sku, name, satz):
    """Produkt direkt über das ORM — für Service-Tests mit der db-Fixture ohne Client."""
    from app.models.product import Product, ProductCategory
    from app.models.unit import UnitOfMeasure, UnitCategory
    unit = db.query(UnitOfMeasure).filter_by(code="STK").first()
    if unit is None:
        unit = UnitOfMeasure(code="STK", name="Stück", category=UnitCategory.COUNT)
        db.add(unit)
        db.flush()
    produkt = Product(sku=sku, name=name, category=ProductCategory.MICROGREEN,
                      base_unit_id=unit.id, tax_rate=satz)
    db.add(produkt)
    db.commit()
    return produkt


class TestS1SteuersatzInDerBestellung:
    """Task 1: Bestellpositionen mit Produkt tragen den Produktsatz."""

    def test_pfandkiste_bekommt_19_prozent_obwohl_das_formular_7_schickt(self, client):
        pfand = _s1_pfandkiste(client)
        order = _s1_bestellung(client, _s1_kunde(client), [
            _s1_zeile(pfand, menge=2, preis="3.00", tax_rate="REDUZIERT"),
        ])
        zeile = order["lines"][0]
        assert zeile["tax_rate"] == "STANDARD"
        # 2 × 3,00 € = 6,00 € netto, 19 % = 1,14 €
        assert Decimal(str(zeile["line_vat"])) == Decimal("1.14")
        assert Decimal(str(order["total_gross"])) == Decimal("7.14")

    def test_ohne_satz_gilt_der_produktsatz(self, client):
        pfand = _s1_pfandkiste(client)
        order = _s1_bestellung(client, _s1_kunde(client), [_s1_zeile(pfand)])
        assert order["lines"][0]["tax_rate"] == "STANDARD"

    def test_bewusst_auf_7_prozent_gesetztes_pfand_bleibt_bei_7(self, client):
        """Der Fix übernimmt den Produktsatz — er erzwingt nicht 19 % für Pfand."""
        pfand = _s1_pfandkiste(client, sku="PFAND-7", tax_rate="REDUZIERT")
        order = _s1_bestellung(client, _s1_kunde(client), [_s1_zeile(pfand, tax_rate="STANDARD")])
        assert order["lines"][0]["tax_rate"] == "REDUZIERT"

    def test_freitext_behaelt_den_satz_vom_client(self, client):
        order = _s1_bestellung(client, _s1_kunde(client), [
            _s1_zeile(None, tax_rate="STANDARD"),
            {"product_name": "Freitext ohne Satz", "quantity": 1, "unit": "STK", "unit_price": "2.00"},
        ])
        assert sorted(z["tax_rate"] for z in order["lines"]) == ["REDUZIERT", "STANDARD"]

    def test_position_nur_mit_variante_nimmt_den_satz_des_elternprodukts(self, client):
        pfand = _s1_pfandkiste(client)
        variante = _s1_variante(client, pfand)
        order = _s1_bestellung(client, _s1_kunde(client), [{
            "product_variant_id": variante["id"], "product_name": "IFCO-Kiste",
            "quantity": 1, "unit": "STK", "unit_price": "18.00", "tax_rate": "REDUZIERT",
        }])
        assert order["lines"][0]["tax_rate"] == "STANDARD"

    def test_nachgetragene_position_nimmt_den_produktsatz(self, client):
        """EditOrderModal schickt keinen Satz — bisher griff der Schema-Default 7 %."""
        pfand = _s1_pfandkiste(client)
        order = _s1_bestellung(client, _s1_kunde(client), [
            _s1_zeile(None, menge=10, preis="2.50", tax_rate="REDUZIERT"),
        ])
        r = client.post(f"/api/v1/sales/orders/{order['id']}/lines", json={
            "product_id": pfand["id"], "product_name": pfand["name"],
            "quantity": 2, "unit": "STK", "unit_price": "3.00",
        })
        assert r.status_code == 201, r.text
        assert r.json()["tax_rate"] == "STANDARD"
        detail = client.get(f"/api/v1/sales/orders/{order['id']}").json()
        # 25,00 € × 7 % = 1,75 € | 6,00 € × 19 % = 1,14 €
        assert Decimal(str(detail["total_vat"])) == Decimal("2.89")

    def test_nachgetragene_variantenposition_behaelt_die_variante(self, client):
        """add_order_line verwarf product_variant_id — die Rechnung fand dann
        kein Produkt hinter der Position und setzte kein Pfandkennzeichen."""
        pfand = _s1_pfandkiste(client)
        variante = _s1_variante(client, pfand)
        order = _s1_bestellung(client, _s1_kunde(client), [
            _s1_zeile(None, menge=10, preis="2.50", tax_rate="REDUZIERT"),
        ])
        r = client.post(f"/api/v1/sales/orders/{order['id']}/lines", json={
            "product_variant_id": variante["id"], "product_name": "IFCO-Kiste",
            "quantity": 1, "unit": "STK", "unit_price": "18.00",
        })
        assert r.status_code == 201, r.text
        assert r.json()["product_variant_id"] == variante["id"]

        detail = client.get(f"/api/v1/sales/orders/{order['id']}").json()
        zeile = next(z for z in detail["lines"] if z["product_variant_id"])
        assert zeile["product_variant_id"] == variante["id"]
        assert zeile["tax_rate"] == "STANDARD"

        # Unbekannte Variante: 404 wie in create_order, kein Fremdschlüsselfehler
        r = client.post(f"/api/v1/sales/orders/{order['id']}/lines", json={
            "product_variant_id": str(uuid.uuid4()), "product_name": "?",
            "quantity": 1, "unit": "STK", "unit_price": "1.00",
        })
        assert r.status_code == 404, r.text

    def test_patch_kann_den_produktsatz_nicht_ueberschreiben(self, client):
        pfand = _s1_pfandkiste(client)
        order = _s1_bestellung(client, _s1_kunde(client), [_s1_zeile(pfand)])
        zeile = order["lines"][0]
        r = client.patch(f"/api/v1/sales/orders/{order['id']}/lines/{zeile['id']}",
                         json={"tax_rate": "REDUZIERT"})
        assert r.status_code == 200, r.text
        assert r.json()["tax_rate"] == "STANDARD"

    def test_patch_zieht_den_alten_satz_nach_und_protokolliert_ihn(self, client):
        """Bestätigte Bestellung mit Altposition (7 %): die nächste Änderung
        bringt den Produktsatz und steht mit altem und neuem Satz im Audit-Log."""
        pfand = _s1_pfandkiste(client)
        order = _s1_bestellung(client, _s1_kunde(client), [_s1_zeile(pfand)])
        zeile = order["lines"][0]
        _s1_altstand(order["id"])
        r = client.post(f"/api/v1/sales/orders/{order['id']}/confirm")
        assert r.status_code == 200, r.text

        r = client.patch(f"/api/v1/sales/orders/{order['id']}/lines/{zeile['id']}",
                         json={"quantity": 3})
        assert r.status_code == 200, r.text
        assert r.json()["tax_rate"] == "STANDARD"

        log = client.get(f"/api/v1/sales/orders/{order['id']}/audit-log").json()
        eintrag = next(e for e in log if e["action"] == "UPDATE_LINE")
        assert eintrag["old_values"]["tax_rate"] == "REDUZIERT"
        assert eintrag["new_values"]["tax_rate"] == "STANDARD"

    def test_kreditlimit_rechnet_pfand_mit_19_prozent(self, client):
        """100 € Pfand netto: mit 7 % 107 € (unter dem Limit von 110 €), richtig 119 €."""
        pfand = _s1_pfandkiste(client)
        kunde = _s1_kunde(client, credit_limit="110.00")
        r = client.post("/api/v1/sales/orders", json={
            "customer_id": kunde["id"], "requested_delivery_date": "2026-10-09",
            "lines": [_s1_zeile(pfand, menge=1, preis="100.00", tax_rate="REDUZIERT")],
        })
        assert r.status_code == 400, r.text
        assert "Kreditlimit" in r.json()["detail"]


class TestS1RechnungAusBestellung:
    """Task 2: Rechnung aus der Bestellung — Satz, Rabatt, Leistungsdatum."""

    def test_altposition_mit_7_prozent_wird_mit_dem_produktsatz_fakturiert(self, client):
        """Der Weg von RE-00002/3/4: Bestellposition 7 %, Produkt 19 %."""
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)

        rechnung = _s1_rechnung_aus(client, order)

        zeilen = _s1_rechnungszeilen(rechnung["id"])
        pfandzeile = next(z for z in zeilen if z["product_id"] is not None)
        assert pfandzeile["tax_rate"] == "STANDARD"
        assert pfandzeile["is_deposit"] is True
        assert next(z for z in zeilen if z["product_id"] is None)["tax_rate"] == "REDUZIERT"
        # 25,00 € × 7 % = 1,75 € | 6,00 € × 19 % = 1,14 €
        assert Decimal(str(rechnung["tax_amount"])) == Decimal("2.89")

    def test_variantenposition_traegt_satz_und_pfandkennzeichen(self, client):
        pfand = _s1_pfandkiste(client)
        variante = _s1_variante(client, pfand)
        order = _s1_bestellung(client, _s1_kunde(client), [{
            "product_variant_id": variante["id"], "product_name": "IFCO-Kiste",
            "quantity": 1, "unit": "STK", "unit_price": "18.00",
        }])
        _s1_altstand(order["id"])

        zeile = _s1_rechnungszeilen(_s1_rechnung_aus(client, order)["id"])[0]

        assert zeile["tax_rate"] == "STANDARD"
        assert zeile["is_deposit"] is True
        assert zeile["product_id"] == uuid.UUID(pfand["id"])

    def test_positionsrabatt_wird_uebernommen(self, client):
        order = _s1_bestellung(client, _s1_kunde(client), [
            _s1_zeile(None, menge=10, preis="10.00", tax_rate="REDUZIERT", discount_percent="10"),
        ])
        assert Decimal(str(order["total_net"])) == Decimal("90.00")

        rechnung = _s1_rechnung_aus(client, order)

        assert _s1_rechnungszeilen(rechnung["id"])[0]["discount_percent"] == Decimal("10")
        assert Decimal(str(rechnung["subtotal"])) == Decimal("90.00")

    def test_leistungsdatum_ist_das_tatsaechliche_lieferdatum(self, client):
        from app.models.order import Order
        order = _s1_bestellung(client, _s1_kunde(client), [_s1_zeile(None, tax_rate="REDUZIERT")],
                               liefertag="2026-10-07")
        with TestingSessionLocal() as db:
            db.get(Order, uuid.UUID(order["id"])).actual_delivery_date = date(2026, 10, 8)
            db.commit()

        assert _s1_rechnung_aus(client, order)["delivery_date"] == "2026-10-08"

    def test_ohne_lieferung_bleibt_das_wunschlieferdatum(self, client):
        order = _s1_bestellung(client, _s1_kunde(client), [_s1_zeile(None, tax_rate="REDUZIERT")],
                               liefertag="2026-10-07")
        assert _s1_rechnung_aus(client, order)["delivery_date"] == "2026-10-07"

    def test_storno_bucht_mit_dem_satz_der_originalzeile_gegen(self, client):
        """Absicherung: der Produktsatz wird NICHT in add_line erzwungen. Der
        Storno einer alten 7-%-Pfandrechnung muss mit 7 % gegenbuchen, sonst
        ergibt er nicht null."""
        pfand = _s1_pfandkiste(client)
        kunde = _s1_kunde(client)
        rechnung = client.post("/api/v1/invoices", json={
            "customer_id": kunde["id"], "invoice_date": "2026-10-08",
        }).json()
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/lines", json={
            "description": "IFCO-Kiste", "quantity": 2, "unit": "STK", "unit_price": "3.00",
            "tax_rate": "REDUZIERT", "product_id": pfand["id"],
        })
        assert r.status_code == 201, r.text
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/finalize")
        assert r.status_code == 200, r.text

        storno = client.post(f"/api/v1/invoices/{rechnung['id']}/cancel",
                             json={"reason": "Steuersatz falsch"})
        assert storno.status_code == 200, storno.text

        gutschrift = storno.json()["credit_note"]
        assert [z["tax_rate"] for z in _s1_rechnungszeilen(gutschrift["id"])] == ["REDUZIERT"]
