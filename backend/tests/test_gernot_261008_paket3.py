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


class TestQ1Platzhalter:
    """Jeder neue Entwurf trägt ENTWURF-… statt einer Rechnungsnummer."""

    def test_neuer_entwurf_traegt_platzhalter(self, client):
        entwurf = _q1_entwurf(client, _q1_kunde(client))

        assert entwurf["status"] == "ENTWURF"
        assert _Q1_PLATZHALTER.match(entwurf["invoice_number"]), entwurf["invoice_number"]
        assert len(entwurf["invoice_number"]) == 20  # invoice_number ist String(20)

    def test_platzhalter_sind_eindeutig(self, client):
        kunde = _q1_kunde(client)
        nummern = {_q1_entwurf(client, kunde)["invoice_number"] for _ in range(5)}
        assert len(nummern) == 5

    def test_rechnung_aus_bestellung_entsteht_mit_platzhalter(self, client):
        bestellung, _ = _q1_bestellung_mit_lieferschein(client, _q1_kunde(client))
        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")
        assert r.status_code == 201, r.text
        assert _Q1_PLATZHALTER.match(r.json()["invoice_number"])

    def test_liste_neueste_zuerst_auch_bei_platzhaltern(self, client):
        """Entscheidung 6: am selben Tag nach Anlagezeitpunkt, nicht nach dem
        zufälligen Platzhalter."""
        kunde = _q1_kunde(client)
        ids = [_q1_entwurf(client, kunde)["id"] for _ in range(4)]

        liste = client.get("/api/v1/invoices").json()

        assert [x["id"] for x in liste] == list(reversed(ids))


class TestQ1Festschreiben:
    """Nummer, Rechnungsdatum und Fälligkeit entstehen beim Finalisieren."""

    def test_nummern_in_der_reihenfolge_des_finalisierens(self, client):
        kunde = _q1_kunde(client)
        a = _q1_entwurf(client, kunde)
        b = _q1_entwurf(client, kunde)

        b = _q1_finalisieren(client, b)
        a = _q1_finalisieren(client, a)

        assert (b["invoice_number"], a["invoice_number"]) == (_q1_nr(1), _q1_nr(2))
        assert a["status"] == b["status"] == "OFFEN"

    def test_finalisieren_setzt_sent_at_nicht(self, client):
        """Spec B2: sent_at heißt 'per Mail versendet'."""
        rechnung = _q1_finalisieren(client, _q1_entwurf(client, _q1_kunde(client)))
        assert rechnung["sent_at"] is None

    def test_ausstellung_wird_vermerkt(self, client):
        """Wer hat wann ausgestellt — sent_at sagt das nicht mehr (Spec B2)."""
        rechnung = _q1_finalisieren(client, _q1_entwurf(client, _q1_kunde(client)))

        notiz = client.get(f"/api/v1/invoices/{rechnung['id']}").json()["internal_notes"]

        assert re.search(
            rf"Ausgestellt am \d\d\.\d\d\.\d{{4}} \d\d:\d\d als {_q1_nr(1)} von testuser", notiz or ""
        ), notiz

    def test_datum_und_faelligkeit_beim_finalisieren(self, client):
        vor_zehn = date.today() - timedelta(days=10)
        entwurf = _q1_entwurf(client, _q1_kunde(client),
                              invoice_date=vor_zehn.isoformat(),
                              due_date=(vor_zehn + timedelta(days=21)).isoformat())

        rechnung = _q1_finalisieren(client, entwurf)

        heute = _q1_heute()
        assert rechnung["invoice_date"] == heute.isoformat()
        # Zahlungsziel des Entwurfs (21 Tage) bleibt, ab dem Ausstellungstag
        assert rechnung["due_date"] == (heute + timedelta(days=21)).isoformat()

    def test_summen_werden_final_berechnet(self, client):
        """Charakterisierung: wie bisher rechnet das Finalisieren die Summen neu."""
        from app.models.invoice import Invoice
        entwurf = _q1_entwurf(client, _q1_kunde(client))
        with TestingSessionLocal() as db:
            db.get(Invoice, uuid.UUID(entwurf["id"])).total = Decimal("1.00")
            db.commit()

        rechnung = _q1_finalisieren(client, entwurf)

        assert Decimal(str(rechnung["total"])) == Decimal("26.75")

    def test_altentwurf_behaelt_re_nummer_und_datum(self, client):
        """Entscheidung 2: bestehende Entwürfe behalten ihre RE-Nummer."""
        kunde = _q1_kunde(client)
        alt_id = _q1_altentwurf(kunde, _q1_nr(3))
        vorher = client.get(f"/api/v1/invoices/{alt_id}").json()

        alt = _q1_finalisieren(client, {"id": alt_id})
        neu = _q1_finalisieren(client, _q1_entwurf(client, kunde))

        assert alt["invoice_number"] == _q1_nr(3)
        assert (alt["invoice_date"], alt["due_date"]) == (vorher["invoice_date"], vorher["due_date"])
        assert neu["invoice_number"] == _q1_nr(4)

    def test_neues_jahr_beginnt_bei_eins(self, client, monkeypatch):
        kunde = _q1_kunde(client)
        _q1_finalisieren(client, _q1_entwurf(client, kunde))
        naechstes = _q1_jahr() + 1
        monkeypatch.setattr("app.services.invoice_service._heute_berlin",
                            lambda: date(naechstes, 1, 2))

        rechnung = _q1_finalisieren(client, _q1_entwurf(client, kunde))

        assert rechnung["invoice_number"] == _q1_nr(1, jahr=naechstes)
        assert rechnung["invoice_date"] == f"{naechstes}-01-02"

    def test_hoechste_nummer_numerisch(self, client):
        from app.services.invoice_service import InvoiceService
        kunde = _q1_kunde(client)
        _q1_altentwurf(kunde, "RE-2031-99999")
        _q1_altentwurf(kunde, "RE-2031-100000")
        with TestingSessionLocal() as db:
            assert InvoiceService(db)._naechste_rechnungsnummer(2031) == "RE-2031-100001"

    def test_leerer_entwurf_wird_abgelehnt_ohne_nummer(self, client):
        r = client.post("/api/v1/invoices", json={
            "customer_id": _q1_kunde(client)["id"], "invoice_date": date.today().isoformat(),
        })
        leer = r.json()

        r = client.post(f"/api/v1/invoices/{leer['id']}/finalize")

        assert r.status_code == 400, r.text
        detail = client.get(f"/api/v1/invoices/{leer['id']}").json()
        assert detail["status"] == "ENTWURF"
        assert _Q1_PLATZHALTER.match(detail["invoice_number"])

    def test_stornorechnung_bekommt_ihre_nummer_beim_festschreiben(self, client):
        rechnung = _q1_finalisieren(client, _q1_entwurf(client, _q1_kunde(client)))

        r = client.post(f"/api/v1/invoices/{rechnung['id']}/cancel",
                        json={"reason": "Preisfehler", "reason_code": "PREISFEHLER"})

        assert r.status_code == 200, r.text
        storno = r.json()["credit_note"]
        assert storno["invoice_number"] == _q1_nr(2)
        assert storno["status"] == "STORNIERT"
        assert storno["sent_at"] is None
        assert storno["due_date"] == storno["invoice_date"]
        assert f"als {_q1_nr(2)} von testuser" in storno["internal_notes"]


class TestQ1Nebenlaeufig:
    """Gleichzeitige Vorgänge auf einer Mandanten-DB wie in Produktion (Datei,
    WAL, Engine aus tenancy). Die Test-DB (in-memory, StaticPool) kann das
    nicht zeigen. Der zweite Vorgang liest seinen Stand, BEVOR der erste
    committet — so wie zwei Requests, die sich überholen."""

    def test_zwei_gleichzeitige_finalisierungen(self, monkeypatch, tmp_path):
        """Zwei VERSCHIEDENE Entwürfe: verschiedene, lückenlose Nummern."""
        from app.models.invoice import Invoice
        from app.services.invoice_service import InvoiceService
        registry, Session = _q1_mandanten_db(monkeypatch, tmp_path)
        try:
            ids = _q1_orm_entwuerfe(Session, 2)
            # Nummer lesen, dann warten: ohne Schreibsperre läsen beide
            # Vorgänge dieselbe höchste Nummer (gegengeprüft: UNIQUE-Fehler).
            _q1_langsame_nummer(monkeypatch, pause=0.3)
            start = threading.Barrier(2)
            ergebnis = {}

            def finalisieren(invoice_id):
                def fn():
                    with Session() as db:
                        start.wait()
                        inv = InvoiceService(db).festschreiben(db.get(Invoice, invoice_id))
                        db.commit()
                        ergebnis[invoice_id] = inv.invoice_number
                return (str(invoice_id), fn)

            fehler = _q1_gleichzeitig(*(finalisieren(i) for i in ids))

            assert fehler == []
            assert sorted(ergebnis.values()) == [_q1_nr(1), _q1_nr(2)]
        finally:
            registry.dispose_tenant("q1test")

    def test_derselbe_entwurf_zweimal_gleichzeitig(self, monkeypatch, tmp_path):
        """Zwei Tabs, Doppelklick oder "Mailen" neben "Finalisieren" auf
        DENSELBEN Entwurf: der zweite Vorgang scheitert, die gemeldete Nummer
        ist die gespeicherte, keine Lücke."""
        from app.models.invoice import Invoice
        from app.services.invoice_service import InvoiceService
        registry, Session = _q1_mandanten_db(monkeypatch, tmp_path)
        try:
            [inv_id] = _q1_orm_entwuerfe(Session)
            gesperrt = threading.Event()
            _q1_langsame_nummer(monkeypatch, gesperrt)
            geladen = threading.Barrier(2)
            gemeldet = {}

            def finalisieren(name, warten):
                def fn():
                    with Session() as db:
                        inv = db.get(Invoice, inv_id)  # beide sehen den Entwurf
                        geladen.wait()
                        if warten:
                            assert gesperrt.wait(5)    # A hält die Sperre
                        InvoiceService(db).festschreiben(inv)
                        db.commit()
                        gemeldet[name] = inv.invoice_number
                return (name, fn)

            fehler = _q1_gleichzeitig(finalisieren("A", False), finalisieren("B", True))

            with Session() as db:
                gespeichert = db.get(Invoice, inv_id).invoice_number
            assert gemeldet == {"A": _q1_nr(1)}
            assert gespeichert == _q1_nr(1)
            assert [(n, "Nur Entwürfe können finalisiert werden" in e) for n, e in fehler] == [("B", True)]
        finally:
            registry.dispose_tenant("q1test")

    def test_zwei_gleichzeitige_stornos(self, monkeypatch, tmp_path):
        """Zwei Stornos derselben Rechnung: genau eine Stornorechnung."""
        from sqlalchemy import select
        from app.models.invoice import Invoice
        from app.services.invoice_service import InvoiceService
        registry, Session = _q1_mandanten_db(monkeypatch, tmp_path)
        try:
            [inv_id] = _q1_orm_entwuerfe(Session)
            with Session() as db:
                InvoiceService(db).festschreiben(db.get(Invoice, inv_id))
                db.commit()
            gesperrt = threading.Event()
            _q1_langsame_nummer(monkeypatch, gesperrt)
            geladen = threading.Barrier(2)

            def stornieren(name, warten):
                def fn():
                    with Session() as db:
                        db.get(Invoice, inv_id)        # beide sehen OFFEN
                        geladen.wait()
                        if warten:
                            assert gesperrt.wait(5)
                        InvoiceService(db).cancel_invoice(inv_id, f"Storno {name}")
                        db.commit()
                return (name, fn)

            fehler = _q1_gleichzeitig(stornieren("A", False), stornieren("B", True))

            with Session() as db:
                storni = db.execute(
                    select(Invoice.invoice_number).where(Invoice.original_invoice_id == inv_id)
                ).scalars().all()
            assert storni == [_q1_nr(2)]
            assert [(n, "bereits storniert" in e) for n, e in fehler] == [("B", True)]
        finally:
            registry.dispose_tenant("q1test")


class TestQ1AndereWege:
    """Jeder andere Weg aus dem Entwurf führt über festschreiben — oder ist zu."""

    def test_mailen_eines_entwurfs_schreibt_fest_mit_echter_nummer(self, client, monkeypatch):
        entwurf = _q1_entwurf(client, _q1_kunde(client))
        gesendet = _q1_mailversand(monkeypatch)

        r = client.post(f"/api/v1/invoices/{entwurf['id']}/send",
                        params={"to_email": "einkauf@oekoring.example"})

        assert r.status_code == 200, r.text
        assert r.json()["invoice_number"] == _q1_nr(1)
        assert _q1_nr(1) in gesendet["subject"]
        assert gesendet["attachment_filename"] == f"{_q1_nr(1)}.pdf"
        detail = client.get(f"/api/v1/invoices/{entwurf['id']}").json()
        assert detail["status"] == "OFFEN"
        assert detail["sent_at"] is not None

    def test_versandfehler_laesst_rechnung_finalisiert_und_unversendet(self, client, monkeypatch):
        entwurf = _q1_entwurf(client, _q1_kunde(client))
        _q1_mailversand(monkeypatch, fehler=ConnectionError("SMTP nicht erreichbar"))

        r = client.post(f"/api/v1/invoices/{entwurf['id']}/send",
                        params={"to_email": "einkauf@oekoring.example"})

        assert r.status_code == 502, r.text
        assert r.json()["detail"].startswith(f"Rechnung {_q1_nr(1)} ist finalisiert, aber nicht versendet.")
        detail = client.get(f"/api/v1/invoices/{entwurf['id']}").json()
        assert (detail["status"], detail["invoice_number"]) == ("OFFEN", _q1_nr(1))
        assert detail["sent_at"] is None
        # die Nummer ist vergeben, die nächste schließt lückenlos an
        naechste = _q1_finalisieren(client, _q1_entwurf(client, _q1_kunde(client, "Bodan")))
        assert naechste["invoice_number"] == _q1_nr(2)

    def test_mailen_ohne_smtp_bleibt_entwurf(self, client, monkeypatch):
        """Ohne SMTP-Einstellungen scheitert der Versand sicher — dann wird
        nicht festgeschrieben, keine Nummer verbraucht."""
        for schluessel in ("SMTP_HOST", "SMTP_USER"):
            monkeypatch.delenv(schluessel, raising=False)
        entwurf = _q1_entwurf(client, _q1_kunde(client))

        r = client.post(f"/api/v1/invoices/{entwurf['id']}/send",
                        params={"to_email": "einkauf@oekoring.example"})

        assert r.status_code == 503, r.text
        assert "Der Entwurf bleibt Entwurf" in r.json()["detail"]
        detail = client.get(f"/api/v1/invoices/{entwurf['id']}").json()
        assert detail["status"] == "ENTWURF"
        assert _Q1_PLATZHALTER.match(detail["invoice_number"])
        assert _q1_finalisieren(client, entwurf)["invoice_number"] == _q1_nr(1)

    def test_patch_mit_status_wird_abgelehnt(self, client):
        entwurf = _q1_entwurf(client, _q1_kunde(client))

        r = client.patch(f"/api/v1/invoices/{entwurf['id']}", json={"status": "OFFEN"})

        assert r.status_code == 422, r.text
        assert client.get(f"/api/v1/invoices/{entwurf['id']}").json()["status"] == "ENTWURF"

    def test_zahlung_auf_entwurf_wird_abgelehnt(self, client):
        entwurf = _q1_entwurf(client, _q1_kunde(client))

        r = client.post(f"/api/v1/invoices/{entwurf['id']}/payments", json={
            "amount": "26.75", "payment_date": date.today().isoformat(),
        })

        assert r.status_code == 400, r.text
        assert client.get(f"/api/v1/invoices/{entwurf['id']}").json()["status"] == "ENTWURF"

    def test_mahnung_auf_entwurf_wird_abgelehnt(self, client):
        entwurf = _q1_entwurf(client, _q1_kunde(client))

        r = client.post(f"/api/v1/invoices/{entwurf['id']}/payment-reminder")

        assert r.status_code == 400, r.text
        from app.models.invoice import Invoice
        with TestingSessionLocal() as db:
            assert not db.get(Invoice, uuid.UUID(entwurf["id"])).reminder_level

    def test_lexoffice_nimmt_keinen_beleg_ohne_nummer(self, client, monkeypatch):
        def kein_netz(*args, **kwargs):
            raise AssertionError("lexoffice darf für einen Beleg ohne Nummer nicht angefragt werden")
        monkeypatch.setattr("app.api.v1.integrations.LexofficeConnector", kein_netz)
        r = client.put("/api/v1/integrations/lexoffice", json={"api_key": "test-key"})
        assert r.status_code == 200, r.text
        kunde = _q1_kunde(client)
        entwurf = _q1_entwurf(client, kunde)
        verworfen = _q1_entwurf(client, kunde)
        r = client.post(f"/api/v1/invoices/{verworfen['id']}/cancel",
                        json={"reason": "verworfen", "create_credit_note": False})
        assert r.status_code == 200, r.text  # STORNIERT, trägt weiter den Platzhalter

        for beleg in (entwurf, verworfen):
            for pfad in ("", "/pull-status"):
                r = client.post(f"/api/v1/integrations/lexoffice/invoices/{beleg['id']}{pfad}")
                assert r.status_code == 409, (pfad, r.text)
        assert client.get(f"/api/v1/invoices/{entwurf['id']}").json()["status"] == "ENTWURF"

    def test_ausgestellte_rechnung_nie_ohne_stornorechnung(self, client):
        """§ 14c UStG: eine ausgestellte Rechnung verschwindet nur mit
        Gegenbeleg. Ohne Stornorechnung verworfen wird nur ein Entwurf."""
        rechnung = _q1_finalisieren(client, _q1_entwurf(client, _q1_kunde(client)))

        r = client.post(f"/api/v1/invoices/{rechnung['id']}/cancel",
                        json={"reason": "verwerfen", "create_credit_note": False})

        assert r.status_code == 400, r.text
        assert "nur mit Stornorechnung" in r.json()["detail"]
        assert client.get(f"/api/v1/invoices/{rechnung['id']}").json()["status"] == "OFFEN"


class TestQ1NebenlaeufigOhneStornorechnung:
    """Mandanten-DB wie in Produktion, siehe TestQ1Nebenlaeufig."""

    def test_storno_ohne_stornorechnung_gegen_finalisieren(self, monkeypatch, tmp_path):
        """'Ohne Stornorechnung verwerfen' gegen ein gleichzeitiges
        Finalisieren: die Rechnung bleibt ausgestellt (OFFEN) — nie
        STORNIERT ohne Gegenbeleg."""
        from app.models.invoice import Invoice
        from app.services.invoice_service import InvoiceService
        registry, Session = _q1_mandanten_db(monkeypatch, tmp_path)
        try:
            [inv_id] = _q1_orm_entwuerfe(Session)
            gesperrt = threading.Event()
            _q1_langsame_nummer(monkeypatch, gesperrt)
            geladen = threading.Barrier(2)

            def finalisieren():
                with Session() as db:
                    inv = db.get(Invoice, inv_id)
                    geladen.wait()
                    InvoiceService(db).festschreiben(inv)
                    db.commit()

            def verwerfen():
                with Session() as db:
                    db.get(Invoice, inv_id)          # sieht den Entwurf
                    geladen.wait()
                    assert gesperrt.wait(5)
                    InvoiceService(db).cancel_invoice(inv_id, "verwerfen", create_credit_note=False)
                    db.commit()

            fehler = _q1_gleichzeitig(("finalisieren", finalisieren), ("verwerfen", verwerfen))

            with Session() as db:
                inv = db.get(Invoice, inv_id)
                assert (inv.invoice_number, inv.status.value) == (_q1_nr(1), "OFFEN")
            assert [(n, "nur mit Stornorechnung" in e) for n, e in fehler] == [("verwerfen", True)]
        finally:
            registry.dispose_tenant("q1test")


def _q1_api_auf(monkeypatch, Session):
    """Lenkt die API (client) für diesen Test auf die Mandanten-DB."""
    from app.api.deps import _tenant_db
    from app.database import get_db
    from app.main import app

    def db_dep():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setitem(app.dependency_overrides, _tenant_db, db_dep)
    monkeypatch.setitem(app.dependency_overrides, get_db, db_dep)


class TestQ1SammellaufUndVerwerfen:
    """Der Sammellauf legt Entwürfe an; ein Entwurf ohne Nummer lässt sich
    verwerfen, ohne eine Lücke zu reißen."""

    def test_sammellauf_legt_entwuerfe_an(self, client):
        _q1_bestellung_mit_lieferschein(client, _q1_kunde(client))

        rechnung = _q1_lauf(client)["rechnungen"][0]

        assert rechnung["status"] == "ENTWURF"
        assert _Q1_PLATZHALTER.match(rechnung["invoice_number"])
        # die Lieferscheine sind reserviert: der nächste Lauf ist leer
        assert _q1_lauf(client, "preview")["kunden"] == []
        assert _q1_finalisieren(client, rechnung)["invoice_number"] == _q1_nr(1)

    def test_entwurf_loeschen_erzeugt_keine_luecke(self, client):
        kunde = _q1_kunde(client)
        a, b, c = (_q1_entwurf(client, kunde) for _ in range(3))

        r = client.delete(f"/api/v1/invoices/{b['id']}")

        assert r.status_code == 204, r.text
        assert client.get(f"/api/v1/invoices/{b['id']}").status_code == 404
        nummern = [_q1_finalisieren(client, x)["invoice_number"] for x in (a, c)]
        assert nummern == [_q1_nr(1), _q1_nr(2)]

    def test_verworfener_sammelentwurf_gibt_lieferscheine_frei(self, client):
        _, ls = _q1_bestellung_mit_lieferschein(client, _q1_kunde(client))
        rechnung = _q1_lauf(client)["rechnungen"][0]

        assert client.delete(f"/api/v1/invoices/{rechnung['id']}").status_code == 204

        assert [k["anzahl_lieferscheine"] for k in _q1_lauf(client, "preview")["kunden"]] == [1]
        neu = _q1_lauf(client)["rechnungen"][0]
        r = client.get(f"/api/v1/invoices/{neu['id']}/delivery-notes")
        assert [n["delivery_note_number"] for n in r.json()] == [ls["delivery_note_number"]]

    def test_verwerfen_nur_fuer_entwuerfe_ohne_nummer(self, client):
        kunde = _q1_kunde(client)
        rechnung = _q1_finalisieren(client, _q1_entwurf(client, kunde))
        alt_id = _q1_altentwurf(kunde, _q1_nr(7))

        assert client.delete(f"/api/v1/invoices/{rechnung['id']}").status_code == 409
        r = client.delete(f"/api/v1/invoices/{alt_id}")
        assert r.status_code == 409, r.text
        assert _q1_nr(7) in r.json()["detail"]
        assert client.get(f"/api/v1/invoices/{alt_id}").json()["status"] == "ENTWURF"


class TestQ1VerwerfenAufMandantenDb:
    """Mandanten-DB wie in Produktion (Fremdschlüssel an, WAL), siehe
    TestQ1Nebenlaeufig."""

    def test_verwerfen_mit_fremdschluesseln(self, client, monkeypatch, tmp_path):
        registry, Session = _q1_mandanten_db(monkeypatch, tmp_path)
        try:
            _q1_api_auf(monkeypatch, Session)
            _q1_bestellung_mit_lieferschein(client, _q1_kunde(client))
            rechnung = _q1_lauf(client)["rechnungen"][0]

            r = client.delete(f"/api/v1/invoices/{rechnung['id']}")

            assert r.status_code == 204, r.text
            assert [k["anzahl_lieferscheine"] for k in _q1_lauf(client, "preview")["kunden"]] == [1]
        finally:
            registry.dispose_tenant("q1test")

    def test_verwerfen_gegen_finalisieren(self, monkeypatch, tmp_path):
        """DELETE läuft gegen ein gleichzeitiges Finalisieren: die eben
        ausgestellte Rechnung bleibt, ihre Nummer wird nie doppelt vergeben."""
        from app.models.invoice import Invoice
        from app.services.invoice_service import InvoiceService
        registry, Session = _q1_mandanten_db(monkeypatch, tmp_path)
        try:
            [inv_id] = _q1_orm_entwuerfe(Session)
            gesperrt = threading.Event()
            _q1_langsame_nummer(monkeypatch, gesperrt)
            geladen = threading.Barrier(2)

            def finalisieren():
                with Session() as db:
                    inv = db.get(Invoice, inv_id)
                    geladen.wait()
                    InvoiceService(db).festschreiben(inv)
                    db.commit()

            def verwerfen():
                with Session() as db:
                    inv = db.get(Invoice, inv_id)    # noch ENTWURF mit Platzhalter
                    geladen.wait()
                    assert gesperrt.wait(5)
                    InvoiceService(db).entwurf_verwerfen(inv)
                    db.commit()

            fehler = _q1_gleichzeitig(("finalisieren", finalisieren), ("verwerfen", verwerfen))

            with Session() as db:
                inv = db.get(Invoice, inv_id)
                assert inv is not None, "die eben ausgestellte Rechnung wurde gelöscht"
                assert (inv.invoice_number, inv.status.value) == (_q1_nr(1), "OFFEN")
            assert [(n, "Nur Entwürfe können verworfen werden" in e) for n, e in fehler] == [("verwerfen", True)]
        finally:
            registry.dispose_tenant("q1test")

    def test_doppelter_sammellauf(self, client, monkeypatch, tmp_path):
        """Zwei gleichzeitige Läufe (zwei Tabs) über dieselben Lieferscheine:
        genau ein Entwurf, der zweite Lauf meldet 409 und legt nichts an."""
        from sqlalchemy import select
        from app.api.v1 import invoices as inv_api
        from app.models.invoice import Invoice
        registry, Session = _q1_mandanten_db(monkeypatch, tmp_path)
        try:
            _q1_api_auf(monkeypatch, Session)
            _, ls = _q1_bestellung_mit_lieferschein(client, _q1_kunde(client))
            original = inv_api._abrechenbare_lieferscheine
            gelesen = threading.Barrier(2)

            def beide_lesen_zuerst(db, anfrage):
                ergebnis = original(db, anfrage)
                gelesen.wait(timeout=10)  # beide Läufe haben gelesen, keiner geschrieben
                return ergebnis

            monkeypatch.setattr(inv_api, "_abrechenbare_lieferscheine", beide_lesen_zuerst)
            anfrage = inv_api.BatchRunRequest(period_from=date(2026, 3, 1), period_to=date(2026, 3, 31))

            def lauf():
                with Session() as db:
                    inv_api.batch_run_commit(anfrage, db)

            fehler = _q1_gleichzeitig(("A", lauf), ("B", lauf))

            with Session() as db:
                entwuerfe = db.execute(select(Invoice.id)).scalars().all()
            assert len(entwuerfe) == 1, entwuerfe
            assert len(fehler) == 1 and "409" in fehler[0][1], fehler
            r = client.get(f"/api/v1/invoices/{entwuerfe[0]}/delivery-notes")
            assert [n["delivery_note_number"] for n in r.json()] == [ls["delivery_note_number"]]
        finally:
            registry.dispose_tenant("q1test")


class TestQ1Entwurfsbeleg:
    """Was ein Entwurf darf: Vorschau-PDF mit Wasserzeichen ja, DATEV nie."""

    def test_entwurf_pdf_mit_wasserzeichen_ohne_nummer(self, client):
        entwurf = _q1_entwurf(client, _q1_kunde(client))

        r = client.get(f"/api/v1/invoices/{entwurf['id']}/pdf")

        assert r.status_code == 200, r.text
        text = _pdf_text(r.content)
        assert b"(ENTWURF) Tj" in text
        assert entwurf["invoice_number"].encode() not in text
        assert b"Rechnung Nr." not in text

    def test_verworfener_entwurf_bleibt_vorschau(self, client):
        """Ohne Stornorechnung verworfen: STORNIERT, aber weiter ohne Nummer —
        das PDF bleibt eine Vorschau mit Wasserzeichen."""
        entwurf = _q1_entwurf(client, _q1_kunde(client))
        r = client.post(f"/api/v1/invoices/{entwurf['id']}/cancel",
                        json={"reason": "verworfen", "create_credit_note": False})
        assert r.status_code == 200, r.text

        text = _pdf_text(client.get(f"/api/v1/invoices/{entwurf['id']}/pdf").content)

        assert b"(ENTWURF) Tj" in text
        assert entwurf["invoice_number"].encode() not in text

    def test_finalisierte_rechnung_ohne_wasserzeichen(self, client):
        rechnung = _q1_finalisieren(client, _q1_entwurf(client, _q1_kunde(client)))

        text = _pdf_text(client.get(f"/api/v1/invoices/{rechnung['id']}/pdf").content)

        assert b"ENTWURF" not in text
        assert f"Rechnung Nr. {_q1_nr(1)}".encode() in text

    def test_gemailtes_pdf_ohne_wasserzeichen(self, client, monkeypatch):
        entwurf = _q1_entwurf(client, _q1_kunde(client))
        gesendet = _q1_mailversand(monkeypatch)

        r = client.post(f"/api/v1/invoices/{entwurf['id']}/send",
                        params={"to_email": "einkauf@oekoring.example"})

        assert r.status_code == 200, r.text
        assert b"ENTWURF" not in _pdf_text(gesendet["attachment_bytes"])

    def test_datev_exportiert_nie_einen_beleg_ohne_nummer(self, client):
        from app.models.invoice import Invoice, InvoiceStatus
        kunde = _q1_kunde(client)
        _q1_entwurf(client, kunde)
        verworfen = _q1_entwurf(client, kunde)
        r = client.post(f"/api/v1/invoices/{verworfen['id']}/cancel",
                        json={"reason": "verworfen", "create_credit_note": False})
        assert r.status_code == 200, r.text
        # Schutz auch gegen einen Platzhalter außerhalb von ENTWURF (Altlast, Fehler)
        kaputt = _q1_entwurf(client, kunde)
        with TestingSessionLocal() as db:
            db.get(Invoice, uuid.UUID(kaputt["id"])).status = InvoiceStatus.OFFEN
            db.commit()
        rechnung = _q1_finalisieren(client, _q1_entwurf(client, kunde))

        # Zeitraum = Rechnungsdatum beim Festschreiben (Berlin), nicht date.today()
        heute = _q1_heute().isoformat()
        r = client.post("/api/v1/invoices/datev-export", json={
            "from_date": heute, "to_date": heute, "include_payments": False,
        })

        assert r.status_code == 200, r.text
        assert "ENTWURF-" not in r.json()["csv_content"]
        assert rechnung["invoice_number"] in r.json()["csv_content"]


class TestQ1Meldungen:
    """Meldungen nennen einen Entwurf nie mit Platzhalter und raten bei
    einem Entwurf nicht zum Storno (der wäre 400)."""

    def _bestellung_mit_entwurf(self, client):
        bestellung, _ = _q1_bestellung_mit_lieferschein(client, _q1_kunde(client))
        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")
        assert r.status_code == 201, r.text
        return bestellung, r.json()

    def test_zweite_rechnung_zu_einem_entwurf(self, client):
        bestellung, entwurf = self._bestellung_mit_entwurf(client)

        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")

        assert r.status_code == 409, r.text
        detail = r.json()["detail"]
        assert "Rechnungsentwurf (noch ohne Nummer)" in detail
        assert "verwerfen" in detail
        assert "ENTWURF-" not in detail and "stornieren" not in detail

    def test_storno_der_bestellung_nennt_den_entwurf(self, client):
        bestellung, _ = self._bestellung_mit_entwurf(client)

        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/status",
                        json={"status": "STORNIERT", "reason": "entfällt"})

        assert r.status_code == 400, r.text
        detail = r.json()["detail"]
        assert "erst den Entwurf verwerfen" in detail
        assert "ENTWURF-" not in detail

    def test_altentwurf_mit_seiner_nummer(self, client):
        from app.models.invoice import Invoice
        bestellung, entwurf = self._bestellung_mit_entwurf(client)
        with TestingSessionLocal() as db:
            db.get(Invoice, uuid.UUID(entwurf["id"])).invoice_number = _q1_nr(9)
            db.commit()

        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")

        assert r.status_code == 409, r.text
        assert f"Rechnungsentwurf {_q1_nr(9)}" in r.json()["detail"]

    def test_ausgestellte_rechnung_wie_bisher(self, client):
        """Charakterisierung: eine finalisierte Rechnung wird weiter mit
        Nummer genannt, Korrektur über Storno."""
        bestellung, entwurf = self._bestellung_mit_entwurf(client)
        rechnung = _q1_finalisieren(client, entwurf)

        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")

        assert r.status_code == 409, r.text
        assert rechnung["invoice_number"] in r.json()["detail"]
        assert "stornieren" in r.json()["detail"]


class TestQ1MeldungenPositionssperre:
    """Paket 2.1 (30765e5/30135b4) sperrt Positionen und Löschen einer
    berechneten Bestellung mit „Bestellung ist bereits berechnet (Nr.)“.
    Steckt sie in einem Entwurf ohne Nummer, nennt die Meldung ihn ohne
    Platzhalter (Q1, Entscheidung 10)."""

    def test_positionssperre_nennt_entwurf_ohne_platzhalter(self, client):
        bestellung, _ = _q1_bestellung_mit_lieferschein(client, _q1_kunde(client))
        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")
        assert r.status_code == 201, r.text
        assert _Q1_PLATZHALTER.match(r.json()["invoice_number"])

        zeile = bestellung["lines"][0]["id"]
        r = client.patch(f"/api/v1/sales/orders/{bestellung['id']}/lines/{zeile}", json={"quantity": 9})

        assert r.status_code == 409, r.text
        assert "Rechnungsentwurf ohne Nummer" in r.json()["detail"]
        assert "ENTWURF-" not in r.json()["detail"]

    def test_bestellantwort_traegt_den_platzhalter_fuer_die_oberflaeche(self, client):
        """Die API liefert rechnung_nummer roh; die Oberfläche zeigt ihn über
        rechnungsnummerAnzeige (Q1.7)."""
        bestellung, _ = _q1_bestellung_mit_lieferschein(client, _q1_kunde(client))
        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")
        assert r.status_code == 201, r.text

        nummer = client.get(f"/api/v1/sales/orders/{bestellung['id']}").json()["rechnung_nummer"]

        assert _Q1_PLATZHALTER.match(nummer)
