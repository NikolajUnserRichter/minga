"""Gernot-Feedback vom 07./08.10.2026 — Paket 3 (Belegfluss).

Gemeinsame Testdatei der Abschnitte Q1–Q7. Helfer und Klassen tragen ein
Abschnitts-Präfix (_q1_/TestQ1, _q2_/TestQ2, …): ein gleichnamiger Helfer
würde still ersetzt. Jeder Abschnitt bringt seine Imports selbst mit.
"""

# ============================================================
# Q1 — Rechnungsnummer erst beim Finalisieren, Sammelrechnung als Entwurf,
#      eine Festschreib-Funktion für alle Wege aus dem Entwurf
# ============================================================

import re
import threading
import time
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.conftest import TestingSessionLocal
from tests.test_documents_preise import _pdf_text

_Q1_PLATZHALTER = re.compile(r"^ENTWURF-[0-9A-F]{12}$")


def _q1_heute():
    """Rechnungsdatum beim Festschreiben: heute in Europe/Berlin."""
    from app.services.invoice_service import _heute_berlin
    return _heute_berlin()


def _q1_jahr():
    return _q1_heute().year


def _q1_nr(laufnummer, jahr=None):
    return f"RE-{jahr or _q1_jahr()}-{laufnummer:05d}"


def _q1_kunde(client, name="Ökoring Handels GmbH", **extra):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "HANDEL", **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _q1_entwurf(client, kunde, **kopf):
    """Entwurf mit einer Freitextposition: 10 × 2,50 € zu 7 % = 26,75 € brutto."""
    r = client.post("/api/v1/invoices", json={
        "customer_id": kunde["id"], "invoice_date": date.today().isoformat(), **kopf,
        "lines": [{"description": "Erbsen-Schale", "quantity": 10, "unit": "STK",
                   "unit_price": "2.50", "tax_rate": "REDUZIERT"}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _q1_finalisieren(client, rechnung):
    r = client.post(f"/api/v1/invoices/{rechnung['id']}/finalize")
    assert r.status_code == 200, r.text
    return r.json()


def _q1_bestellung_mit_lieferschein(client, kunde):
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"], "requested_delivery_date": "2026-03-05",
        "lines": [{"product_name": "Erbsen-Schale", "quantity": 10, "unit": "STK",
                   "unit_price": 2.50, "tax_rate": "REDUZIERT"}],
    })
    assert r.status_code == 201, r.text
    bestellung = r.json()
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes", json={})
    assert r.status_code == 201, r.text
    return bestellung, r.json()


def _q1_lauf(client, endpoint="commit"):
    r = client.post(f"/api/v1/invoices/batch-run/{endpoint}",
                    json={"period_from": "2026-03-01", "period_to": "2026-03-31"})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _q1_altentwurf(kunde, nummer, tage_alt=10):
    """Entwurf, wie ihn der Code vor Paket 3 anlegte: echte RE-Nummer schon
    beim Anlegen, Datum in der Vergangenheit (Bestand wie RE-2026-00003).
    Direkt per ORM — über die API entsteht so ein Entwurf nicht mehr."""
    from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus, TaxRate
    datum = date.today() - timedelta(days=tage_alt)
    with TestingSessionLocal() as db:
        inv = Invoice(
            invoice_number=nummer, customer_id=uuid.UUID(kunde["id"]),
            invoice_date=datum, due_date=datum + timedelta(days=14),
            status=InvoiceStatus.ENTWURF,
        )
        db.add(inv)
        db.flush()
        db.add(InvoiceLine(
            invoice_id=inv.id, position=1, description="Erbsen-Schale",
            quantity=Decimal("10"), unit="STK", unit_price=Decimal("2.50"),
            tax_rate=TaxRate.REDUZIERT, line_total=Decimal("25.00"),
        ))
        db.commit()
        return str(inv.id)


def _q1_mailversand(monkeypatch, fehler=None):
    """SMTP 'konfiguriert' (Umgebung) und Versand abgefangen; liefert die
    Argumente der Mail. fehler: Ausnahme, die der Versand wirft.

    Die EINZIGE Stelle der Q1-Tests, die den Versand ersetzt: verlegt ein
    späterer Abschnitt den Versand (Q2: app.services.belegversand), wird
    nur dieser Helfer umgehängt."""
    monkeypatch.setenv("SMTP_HOST", "smtp.farm.example")
    monkeypatch.setenv("SMTP_USER", "versand@farm.example")
    gesendet = {}

    def versand(**kw):
        if fehler is not None:
            raise fehler
        gesendet.update(kw)

    monkeypatch.setattr("app.api.v1.invoices.send_email", versand)
    return gesendet


def _q1_mandanten_db(monkeypatch, tmp_path, slug="q1test"):
    """Mandanten-DB wie in Produktion (Datei, WAL, Fremdschlüssel an, Engine
    aus tenancy). Die Test-DB (in-memory, StaticPool) kann Nebenläufigkeit
    nicht zeigen."""
    from app import tenancy
    from app.database import Base
    monkeypatch.setattr(tenancy, "TENANTS_DIR", tmp_path)
    registry = tenancy._TenantRegistry()
    Base.metadata.create_all(registry.get_engine(slug))
    return registry, registry.get_sessionmaker(slug)


def _q1_orm_entwuerfe(Session, anzahl=1):
    """Entwürfe mit je einer Position (2,50 € zu 7 %) über den Service."""
    from app.models.customer import Customer, CustomerType
    from app.models.invoice import TaxRate
    from app.services.invoice_service import InvoiceService
    with Session() as db:
        kunde = Customer(name="Großer Kern", typ=CustomerType.HANDEL, aktiv=True)
        db.add(kunde)
        db.flush()
        svc = InvoiceService(db)
        ids = []
        for _ in range(anzahl):
            inv = svc.create_invoice(customer_id=kunde.id)
            svc.add_line(inv.id, "Erbsen-Schale", Decimal("1"), "STK",
                         Decimal("2.50"), tax_rate=TaxRate.REDUZIERT)
            ids.append(inv.id)
        db.commit()
        return ids


def _q1_langsame_nummer(monkeypatch, gesperrt=None, pause=0.4):
    """Hält die Schreibsperre nach dem Lesen der höchsten Nummer `pause`
    Sekunden fest und meldet über `gesperrt` (threading.Event), dass sie
    gehalten wird."""
    from app.services.invoice_service import InvoiceService
    original = InvoiceService._naechste_rechnungsnummer

    def langsam(self, jahr):
        nummer = original(self, jahr)
        if gesperrt is not None:
            gesperrt.set()
        time.sleep(pause)
        return nummer

    monkeypatch.setattr(InvoiceService, "_naechste_rechnungsnummer", langsam)


def _q1_gleichzeitig(*vorgaenge):
    """Startet die Vorgänge in eigenen Threads; liefert die Fehler als
    Liste von (Name, repr). Jeder Vorgang ist (Name, Funktion)."""
    fehler = []

    def lauf(name, fn):
        try:
            fn()
        except Exception as e:  # noqa: BLE001 — der Test wertet die Fehler aus
            fehler.append((name, repr(e)))

    threads = [threading.Thread(target=lauf, args=v) for v in vorgaenge]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return fehler


class TestQ1MandantPflicht:
    """Sicherheit (Q1.0): Fachdaten nur mit Mandant aus der Subdomain.

    Auf dem Apex- und dem Admin-Host lief /api/v1 ohne Request-Tenant:
    get_db fiel auf DEFAULT_TENANT_SLUG zurück, get_current_user glich den
    tenant_slug des Tokens nicht ab. Ein Login eines anderen Mandanten
    (Demo: anna, Rolle admin) erreichte so die Daten des Default-Mandanten."""

    @pytest.mark.parametrize("host", ["admin.novaerp.de", "novaerp.de", "www.novaerp.de"])
    def test_fachdaten_ohne_mandant_404(self, client, monkeypatch, host):
        monkeypatch.setenv("SPROUDDESK_ROOT_DOMAIN", "novaerp.de")
        for methode, pfad in (
            ("GET", "/api/v1/invoices"),
            ("GET", "/api/v1/sales/customers"),
            ("POST", "/api/v1/invoices/batch-run/commit"),
            ("DELETE", f"/api/v1/invoices/{uuid.uuid4()}"),
        ):
            r = client.request(methode, pfad, headers={"Host": host})
            assert r.status_code == 404, (host, methode, pfad, r.status_code, r.text)
            assert "Tenant nicht gefunden" in r.json()["detail"]

    def test_plattform_und_marketing_bleiben_erreichbar(self, client, monkeypatch):
        monkeypatch.setenv("SPROUDDESK_ROOT_DOMAIN", "novaerp.de")
        monkeypatch.delenv("PLATFORM_ADMIN_KEY", raising=False)

        r = client.get("/api/v1/platform/tenants", headers={"Host": "admin.novaerp.de"})
        assert r.status_code == 503, r.text  # Key nicht gesetzt — aber nicht 404
        r = client.get("/api/v1/branding", headers={"Host": "novaerp.de"})
        assert r.status_code == 200, r.text
        r = client.post("/api/track", json={"p": "/"}, headers={"Host": "novaerp.de"})
        assert r.status_code == 200, r.text

    def test_mandanten_host_unveraendert(self, client):
        """Gegenprobe: der Mandant aus der Subdomain (Tests: localhost) bleibt."""
        assert client.get("/api/v1/invoices").status_code == 200
