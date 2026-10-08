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


class TestS1Sammelrechnung:
    """Task 3: Sammelrechnung übergibt Produkt, Produktsatz und Rabatt."""

    def _lauf(self, client, kunde, *zeilen):
        order = _s1_bestellung(client, kunde, list(zeilen), liefertag="2026-09-15")
        _s1_altstand(order["id"])
        note = client.post(f"/api/v1/sales/orders/{order['id']}/delivery-notes", json={})
        assert note.status_code == 201, note.text
        r = client.post("/api/v1/invoices/batch-run/commit", json={
            "period_from": "2026-09-01", "period_to": "2026-09-30",
            "customer_ids": [kunde["id"]],
        })
        assert r.status_code == 201, r.text
        return r.json()["rechnungen"][0]

    def test_pfandzeile_traegt_produkt_satz_und_kennzeichen(self, client):
        pfand = _s1_pfandkiste(client)
        rechnung = self._lauf(client, _s1_kunde(client), _s1_zeile(pfand, menge=4, preis="3.00"))

        zeile = _s1_rechnungszeilen(rechnung["id"])[0]
        assert zeile["product_id"] == uuid.UUID(pfand["id"])
        assert zeile["is_deposit"] is True
        assert zeile["tax_rate"] == "STANDARD"
        # 4 × 3,00 € netto + 19 % = 14,28 € Pfand brutto
        assert Decimal(str(rechnung["total_deposit"])) == Decimal("14.28")

    def test_positionsrabatt_bleibt_erhalten(self, client):
        rechnung = self._lauf(client, _s1_kunde(client), _s1_zeile(
            None, menge=10, preis="10.00", tax_rate="REDUZIERT", discount_percent="10"))
        assert Decimal(str(rechnung["subtotal"])) == Decimal("90.00")


class TestS1Produktstamm:
    """Task 4: PATCH und Import wenden dieselbe Pfandregel an wie das Anlegen."""

    def test_patch_auf_pfandkennzeichen_setzt_19_prozent(self, client):
        kiste = _s1_produkt(client, "KISTE-1", "Mehrwegkiste", "3.00", category="PACKAGING")
        assert kiste["tax_rate"] == "REDUZIERT"
        r = client.patch(f"/api/v1/products/{kiste['id']}", json={"is_deposit": True})
        assert r.status_code == 200, r.text
        assert r.json()["tax_rate"] == "STANDARD"

    def test_patch_auf_kategorie_pfand_setzt_kennzeichen_und_19_prozent(self, client):
        kiste = _s1_produkt(client, "KISTE-2", "Mehrwegkiste", "3.00", category="PACKAGING")
        r = client.patch(f"/api/v1/products/{kiste['id']}", json={"category": "PFAND"})
        assert r.status_code == 200, r.text
        assert r.json()["category"] == "PFAND"
        assert r.json()["is_deposit"] is True
        assert r.json()["tax_rate"] == "STANDARD"

    def test_ausdruecklicher_satz_im_patch_gewinnt(self, client):
        kiste = _s1_produkt(client, "KISTE-3", "Mehrwegkiste", "3.00", category="PACKAGING")
        r = client.patch(f"/api/v1/products/{kiste['id']}",
                         json={"is_deposit": True, "tax_rate": "REDUZIERT"})
        assert r.status_code == 200, r.text
        assert r.json()["tax_rate"] == "REDUZIERT"

    def test_patch_mit_leerer_kategorie_wird_abgewiesen(self, client):
        """products.category ist NOT NULL: ein ausdrückliches null ergibt 422,
        nicht einen Datenbankfehler (500) beim Commit."""
        kiste = _s1_produkt(client, "KISTE-4", "Mehrwegkiste", "3.00", category="PACKAGING")
        r = client.patch(f"/api/v1/products/{kiste['id']}", json={"category": None})
        assert r.status_code == 422, r.text
        assert client.get(f"/api/v1/products/{kiste['id']}").json()["category"] == "PACKAGING"

    def test_speichern_eines_7_prozent_pfands_kippt_den_satz_nicht(self, client):
        """Erneutes is_deposit=true ist kein Übergang — der bewusst gewählte Satz bleibt."""
        pfand = _s1_pfandkiste(client, sku="PFAND-7B", tax_rate="REDUZIERT")
        r = client.patch(f"/api/v1/products/{pfand['id']}",
                         json={"is_deposit": True, "name": "IFCO-Kiste 7 %"})
        assert r.status_code == 200, r.text
        assert r.json()["tax_rate"] == "REDUZIERT"

    def test_reimport_ohne_steuersatz_laesst_pfand_bei_19_prozent(self, client):
        pfand = _s1_pfandkiste(client, sku="PFAND-IMP1")
        assert pfand["tax_rate"] == "STANDARD"

        ergebnis = _s1_produktimport(client, {
            "sku": "PFAND-IMP1", "name": "IFCO-Kiste", "category": "PFAND", "base_price": "3.10",
        })

        assert ergebnis["updated"] == 1, ergebnis
        p = client.get(f"/api/v1/products/{pfand['id']}").json()
        assert p["tax_rate"] == "STANDARD"
        assert Decimal(str(p["base_price"])) == Decimal("3.10")

    def test_neuer_pfandartikel_ohne_steuersatz_bekommt_19_prozent(self, client):
        _s1_einheit()
        ergebnis = _s1_produktimport(client, {"sku": "PFAND-IMP2", "name": "IFCO-Kiste", "category": "PFAND"})
        assert ergebnis["created"] == 1, ergebnis
        p = next(p for p in client.get("/api/v1/products").json() if p["sku"] == "PFAND-IMP2")
        assert p["is_deposit"] is True
        assert p["tax_rate"] == "STANDARD"

    def test_zeile_ohne_kategorie_laesst_den_bestand_unveraendert(self, client):
        """Gegenprobe zur Lückenprüfung: category ist Pflichtspalte, eine Zeile
        ohne sie wird verworfen — der Pfandartikel bleibt PFAND."""
        pfand = _s1_pfandkiste(client, sku="PFAND-IMP3")
        ergebnis = _s1_produktimport(client, {"sku": "PFAND-IMP3", "name": "IFCO-Kiste"})
        assert ergebnis["updated"] == 0
        assert any("category" in f for f in ergebnis["errors"]), ergebnis
        p = client.get(f"/api/v1/products/{pfand['id']}").json()
        assert p["category"] == "PFAND"
        assert p["tax_rate"] == "STANDARD"


class TestS1Shopify:
    """Task 5: Shopify-Import nimmt den Produktsatz statt pauschal 19 %."""

    def _bestellung(self, *positionen):
        return {
            "id": 9001, "name": "#9001", "currency": "EUR",
            "customer": {"first_name": "Eva", "last_name": "Shop", "email": "eva@example.com"},
            "line_items": list(positionen),
        }

    def _saetze(self, db):
        from app.models.order import Order
        order = db.query(Order).filter_by(customer_reference="#9001").one()
        return [l.tax_rate.value for l in sorted(order.lines, key=lambda l: l.position)]

    def test_bekannter_artikel_nimmt_den_produktsatz(self, db):
        from app.models.enums import TaxRate
        from app.services.shopify_service import import_shopify_order
        _s1_produkt_orm(db, "MG-ERBSE", "Erbsenkresse", TaxRate.REDUZIERT)

        import_shopify_order(db, self._bestellung(
            {"title": "Erbsenkresse", "sku": "MG-ERBSE", "quantity": 2, "price": "4.00"}))

        assert self._saetze(db) == ["REDUZIERT"]

    def test_unbekannter_artikel_nimmt_den_satz_aus_shopify(self, db):
        from app.services.shopify_service import import_shopify_order
        import_shopify_order(db, self._bestellung(
            {"title": "Kresse lose", "sku": None, "quantity": 1, "price": "3.00",
             "tax_lines": [{"rate": 0.07, "price": "0.21", "title": "MwSt"}]},
            {"title": "Tasse", "sku": None, "quantity": 1, "price": "9.00"}))

        # ohne tax_lines wie bisher 19 %
        assert self._saetze(db) == ["REDUZIERT", "STANDARD"]


class TestS1Datenkorrektur:
    """Task 6: einmalige Korrektur offener Bestellpositionen."""

    def _lauf(self, **kw):
        from app.services.steuersatz_korrektur import korrigiere_offene_bestellpositionen
        with TestingSessionLocal() as db:
            ergebnis = korrigiere_offene_bestellpositionen(db, **kw)
            db.commit()
            return ergebnis

    def test_offene_bestellung_wird_auf_den_produktsatz_korrigiert(self, client):
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)
        # 31,00 € × 7 % = 2,17 € — der falsche Stand
        assert Decimal(str(order["total_vat"])) == Decimal("2.17")

        ergebnis = self._lauf()

        assert ergebnis["bestellungen"] == 1 and ergebnis["positionen"] == 1
        nachher = client.get(f"/api/v1/sales/orders/{order['id']}").json()
        assert {bool(z["product_id"]): z["tax_rate"] for z in nachher["lines"]} == {
            True: "STANDARD", False: "REDUZIERT",
        }
        pfandzeile = _s1_pfandzeile(client, order["id"])
        assert Decimal(str(pfandzeile["line_vat"])) == Decimal("1.14")
        assert Decimal(str(pfandzeile["line_gross"])) == Decimal("7.14")
        # 25,00 € × 7 % = 1,75 € | 6,00 € × 19 % = 1,14 €
        assert Decimal(str(nachher["total_vat"])) == Decimal("2.89")
        assert Decimal(str(nachher["total_gross"])) == Decimal("33.89")

    def test_korrektur_steht_im_audit_log(self, client):
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)

        self._lauf()

        log = client.get(f"/api/v1/sales/orders/{order['id']}/audit-log").json()
        eintrag = next(e for e in log if e["action"] == "STEUERSATZ_KORREKTUR")
        assert eintrag["old_values"]["positionen"][0]["tax_rate"] == "REDUZIERT"
        assert eintrag["new_values"]["positionen"][0]["tax_rate"] == "STANDARD"
        assert Decimal(eintrag["old_values"]["total_gross"]) == Decimal("33.17")
        assert Decimal(eintrag["new_values"]["total_gross"]) == Decimal("33.89")

    def test_zweiter_lauf_aendert_nichts(self, client):
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)
        self._lauf()

        zweiter = self._lauf()

        assert zweiter["bestellungen"] == 0
        log = client.get(f"/api/v1/sales/orders/{order['id']}/audit-log").json()
        assert sum(1 for e in log if e["action"] == "STEUERSATZ_KORREKTUR") == 1

    def test_bestellung_mit_rechnung_wird_nicht_angefasst(self, client):
        """Auch ein Rechnungsentwurf (RE-00003) sperrt: Rechnungen fasst die
        Korrektur nie an, und die Bestellung soll nicht von ihr abweichen."""
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)
        rechnung = _s1_rechnung_aus(client, order)
        rechnungszeilen = _s1_rechnungszeilen(rechnung["id"])

        ergebnis = self._lauf()

        assert ergebnis["bestellungen"] == 0
        assert ergebnis["uebersprungen_mit_rechnung"] == [order["order_number"]]
        assert _s1_pfandzeile(client, order["id"])["tax_rate"] == "REDUZIERT"
        assert _s1_rechnungszeilen(rechnung["id"]) == rechnungszeilen

    def test_bestellung_in_sammelrechnung_wird_nicht_angefasst(self, client):
        pfand = _s1_pfandkiste(client)
        kunde = _s1_kunde(client)
        order = _s1_altbestellung(client, kunde, pfand, liefertag="2026-09-15")
        assert client.post(f"/api/v1/sales/orders/{order['id']}/delivery-notes", json={}).status_code == 201
        r = client.post("/api/v1/invoices/batch-run/commit", json={
            "period_from": "2026-09-01", "period_to": "2026-09-30", "customer_ids": [kunde["id"]],
        })
        assert r.status_code == 201, r.text

        ergebnis = self._lauf()

        assert ergebnis["bestellungen"] == 0
        assert _s1_pfandzeile(client, order["id"])["tax_rate"] == "REDUZIERT"

    def test_stornierte_bestellung_bleibt(self, client):
        from app.models.enums import OrderStatus
        from app.models.order import Order
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)
        with TestingSessionLocal() as db:
            db.get(Order, uuid.UUID(order["id"])).status = OrderStatus.STORNIERT
            db.commit()

        assert self._lauf()["bestellungen"] == 0
        assert _s1_pfandzeile(client, order["id"])["tax_rate"] == "REDUZIERT"

    def test_nach_storno_der_rechnung_gezielt_korrigierbar(self, client):
        """Für die Neuausstellung von RE-00002/4: erst stornieren, dann die
        Bestellung gezielt korrigieren, dann neu fakturieren."""
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)
        rechnung = _s1_rechnung_aus(client, order)
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/cancel", json={"reason": "Steuersatz Pfand"})
        assert r.status_code == 200, r.text

        ergebnis = self._lauf(nur_bestellungen=[uuid.UUID(order["id"])])

        assert ergebnis["bestellungen"] == 1
        assert ergebnis["geaendert"] == [order["order_number"]]
        # Die Stornorechnung sperrt nicht: beide Listen leer, wie das Runbook es verlangt
        assert ergebnis["uebersprungen_mit_rechnung"] == []
        assert ergebnis["uebersprungen_status"] == []
        assert _s1_pfandzeile(client, order["id"])["tax_rate"] == "STANDARD"

    def test_gezielter_aufruf_meldet_nicht_offene_und_unbekannte_bestellungen(self, client):
        """nur_bestellungen filtert nach Status — eine fakturierte Bestellung
        oder eine unbekannte ID darf nicht still durchrutschen. Sonst hielte
        das Runbook ein leeres Ergebnis für Erfolg."""
        from app.models.enums import OrderStatus
        from app.models.order import Order
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)
        with TestingSessionLocal() as db:
            db.get(Order, uuid.UUID(order["id"])).status = OrderStatus.FAKTURIERT
            db.commit()
        unbekannt = uuid.uuid4()

        ergebnis = self._lauf(nur_bestellungen=[uuid.UUID(order["id"]), unbekannt])

        assert ergebnis["bestellungen"] == 0
        assert ergebnis["uebersprungen_status"] == [
            f"{order['order_number']} (FAKTURIERT)",
            f"{unbekannt} (nicht gefunden)",
        ]
        assert _s1_pfandzeile(client, order["id"])["tax_rate"] == "REDUZIERT"
        # Der automatische Lauf meldet fakturierte Bestellungen nicht.
        assert self._lauf()["uebersprungen_status"] == []

    def test_laeuft_je_mandant_nur_einmal(self, client):
        from app.models.app_setting import AppSetting
        from app.services.steuersatz_korrektur import MARKER, korrektur_einmalig_ausfuehren
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)
        with TestingSessionLocal() as db:
            erstes = korrektur_einmalig_ausfuehren(db)
            db.commit()
        assert erstes["bestellungen"] == 1

        _s1_altstand(order["id"])  # dieselbe Abweichung taucht wieder auf
        with TestingSessionLocal() as db:
            zweites = korrektur_einmalig_ausfuehren(db)
            db.commit()
            assert db.get(AppSetting, MARKER) is not None

        assert zweites is None
        assert _s1_pfandzeile(client, order["id"])["tax_rate"] == "REDUZIERT"

    def test_auto_migrate_fuehrt_die_korrektur_aus(self):
        """Verdrahtung in tenancy._auto_migrate — auf einer eigenen In-Memory-
        Engine, die geteilte Test-Engine bleibt unberührt."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from sqlalchemy.pool import StaticPool
        from app.database import Base
        from app.models.app_setting import AppSetting
        from app.services.steuersatz_korrektur import MARKER
        from app.tenancy import _auto_migrate

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        try:
            _auto_migrate(engine)
            with Session(engine) as s:
                assert s.get(AppSetting, MARKER) is not None
        finally:
            Base.metadata.drop_all(bind=engine)
            engine.dispose()

    def test_gescheiterte_korrektur_blockiert_keine_schemamigration(self, monkeypatch, caplog):
        """Scheitert die Korrektur, laufen die Spaltenmigrationen trotzdem, es
        steht kein Marker, und _auto_migrate wirft nicht — beim nächsten Start
        wird sie erneut versucht. Stünde der Block am Anfang des ersten try,
        fehlte die Spalte; stünde er in dessen except-Zweig, fehlte die
        eigene Fehlermeldung."""
        import logging
        from sqlalchemy import create_engine, inspect, text
        from sqlalchemy.orm import Session
        from sqlalchemy.pool import StaticPool
        from app.database import Base
        from app.models.app_setting import AppSetting
        from app.services.steuersatz_korrektur import MARKER
        from app.tenancy import _auto_migrate

        def scheitert(db, nur_bestellungen=None):
            raise RuntimeError("Korrektur gescheitert (Test)")

        monkeypatch.setattr(
            "app.services.steuersatz_korrektur.korrigiere_offene_bestellpositionen", scheitert)

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        try:
            # Älteres Schema: eine Spalte fehlt, die _auto_migrate nachträgt.
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE invoices DROP COLUMN service_period_end"))

            with caplog.at_level(logging.ERROR, logger="app.tenancy"):
                _auto_migrate(engine)  # wirft nicht

            spalten = {c["name"] for c in inspect(engine).get_columns("invoices")}
            assert "service_period_end" in spalten
            with Session(engine) as s:
                assert s.get(AppSetting, MARKER) is None
            assert "Steuersatz-Korrektur fehlgeschlagen" in caplog.text
        finally:
            Base.metadata.drop_all(bind=engine)
            engine.dispose()
