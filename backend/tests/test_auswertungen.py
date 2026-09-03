"""Auswertungen — Umsatz je Monat und Kundentyp.

Beim Verdrahten der Rollen aufgefallen: der Endpunkt nutzte ``to_char``, eine
Postgres-Funktion. Jeder Mandant läuft aber auf SQLite — die Umsatzauswertung
lief deshalb IMMER in einen 500er, auch in der Produktion. Der bestehende Test
in test_refinements.py prüfte nur ``!= 404`` und blieb dabei grün.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.customer import Customer, CustomerType
from app.models.invoice import Invoice, InvoiceStatus


@pytest.fixture
def rechnungen(client, db):
    """Zwei Kunden verschiedener Typen mit Rechnungen in zwei Monaten."""
    gastro = Customer(name="Restaurant Alt", typ=CustomerType.GASTRO)
    handel = Customer(name="BioMarkt Neu", typ=CustomerType.HANDEL)
    db.add_all([gastro, handel])
    db.flush()

    heute = date.today()
    voriger = (heute.replace(day=1) - timedelta(days=1)).replace(day=1)

    db.add_all([
        Invoice(invoice_number="RE-1", customer_id=gastro.id, invoice_date=heute,
                due_date=heute, status=InvoiceStatus.OFFEN, subtotal=Decimal("100.00")),
        Invoice(invoice_number="RE-2", customer_id=gastro.id, invoice_date=heute,
                due_date=heute, status=InvoiceStatus.BEZAHLT, subtotal=Decimal("50.00")),
        Invoice(invoice_number="RE-3", customer_id=handel.id, invoice_date=voriger,
                due_date=voriger, status=InvoiceStatus.BEZAHLT, subtotal=Decimal("200.00")),
        # Entwürfe zählen nicht mit — sonst stünde Umsatz im Chart, den es nicht gibt
        Invoice(invoice_number="RE-4", customer_id=handel.id, invoice_date=heute,
                due_date=heute, status=InvoiceStatus.ENTWURF, subtotal=Decimal("999.00")),
    ])
    db.commit()
    return {"heute": heute.strftime("%Y-%m"), "voriger": voriger.strftime("%Y-%m")}


class TestUmsatzauswertung:
    def test_liefert_monate_statt_serverfehler(self, client, rechnungen):
        r = client.get("/api/v1/analytics/revenue")

        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_gruppiert_nach_monat_und_kundentyp(self, client, rechnungen):
        zeilen = client.get("/api/v1/analytics/revenue").json()

        gefunden = {(z["month"], z["customer_type"]): Decimal(str(z["revenue"])) for z in zeilen}
        # Zwei Rechnungen desselben Kunden im selben Monat werden summiert
        assert gefunden[(rechnungen["heute"], "GASTRO")] == Decimal("150.00")
        assert gefunden[(rechnungen["voriger"], "HANDEL")] == Decimal("200.00")

    def test_entwuerfe_bleiben_draussen(self, client, rechnungen):
        zeilen = client.get("/api/v1/analytics/revenue").json()

        gefunden = {(z["month"], z["customer_type"]) for z in zeilen}
        assert (rechnungen["heute"], "HANDEL") not in gefunden

    def test_monat_ist_sortierbar_formatiert(self, client, rechnungen):
        zeilen = client.get("/api/v1/analytics/revenue").json()

        monate = [z["month"] for z in zeilen]
        assert all(len(m) == 7 and m[4] == "-" for m in monate), monate
        assert monate == sorted(monate), "Chart erwartet aufsteigende Monate"
