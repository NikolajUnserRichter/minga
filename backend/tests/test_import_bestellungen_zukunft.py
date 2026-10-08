import io
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from openpyxl import load_workbook

from tests.conftest import TestingSessionLocal


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _heute_berlin():
    return datetime.now(ZoneInfo("Europe/Berlin")).date()


def _kunde(client, name="Testküche Zukunft"):
    response = client.post("/api/v1/sales/customers", json={"name": name, "typ": "GASTRO"})
    assert response.status_code == 201, response.text
    return response.json()


def _produkt(sku="MG-ZUKUNFT"):
    from app.models.product import Product, ProductCategory
    from app.models.unit import UnitCategory, UnitOfMeasure

    with TestingSessionLocal() as db:
        unit = UnitOfMeasure(
            code=f"STK-{sku}",
            name=f"Stück {sku}",
            symbol="Stk",
            category=UnitCategory.COUNT,
            is_base_unit=True,
        )
        db.add(unit)
        db.flush()
        product = Product(
            sku=sku,
            name=f"Produkt {sku}",
            category=ProductCategory.MICROGREEN,
            base_unit_id=unit.id,
            base_price=Decimal("3.90"),
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        return {"id": str(product.id), "sku": product.sku, "name": product.name}


def _import_bestellungen(client, rows):
    template = client.get("/api/v1/imports/template/order_history")
    assert template.status_code == 200, template.text
    workbook = load_workbook(io.BytesIO(template.content))
    sheet = workbook["Daten"]
    for row in rows:
        sheet.append(row)
    content = io.BytesIO()
    workbook.save(content)
    return client.post(
        "/api/v1/imports/order_history",
        files={"file": ("bestellungen.xlsx", content.getvalue(), XLSX_MIME)},
    )


def _zeile(externe_nummer, kunde, produkt, bestelldatum, lieferdatum, status=None):
    return [
        externe_nummer,
        kunde["name"],
        bestelldatum,
        lieferdatum,
        produkt["sku"],
        2,
        "STK",
        "3.90",
        status,
        None,
    ]


def _bestellung(client, externe_nummer):
    response = client.get("/api/v1/sales/orders")
    assert response.status_code == 200, response.text
    summary = next(item for item in response.json()["items"] if item["customer_reference"] == externe_nummer)
    response = client.get(f"/api/v1/sales/orders/{summary['id']}")
    assert response.status_code == 200, response.text
    return response.json()


def test_leerer_status_zukunft_wird_bestaetigt_und_bleibt_bearbeitbar(client):
    heute = _heute_berlin()
    lieferdatum = heute + timedelta(days=3)
    kunde = _kunde(client)
    produkt = _produkt()
    externe_nummer = "ZUK-LEER-001"

    response = _import_bestellungen(
        client,
        [_zeile(externe_nummer, kunde, produkt, heute, lieferdatum)],
    )
    assert response.status_code == 200, response.text

    order = _bestellung(client, externe_nummer)
    assert order["status"] == "BESTAETIGT"
    assert order["actual_delivery_date"] is None
    assert order["confirmed_delivery_date"] == lieferdatum.isoformat()

    plan_date = lieferdatum - timedelta(days=1)
    response = client.get("/api/v1/production/day-plan", params={"target_date": plan_date.isoformat()})
    assert response.status_code == 200, response.text
    assert any(item["order_id"] == order["id"] for item in response.json()["verpacken"])

    response = client.post(
        f"/api/v1/sales/orders/{order['id']}/lines",
        json={
            "product_id": produkt["id"],
            "product_name": produkt["name"],
            "quantity": 1,
            "unit": "STK",
            "unit_price": "3.90",
        },
    )
    assert response.status_code == 201, response.text


def test_leerer_status_vergangenheit_wird_geliefert(client):
    heute = _heute_berlin()
    lieferdatum = heute - timedelta(days=3)
    kunde = _kunde(client)
    produkt = _produkt()
    externe_nummer = "ALT-LEER-001"

    response = _import_bestellungen(
        client,
        [_zeile(externe_nummer, kunde, produkt, lieferdatum, lieferdatum)],
    )
    assert response.status_code == 200, response.text

    order = _bestellung(client, externe_nummer)
    assert order["status"] == "GELIEFERT"
    assert order["actual_delivery_date"] == lieferdatum.isoformat()


def test_leerer_status_heute_wird_bestaetigt(client):
    heute = _heute_berlin()
    kunde = _kunde(client)
    produkt = _produkt()
    externe_nummer = "HEUTE-LEER-001"

    response = _import_bestellungen(
        client,
        [_zeile(externe_nummer, kunde, produkt, heute, heute)],
    )
    assert response.status_code == 200, response.text

    order = _bestellung(client, externe_nummer)
    assert order["status"] == "BESTAETIGT"
    assert order["actual_delivery_date"] is None
    assert order["confirmed_delivery_date"] == heute.isoformat()


def test_geliefert_mit_zukunftsdatum_lehnt_ganzen_lauf_ab(client):
    heute = _heute_berlin()
    lieferdatum = heute + timedelta(days=3)
    kunde = _kunde(client)
    produkt = _produkt()
    gueltige_nummer = "ROLLBACK-OK-001"
    fehlerhafte_nummer = "ROLLBACK-FEHLER-001"

    response = _import_bestellungen(
        client,
        [
            _zeile(gueltige_nummer, kunde, produkt, heute, lieferdatum, "BESTAETIGT"),
            _zeile(fehlerhafte_nummer, kunde, produkt, heute, lieferdatum, "GELIEFERT"),
        ],
    )

    assert response.status_code == 400, response.text
    assert fehlerhafte_nummer in response.json()["detail"]
    assert lieferdatum.strftime("%d.%m.%Y") in response.json()["detail"]
    orders = client.get("/api/v1/sales/orders").json()["items"]
    references = {item["customer_reference"] for item in orders}
    assert gueltige_nummer not in references
    assert fehlerhafte_nummer not in references


def test_ausdruecklich_bestaetigt_in_vergangenheit_bleibt_bestaetigt(client):
    heute = _heute_berlin()
    lieferdatum = heute - timedelta(days=3)
    kunde = _kunde(client)
    produkt = _produkt()
    externe_nummer = "ALT-BESTAETIGT-001"

    response = _import_bestellungen(
        client,
        [_zeile(externe_nummer, kunde, produkt, lieferdatum, lieferdatum, "BESTAETIGT")],
    )
    assert response.status_code == 200, response.text

    order = _bestellung(client, externe_nummer)
    assert order["status"] == "BESTAETIGT"
    assert order["actual_delivery_date"] is None


def test_vorlage_enthaelt_leeren_status_mit_zukunftsdatum(client):
    heute = _heute_berlin()
    response = client.get("/api/v1/imports/template/order_history")
    assert response.status_code == 200, response.text

    workbook = load_workbook(io.BytesIO(response.content), data_only=True)
    sheet = workbook["Beispiel"]
    headers = [str(cell.value).split(" ")[0] for cell in sheet[1]]
    lieferdatum_index = headers.index("lieferdatum")
    status_index = headers.index("status")
    beispielzeilen = list(sheet.iter_rows(min_row=2, max_row=4, values_only=True))

    assert any(
        row[status_index] in (None, "")
        and datetime.strptime(row[lieferdatum_index], "%d.%m.%Y").date() > heute
        for row in beispielzeilen
    )


# ===========================================================================
# P5 — Bestell-Import härten (A6-Rest, Gernot 08.10.2026). Helfer: _p5_.
# ===========================================================================


def _p5_zeile(externe_nummer, kunde, produkt, bestelldatum, lieferdatum, *,
              menge=2, einheit="STK", preis="3.90", status=None, bundle=None):
    """Eine Importzeile mit frei wählbaren Spalten (Reihenfolge wie COLUMNS)."""
    return [externe_nummer, kunde["name"], bestelldatum, lieferdatum, produkt["sku"],
            menge, einheit, preis, status, bundle]


def _p5_referenzen(client):
    response = client.get("/api/v1/sales/orders")
    assert response.status_code == 200, response.text
    return {item["customer_reference"] for item in response.json()["items"]}


class TestP5AllesOderNichts:
    """Lücke 10 aus T1: Eine Zeile mit Lesefehler fiel still heraus, die
    Bestellung entstand ohne sie, und ein erneuter Upload übersprang sie."""

    def _datei(self, kunde, produkt, preis_zweite_position):
        heute = _heute_berlin()
        lieferdatum = heute + timedelta(days=2)
        return [
            _p5_zeile("P5-NACHBAR", kunde, produkt, heute, lieferdatum),
            _p5_zeile("P5-ZWEI", kunde, produkt, heute, lieferdatum),
            _p5_zeile("P5-ZWEI", kunde, produkt, heute, lieferdatum, preis=preis_zweite_position),
        ]

    def test_zeile_ohne_preis_legt_keine_bestellung_an(self, client):
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, self._datei(kunde, produkt, None))

        assert response.status_code == 400, response.text
        detail = response.json()["detail"]
        assert "keine Bestellung angelegt" in detail
        # Datenzeilen beginnen in Zeile 3 (Kopf + Typzeile davor)
        assert "Zeile 5: 'einzelpreis' fehlt" in detail
        referenzen = _p5_referenzen(client)
        assert "P5-ZWEI" not in referenzen
        assert "P5-NACHBAR" not in referenzen, "alles oder nichts: auch die fehlerfreie Bestellung nicht"

    def test_korrigierte_datei_bringt_beide_positionen(self, client):
        kunde = _kunde(client)
        produkt = _produkt()
        assert _import_bestellungen(client, self._datei(kunde, produkt, None)).status_code == 400

        response = _import_bestellungen(client, self._datei(kunde, produkt, "4.50"))

        assert response.status_code == 200, response.text
        assert response.json()["created"] == 2
        assert len(_bestellung(client, "P5-ZWEI")["lines"]) == 2

    def test_alle_fehler_in_einer_antwort(self, client):
        heute = _heute_berlin()
        lieferdatum = heute + timedelta(days=2)
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-OHNE-MENGE", kunde, produkt, heute, lieferdatum, menge=None),
            _p5_zeile("P5-FALSCHE-SKU", kunde, {"sku": "GIBT-ES-NICHT"}, heute, lieferdatum),
            _p5_zeile("P5-FREMDER-KUNDE", {"name": "Unbekannte GmbH"}, produkt, heute, lieferdatum),
        ])

        assert response.status_code == 400, response.text
        detail = response.json()["detail"]
        assert "Zeile 3: 'menge' fehlt" in detail
        assert "GIBT-ES-NICHT" in detail
        assert "Unbekannte GmbH" in detail
        assert _p5_referenzen(client) == set()


class TestP5Kopfdaten:
    """Status, Bestelldatum und Kunde werden geprüft statt still übernommen."""

    @pytest.mark.parametrize("eingabe, erwartet", [
        ("Bestätigt", "BESTAETIGT"),        # heute: still GELIEFERT
        ("in produktion", "IN_PRODUKTION"),  # heute: still GELIEFERT
        ("Geliefert", "GELIEFERT"),          # Charakterisierung, schon grün
        ("STORNIERT", "STORNIERT"),          # Charakterisierung, schon grün
    ])
    def test_bezeichnungen_der_oberflaeche_werden_erkannt(self, client, eingabe, erwartet):
        vergangen = _heute_berlin() - timedelta(days=3)
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-STATUS", kunde, produkt, vergangen, vergangen, status=eingabe),
        ])

        assert response.status_code == 200, response.text
        assert _bestellung(client, "P5-STATUS")["status"] == erwartet

    def test_unbekannter_status_ist_ein_fehler(self, client):
        heute = _heute_berlin()
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-OFFEN", kunde, produkt, heute, heute + timedelta(days=2), status="offen"),
        ])

        assert response.status_code == 400, response.text
        assert "Status 'offen'" in response.json()["detail"]
        assert _p5_referenzen(client) == set()

    def test_gepackt_fuer_ausstehende_lieferung_wird_abgelehnt(self, client):
        """IN_PRODUKTION heißt nach P2 „gepackt“ — das passiert im Tagesplan,
        nicht im Import (P2, Entscheidung M2)."""
        heute = _heute_berlin()
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-GEPACKT", kunde, produkt, heute, heute + timedelta(days=2), status="IN_PRODUKTION"),
        ])

        assert response.status_code == 400, response.text
        assert "P5-GEPACKT" in response.json()["detail"]
        assert "IN_PRODUKTION" in response.json()["detail"]

    def test_bestelldatum_nach_lieferdatum(self, client):
        heute = _heute_berlin()
        kunde = _kunde(client)
        produkt = _produkt()
        bestelldatum = heute - timedelta(days=1)
        lieferdatum = heute - timedelta(days=3)

        response = _import_bestellungen(client, [
            _p5_zeile("P5-SPAET-BESTELLT", kunde, produkt, bestelldatum, lieferdatum),
        ])

        assert response.status_code == 400, response.text
        detail = response.json()["detail"]
        assert "P5-SPAET-BESTELLT" in detail
        assert f"Bestelldatum {bestelldatum.strftime('%d.%m.%Y')} liegt nach dem Lieferdatum" in detail

    def test_bestelldatum_in_der_zukunft(self, client):
        """Produktionsfall BE-20261011-0001: Bestelldatum 11.10., importiert am 08.10."""
        heute = _heute_berlin()
        kunde = _kunde(client)
        produkt = _produkt()
        bestelldatum = heute + timedelta(days=1)

        response = _import_bestellungen(client, [
            _p5_zeile("P5-ZUKUNFT-BESTELLT", kunde, produkt, bestelldatum, heute + timedelta(days=3)),
        ])

        assert response.status_code == 400, response.text
        assert f"Bestelldatum {bestelldatum.strftime('%d.%m.%Y')} liegt in der Zukunft" in response.json()["detail"]

    def test_deaktivierter_kunde(self, client):
        """Wie create_order (sales.py: 'Kunde ist deaktiviert')."""
        import uuid
        from app.models.customer import Customer

        heute = _heute_berlin()
        kunde = _kunde(client, name="Ehemals GmbH")
        produkt = _produkt()
        with TestingSessionLocal() as db:
            db.get(Customer, uuid.UUID(kunde["id"])).aktiv = False
            db.commit()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-INAKTIV", kunde, produkt, heute, heute + timedelta(days=2)),
        ])

        assert response.status_code == 400, response.text
        assert "Ehemals GmbH" in response.json()["detail"]
        assert "deaktiviert" in response.json()["detail"]

    def test_vorlage_nennt_die_gueltigen_status(self, client):
        response = client.get("/api/v1/imports/template/order_history")
        workbook = load_workbook(io.BytesIO(response.content), data_only=True)
        texte = " ".join(
            str(zelle) for zeile in workbook["Beispiel"].iter_rows(values_only=True) for zelle in zeile if zelle
        )
        assert "ENTWURF, BESTAETIGT, IN_PRODUKTION, GELIEFERT, FAKTURIERT, STORNIERT" in texte
