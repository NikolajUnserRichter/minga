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


class TestQ1EmpfaengerFestgeschrieben:
    """GoBD: eine ausgestellte Rechnung ändert sich nicht, wenn sich Kunde
    oder Bestellung ändern. Das PDF entsteht bei jedem Abruf neu — es liest
    den beim Festschreiben eingefrorenen Stand. Gemessen vorher: die Rolle
    production_staff bekam auf das PDF 403, änderte per PATCH
    /sales/customers/{id} aber Name und USt-IdNr., die das PDF einer
    ausgestellten Rechnung danach zeigte."""

    _VORHER = {"customer_number": "K-Q1-001", "ust_id": "DE111111111",
               "adresse": "Altweg 1, 80331 Muenchen", "skonto_percent": "2", "skonto_days": 10}
    _NACHHER = {"name": "Umbenannt GmbH", "customer_number": "K-Q1-999", "ust_id": "DE999999999",
                "adresse": "Neuweg 9, 10115 Berlin", "skonto_percent": "5", "skonto_days": 20}

    def _pdf(self, client, rechnung):
        r = client.get(f"/api/v1/invoices/{rechnung['id']}/pdf")
        assert r.status_code == 200, r.text
        return _pdf_text(r.content)

    def test_kundenaenderung_aendert_ausgestellte_rechnung_nicht(self, client):
        kunde = _q1_kunde(client, "Bodan Naturkost GmbH", **self._VORHER)
        rechnung = _q1_finalisieren(client, _q1_entwurf(client, kunde))

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json=self._NACHHER)
        assert r.status_code == 200, r.text
        text = self._pdf(client, rechnung)

        for alt in (b"Bodan Naturkost GmbH", b"K-Q1-001", b"DE111111111", b"Altweg 1", b"2.0% Skonto"):
            assert alt in text, alt
        for neu in (b"Umbenannt", b"K-Q1-999", b"DE999999999", b"Neuweg", b"5.0% Skonto"):
            assert neu not in text, neu

    def test_auftragsnummer_bleibt(self, client):
        from app.models.order import Order
        bestellung, _ = _q1_bestellung_mit_lieferschein(client, _q1_kunde(client))
        with TestingSessionLocal() as db:
            db.get(Order, uuid.UUID(bestellung["id"])).customer_reference = "EB-ALT-1"
            db.commit()
        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")
        assert r.status_code == 201, r.text
        rechnung = _q1_finalisieren(client, r.json())
        with TestingSessionLocal() as db:
            db.get(Order, uuid.UUID(bestellung["id"])).customer_reference = "EB-NEU-2"
            db.commit()

        text = self._pdf(client, rechnung)

        assert b"EB-ALT-1" in text and b"EB-NEU-2" not in text

    def test_entwurf_zeigt_den_aktuellen_kunden(self, client):
        """Die Vorschau eines Entwurfs folgt dem Kunden bis zum Festschreiben."""
        kunde = _q1_kunde(client, "Bodan Naturkost GmbH", **self._VORHER)
        entwurf = _q1_entwurf(client, kunde)

        assert client.patch(f"/api/v1/sales/customers/{kunde['id']}", json=self._NACHHER).status_code == 200
        text = self._pdf(client, entwurf)

        assert b"Umbenannt GmbH" in text and b"DE999999999" in text

    def test_snapshot_steht_an_der_rechnung(self, client):
        kunde = _q1_kunde(client, "Bodan Naturkost GmbH", **self._VORHER)
        rechnung = _q1_finalisieren(client, _q1_entwurf(client, kunde))

        snapshot = client.get(f"/api/v1/invoices/{rechnung['id']}").json()["billing_address"]

        assert snapshot["festgeschrieben"] is True
        assert (snapshot["name"], snapshot["ust_id"], snapshot["skonto_days"]) == (
            "Bodan Naturkost GmbH", "DE111111111", 10)


# =====================================================================
# Q4 — Mitarbeiterrechte (B8-Kern): Halle liest Produkte, Rechnungen
#      nur mit Rechnungsrecht, Feldschutz für Konditionen und Empfänger,
#      Mandantenpflicht, Empfänger auf der Rechnung eingefroren.
#      Spec 08.10.2026 Entscheidung 6, T3 R4, T5 R1/R2/R3/3.3.
# =====================================================================
from datetime import date as _q4_date, timedelta as _q4_timedelta
from decimal import Decimal

import pytest

from app.api.deps import get_current_user
from app.main import app

_Q4_USER_ID = "123e4567-e89b-12d3-a456-426614174000"
_Q4_FREMD = "00000000-0000-0000-0000-0000000000ff"
# Rollen der Demo-Logins (platform.py DEMO_USERS: anna, ben, clara, paul).
_Q4_DEMO_ROLLEN = ["admin", "sales", "accounting", "production_planner"]
_Q4_OHNE_RECHNUNGSRECHT = ["production_staff", "production_planner"]
_Q4_MIT_RECHNUNGSRECHT = ["admin", "sales", "accounting"]


def _q4_als(*rollen):
    """Login mit genau diesen Rollen (Muster tests/test_rollen.py::_als).
    Das client-Fixture entfernt die Überschreibung beim Aufräumen."""
    async def override():
        return {"id": _Q4_USER_ID, "username": "q4", "email": "q4@example.com",
                "roles": list(rollen)}
    app.dependency_overrides[get_current_user] = override


def _q4_verwaltung():
    """Zurück auf das Standard-Login des client-Fixtures (conftest.py)."""
    _q4_als("admin", "production_planner")


def _q4_einheit():
    from app.models.unit import UnitOfMeasure, UnitCategory
    from tests.conftest import TestingSessionLocal
    with TestingSessionLocal() as db:
        unit = db.query(UnitOfMeasure).filter_by(code="STK").first()
        if unit is None:
            unit = UnitOfMeasure(code="STK", name="Stück", symbol="Stk",
                                 category=UnitCategory.COUNT, is_base_unit=True)
            db.add(unit)
            db.commit()
        return str(unit.id)


def _q4_produkt(client, sku="KRESSE-50", name="Kresse 50 g", preis="2.50"):
    r = client.post("/api/v1/products", json={
        "sku": sku, "name": name, "base_price": preis,
        "category": "MICROGREEN", "base_unit_id": _q4_einheit(),
    })
    assert r.status_code == 201, r.text
    return r.json()


def _q4_kunde(client, **felder):
    r = client.post("/api/v1/sales/customers", json={
        "name": "Ökoring", "typ": "HANDEL", "email": "einkauf@oekoring.de", **felder})
    assert r.status_code == 201, r.text
    return r.json()


def _q4_bestellung(client, kunde, produkt):
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"],
        "requested_delivery_date": (_q4_date.today() + _q4_timedelta(days=3)).isoformat(),
        "lines": [{"product_id": produkt["id"], "product_name": produkt["name"],
                   "quantity": 3, "unit": "STK", "unit_price": "2.50"}],
    })
    return r


def _q4_kunde_db(kunde_id):
    from uuid import UUID
    from app.models.customer import Customer
    from tests.conftest import TestingSessionLocal
    with TestingSessionLocal() as db:
        k = db.get(Customer, UUID(kunde_id))
        return {"name": k.name, "email": k.email, "discount_percent": k.discount_percent,
                "pfand_abrechnung": k.pfand_abrechnung.value, "payment_terms": k.payment_terms.value}


def _q4_kundenformular(kunde, **aenderungen):
    """Was Customers.tsx (CustomerForm.handleSubmit) beim Speichern schickt:
    alle Formularfelder, Prozente als Zahl."""
    daten = {
        "name": kunde["name"], "typ": kunde["typ"], "customer_number": kunde["customer_number"],
        "email": kunde["email"], "telefon": "", "adresse": "", "ust_id": "",
        "liefertage": [1, 3], "payment_terms": kunde["payment_terms"],
        "discount_percent": float(kunde["discount_percent"]),
        "skonto_percent": float(kunde["skonto_percent"]),
        "skonto_days": kunde["skonto_days"],
        "packaging_fee_amount": float(kunde["packaging_fee_amount"]),
        "packaging_fee_percent": float(kunde["packaging_fee_percent"]),
        "show_prices_on_delivery_note": kunde["show_prices_on_delivery_note"],
        "aktiv": kunde["aktiv"], "pfand_abrechnung": kunde["pfand_abrechnung"],
    }
    daten.update(aenderungen)
    return daten


class TestQ4HalleLiestProdukte:
    """R1: Das Bestellformular lädt GET /products (CreateOrderModal, EditOrderModal).
    Für production_staff war das 403 — das Formular zeigte Saatgut statt Produkte."""

    def test_halle_liest_produktliste_und_varianten(self, client):
        produkt = _q4_produkt(client)
        _q4_als("production_staff")

        liste = client.get("/api/v1/products", params={"is_active": True, "page_size": 500})
        varianten = client.get(f"/api/v1/products/{produkt['id']}/variants")
        einzeln = client.get(f"/api/v1/products/{produkt['id']}")

        assert liste.status_code == 200, liste.text
        assert [p["id"] for p in liste.json()] == [produkt["id"]]
        assert varianten.status_code == 200, varianten.text
        assert einzeln.status_code == 200, einzeln.text

    def test_halle_legt_bestellung_mit_produkt_aus_der_liste_an(self, client):
        """Der ganze Weg aus dem Formular: Liste lesen, Produkt wählen, speichern."""
        _q4_produkt(client)
        kunde = _q4_kunde(client)
        _q4_als("production_staff")
        produkt = client.get("/api/v1/products", params={"is_active": True}).json()[0]

        r = _q4_bestellung(client, kunde, produkt)

        assert r.status_code == 201, r.text
        assert r.json()["lines"][0]["product_id"] == produkt["id"]

    @pytest.mark.parametrize("methode,pfad", [
        ("POST", "/api/v1/products"),
        ("PATCH", f"/api/v1/products/{_Q4_FREMD}"),
        ("DELETE", f"/api/v1/products/{_Q4_FREMD}"),
        ("POST", f"/api/v1/products/{_Q4_FREMD}/variants"),
    ])
    def test_halle_pflegt_den_katalog_nicht(self, client, methode, pfad):
        _q4_als("production_staff")
        assert client.request(methode, pfad, json={}).status_code == 403

    @pytest.mark.parametrize("pfad", ["/api/v1/product-groups", "/api/v1/grow-plans", "/api/v1/price-lists"])
    def test_gruppen_wachstumsplaene_preislisten_bleiben_gesperrt(self, client, pfad):
        """Nur der Produktrouter wird geöffnet — das Formular braucht nicht mehr."""
        _q4_als("production_staff")
        assert client.get(pfad).status_code == 403

    @pytest.mark.parametrize("rolle", _Q4_DEMO_ROLLEN)
    def test_demo_rollen_unveraendert(self, client, rolle):
        _q4_als(rolle)
        assert client.get("/api/v1/products").status_code == 200
        darf_schreiben = client.post("/api/v1/products", json={}).status_code
        assert darf_schreiben != 403, f"{rolle} pflegt Produkte weiter (422 auf leeren Body)"

    def test_saatgut_id_als_produkt_endet_mit_404(self, client, sample_seed):
        """Charakterisierung (bleibt grün): So endete das Speichern mit dem Saatgut-Ersatz
        des Formulars — die Saatgut-ID ging als product_id an create_order."""
        kunde = _q4_kunde(client)
        _q4_als("production_staff")

        r = client.post("/api/v1/sales/orders", json={
            "customer_id": kunde["id"],
            "requested_delivery_date": (_q4_date.today() + _q4_timedelta(days=3)).isoformat(),
            "lines": [{"product_id": sample_seed["id"], "product_name": sample_seed["name"],
                       "quantity": 1, "unit": "g", "unit_price": "10"}],
        })

        assert r.status_code == 404
        assert "nicht gefunden" in r.json()["detail"]


class TestQ4RechnungenNurMitRechnungsrecht:
    """R3 serverseitig — Charakterisierung (von Anfang an grün): Der Belege-Dialog
    blendet den Rechnungsteil aus, der Server bleibt trotzdem zu (_deps_geld)."""

    @pytest.mark.parametrize("rolle", _Q4_OHNE_RECHNUNGSRECHT)
    @pytest.mark.parametrize("methode,pfad", [
        ("GET", f"/api/v1/invoices?order_id={_Q4_FREMD}"),
        ("POST", f"/api/v1/invoices/from-order/{_Q4_FREMD}"),
        ("POST", f"/api/v1/invoices/{_Q4_FREMD}/finalize"),
        ("POST", f"/api/v1/invoices/{_Q4_FREMD}/send?to_email=a%40b.de"),
        ("GET", f"/api/v1/invoices/{_Q4_FREMD}/pdf"),
    ])
    def test_ohne_rechnungsrecht_403(self, client, rolle, methode, pfad):
        _q4_als(rolle)
        assert client.request(methode, pfad).status_code == 403

    @pytest.mark.parametrize("rolle", _Q4_MIT_RECHNUNGSRECHT)
    def test_mit_rechnungsrecht_offen(self, client, rolle):
        _q4_als(rolle)
        r = client.get("/api/v1/invoices", params={"order_id": _Q4_FREMD})
        assert r.status_code == 200, r.text


class TestQ4Kundenfeldschutz:
    """Spec Entscheidung 6 / T3 R4 / T5 R2: Die Halle legt Kunden an und pflegt
    Stammdaten (Gernot, 03.09.). Konditionen ändern nur Verwaltung, Vertrieb und
    Buchhaltung. Der Schutz greift nur bei einer echten Änderung — das Formular
    schickt alle Felder."""

    @pytest.mark.parametrize("feld,wert", [
        ("pfand_abrechnung", "KEINE"),
        ("discount_percent", 5),
        ("payment_terms", "NET_30"),
        ("credit_limit", 500),
        ("skonto_percent", 2),
        ("skonto_days", 10),
        ("packaging_fee_amount", 4.5),
        ("packaging_fee_percent", 1),
        ("datev_account", "10077"),
    ])
    def test_halle_aendert_kein_abrechnungsfeld(self, client, feld, wert):
        from app.core.rollen import KUNDENFELDER_KAUFMAENNISCH
        kunde = _q4_kunde(client)
        _q4_als("production_staff")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={feld: wert})

        assert r.status_code == 403, r.text
        assert KUNDENFELDER_KAUFMAENNISCH[feld] in r.json()["detail"]
        _q4_verwaltung()
        assert client.get(f"/api/v1/sales/customers/{kunde['id']}").json()[feld] == kunde[feld]

    def test_halle_aendert_keine_preisliste(self, client):
        from app.models.product import PriceList
        from tests.conftest import TestingSessionLocal
        with TestingSessionLocal() as db:
            liste = PriceList(name="Gastro 2026", code="GASTRO26")
            db.add(liste)
            db.commit()
            liste_id = str(liste.id)
        kunde = _q4_kunde(client)
        _q4_als("production_staff")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"price_list_id": liste_id})

        assert r.status_code == 403, r.text

    def test_abgelehnte_aenderung_schreibt_auch_die_freien_felder_nicht(self, client):
        kunde = _q4_kunde(client)
        _q4_als("production_staff")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}",
                         json={"name": "Ökoring eG", "discount_percent": 7})

        assert r.status_code == 403
        assert _q4_kunde_db(kunde["id"])["name"] == "Ökoring"

    def test_volles_formular_mit_unveraenderten_konditionen_geht_durch(self, client):
        """Gespeicherte Werte 5.00 % / NET_30 / KEINE, das Formular schickt 5 / NET_30 / KEINE
        und die unveränderte E-Mail."""
        kunde = _q4_kunde(client, discount_percent="5.00", payment_terms="NET_30",
                          pfand_abrechnung="KEINE", skonto_percent="2.5", skonto_days=10)
        _q4_als("production_staff")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}",
                         json=_q4_kundenformular(kunde, name="Ökoring eG", telefon="089 123"))

        assert r.status_code == 200, r.text
        stand = _q4_kunde_db(kunde["id"])
        assert stand["name"] == "Ökoring eG"
        assert stand["pfand_abrechnung"] == "KEINE"
        assert stand["payment_terms"] == "NET_30"

    def test_volles_formular_mit_geaendertem_rabatt_wird_abgelehnt(self, client):
        kunde = _q4_kunde(client, discount_percent="5.00")
        _q4_als("production_staff")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}",
                         json=_q4_kundenformular(kunde, discount_percent=7.5))

        assert r.status_code == 403, r.text
        assert ": Jahresrabatt %." in r.json()["detail"]

    def test_veraltetes_formular_nennt_neu_laden(self, client):
        """Die Halle öffnet das Formular, danach ändert die Verwaltung den Rabatt.
        Die Halle speichert nur eine neue Telefonnummer (Befund H4)."""
        kunde = _q4_kunde(client, discount_percent="5.00")
        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"discount_percent": 6})
        assert r.status_code == 200, r.text
        _q4_als("production_staff")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}",
                         json=_q4_kundenformular(kunde, telefon="089 123"))

        assert r.status_code == 403, r.text
        assert "Formular veraltet" in r.json()["detail"]
        assert _q4_kunde_db(kunde["id"])["discount_percent"] == Decimal("6.00")

    def test_halle_legt_kunden_mit_standardkonditionen_an(self, client):
        """Neuanlage aus dem Formular: alle Konditionen auf Standard, E-Mail gesetzt —
        erlaubt (Gernot, 03.09.)."""
        _q4_als("production_staff")

        r = client.post("/api/v1/sales/customers", json={
            "name": "Fruchthof Nagel", "typ": "HANDEL", "customer_number": "",
            "email": "info@fruchthof-nagel.de",
            "liefertage": [2], "payment_terms": "NET_14", "discount_percent": 0,
            "skonto_percent": 0, "skonto_days": 0, "packaging_fee_amount": 0,
            "packaging_fee_percent": 0, "show_prices_on_delivery_note": False,
            "aktiv": True, "pfand_abrechnung": "JE_LIEFERUNG",
        })

        assert r.status_code == 201, r.text
        assert r.json()["pfand_abrechnung"] == "JE_LIEFERUNG"
        assert r.json()["email"] == "info@fruchthof-nagel.de"

    @pytest.mark.parametrize("feld,wert", [
        ("pfand_abrechnung", "KEINE"),
        ("discount_percent", 3),
        ("payment_terms", "NET_30"),
    ])
    def test_halle_legt_keinen_kunden_mit_abweichender_kondition_an(self, client, feld, wert):
        _q4_als("production_staff")

        r = client.post("/api/v1/sales/customers",
                        json={"name": "Großer Kern", "typ": "GASTRO", feld: wert})

        assert r.status_code == 403, r.text
        _q4_verwaltung()
        assert client.get("/api/v1/sales/customers", params={"search": "Großer Kern"}).json()["total"] == 0

    @pytest.mark.parametrize("rolle", _Q4_MIT_RECHNUNGSRECHT)
    def test_kaufmaennische_rollen_aendern_konditionen(self, client, rolle):
        kunde = _q4_kunde(client)
        _q4_als(rolle)

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}",
                         json={"pfand_abrechnung": "KEINE", "discount_percent": 5})

        assert r.status_code == 200, r.text
        assert r.json()["pfand_abrechnung"] == "KEINE"

    def test_planung_aendert_keine_konditionen(self, client):
        """Spec 08.10., Abnahme Paket 1: 'production_planner/production_staff können
        pfand_abrechnung setzen' — offen für Paket 3. T3 R4: nur Admin, Vertrieb,
        Buchhaltung."""
        kunde = _q4_kunde(client)
        _q4_als("production_planner")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"pfand_abrechnung": "KEINE"})

        assert r.status_code == 403, r.text
        assert "Pfandabrechnung" in r.json()["detail"]

    def test_halle_mit_zusaetzlicher_vertriebsrolle_darf(self, client):
        kunde = _q4_kunde(client)
        _q4_als("production_staff", "sales")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"discount_percent": 5})

        assert r.status_code == 200, r.text


class TestQ4EmpfaengerDesKunden:
    """Befund B1: Über die Haupt-E-Mail laufen der Rückfall jeder Empfängerliste
    (Q2: belegversand.hinterlegte_empfaenger), die Vorbelegung des Versanddialogs
    und der Mahnlauf (send_payment_reminders: email_to=customer.email). Ändern nur
    Rollen ohne die Halle (T5 3.3); bei der Neuanlage frei."""

    def test_halle_aendert_keine_haupt_email(self, client):
        kunde = _q4_kunde(client)
        _q4_als("production_staff")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}",
                         json={"email": "angreifer@fremd.example"})

        assert r.status_code == 403, r.text
        assert "E-Mail (Hauptkontakt)" in r.json()["detail"]
        assert _q4_kunde_db(kunde["id"])["email"] == "einkauf@oekoring.de"

    def test_altbestand_email_in_anderer_schreibweise_gilt_als_unveraendert(self, client):
        """EmailStr schreibt die Domain klein. Ein Altbestand mit großer Domain
        darf das Formular der Halle nicht sperren."""
        from uuid import UUID
        from app.models.customer import Customer
        from tests.conftest import TestingSessionLocal
        kunde = _q4_kunde(client)
        with TestingSessionLocal() as db:
            db.get(Customer, UUID(kunde["id"])).email = "Einkauf@OEKORING.de"
            db.commit()
        kunde["email"] = "Einkauf@OEKORING.de"
        _q4_als("production_staff")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}",
                         json=_q4_kundenformular(kunde, telefon="089 1"))

        assert r.status_code == 200, r.text

    def test_planung_pflegt_die_haupt_email(self, client):
        kunde = _q4_kunde(client)
        _q4_als("production_planner")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}",
                         json={"email": "rechnung@oekoring.de"})

        assert r.status_code == 200, r.text

    def test_empfaengerlisten_ohne_die_halle(self, client):
        """Greift erst, wenn der Versand-Abschnitt (Q2.3) die Empfängerlisten am Kunden
        eingeführt hat. Bestandskunden haben dort NULL, das Formular schickt []."""
        from app.schemas.customer import CustomerUpdate
        if "invoice_emails" not in CustomerUpdate.model_fields:
            pytest.skip("Empfängerlisten (Q2.3) noch nicht umgesetzt")
        from uuid import UUID
        from app.models.customer import Customer
        from tests.conftest import TestingSessionLocal
        kunde = _q4_kunde(client)
        with TestingSessionLocal() as db:
            k = db.get(Customer, UUID(kunde["id"]))
            k.confirmation_emails = k.delivery_note_emails = k.invoice_emails = None
            db.commit()
        _q4_als("production_staff")

        unveraendert = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={
            "telefon": "089 1", "confirmation_emails": [], "delivery_note_emails": [],
            "invoice_emails": [],
        })
        geaendert = client.patch(f"/api/v1/sales/customers/{kunde['id']}",
                                 json={"invoice_emails": ["rechnung@oekoring.de"]})

        assert unveraendert.status_code == 200, unveraendert.text
        assert geaendert.status_code == 403, geaendert.text


# Kundenfelder, die die Halle ändern darf (Stammdaten, Gernot 03.09.). Wer ein
# Feld zu CustomerCreate/CustomerUpdate hinzufügt, ordnet es hier oder in
# app.core.rollen (KUNDENFELDER_KAUFMAENNISCH, KUNDENFELDER_EMPFAENGER) ein.
# Name, Kundennummer, USt-IdNr. und Anschrift trägt die festgeschriebene
# Rechnung eingefroren (Q1.6; Altrechnungen Q4.9).
_Q4_FREIE_KUNDENFELDER = {
    "name", "typ", "telefon", "adresse", "liefertage", "customer_number",
    "ansprechpartner_name", "ansprechpartner_email", "ansprechpartner_telefon",
    "ust_id", "steuernummer", "show_prices_on_delivery_note", "notizen", "aktiv",
    "addresses",
}
# Empfängerlisten des Versand-Abschnitts (Q2.3): in KUNDENFELDER_EMPFAENGER
# eingeordnet, bevor es sie gibt — der Wachhund bleibt in jeder Reihenfolge
# von Q2 und Q4 grün.
_Q4_KUENFTIGE_KUNDENFELDER = {"confirmation_emails", "delivery_note_emails", "invoice_emails"}


class TestQ4KundenfelderEingeordnet:
    def test_jedes_kundenfeld_ist_eingeordnet(self):
        """Wachhund: Ein neues Kundenfeld (z. B. invoice_mode, Q7) darf nicht
        ungeprüft für die Halle schreibbar werden."""
        from app.core.rollen import KUNDENFELDER_EMPFAENGER, KUNDENFELDER_KAUFMAENNISCH
        from app.schemas.customer import CustomerCreate, CustomerUpdate

        felder = set(CustomerCreate.model_fields) | set(CustomerUpdate.model_fields)
        kaufmaennisch = set(KUNDENFELDER_KAUFMAENNISCH)
        empfaenger = set(KUNDENFELDER_EMPFAENGER)
        geschuetzt = kaufmaennisch | empfaenger

        assert felder - geschuetzt - _Q4_FREIE_KUNDENFELDER == set()
        assert kaufmaennisch & empfaenger == set()
        assert geschuetzt & _Q4_FREIE_KUNDENFELDER == set()
        unbekannt = geschuetzt - felder - _Q4_KUENFTIGE_KUNDENFELDER
        assert unbekannt == set(), f"Unbekannte Felder im Feldschutz: {sorted(unbekannt)}"


class TestQ4SonderpreiseDatevKatalogpreis:
    """T5 R2, soweit Gernots Entscheidung vom 03.09. (Kunden und Bestellungen
    erfassen) unberührt bleibt: Sonderpreise pflegen alle außer der Halle, den
    DATEV-Debitorenexport ziehen nur Verwaltung, Vertrieb und Buchhaltung.
    Lesen der Sonderpreise bleibt offen (Bestellformular)."""

    def _sonderpreis(self, client):
        produkt = _q4_produkt(client)
        kunde = _q4_kunde(client)
        r = client.post(f"/api/v1/sales/customers/{kunde['id']}/prices",
                        json={"product_id": produkt["id"], "unit_price": "2.20"})
        assert r.status_code == 201, r.text
        return kunde, produkt, r.json()

    def test_halle_pflegt_keine_sonderpreise(self, client):
        kunde, produkt, preis = self._sonderpreis(client)
        _q4_als("production_staff")

        neu = client.post(f"/api/v1/sales/customers/{kunde['id']}/prices",
                          json={"product_id": produkt["id"], "unit_price": "1.00"})
        aendern = client.patch(f"/api/v1/sales/customer-prices/{preis['id']}", json={"unit_price": "1.00"})
        loeschen = client.delete(f"/api/v1/sales/customer-prices/{preis['id']}")

        assert (neu.status_code, aendern.status_code, loeschen.status_code) == (403, 403, 403)
        _q4_verwaltung()
        preise = client.get(f"/api/v1/sales/customers/{kunde['id']}/prices").json()
        assert [Decimal(p["unit_price"]) for p in preise] == [Decimal("2.20")]

    def test_halle_liest_sonderpreis_fuers_bestellformular(self, client):
        kunde, produkt, _ = self._sonderpreis(client)
        _q4_als("production_staff")

        liste = client.get(f"/api/v1/sales/customers/{kunde['id']}/prices")
        wirksam = client.get(f"/api/v1/sales/customers/{kunde['id']}/effective-price/{produkt['id']}")

        assert liste.status_code == 200, liste.text
        assert wirksam.status_code == 200, wirksam.text

    @pytest.mark.parametrize("rolle", _Q4_OHNE_RECHNUNGSRECHT)
    def test_datev_debitorenexport_nur_kaufmaennisch(self, client, rolle):
        """T5 R2: 'nur noch admin, sales und accounting, und zwar schon beim Lesen'."""
        _q4_als(rolle)
        assert client.get("/api/v1/sales/customers/export/datev").status_code == 403

    @pytest.mark.parametrize("rolle", _Q4_MIT_RECHNUNGSRECHT)
    def test_kaufmaennische_rollen_ziehen_den_export(self, client, rolle):
        _q4_als(rolle)
        assert client.get("/api/v1/sales/customers/export/datev").status_code == 200

    @pytest.mark.parametrize("rolle", _Q4_DEMO_ROLLEN)
    def test_demo_rollen_pflegen_sonderpreise_weiter(self, client, rolle):
        _, _, preis = self._sonderpreis(client)
        _q4_als(rolle)

        r = client.patch(f"/api/v1/sales/customer-prices/{preis['id']}", json={"unit_price": "2.10"})

        assert r.status_code == 200, r.text

    def test_halle_liest_keinen_kundenpreis_ueber_den_katalog(self, client):
        """Befund H1: GET /products/{id}/price?customer_id= liest Preislistenpreis und
        Kundenrabatt (ProductService.get_product_price). /price-lists bleibt für die
        Halle zu; das Bestellformular ruft den Endpunkt nicht (productsApi.getPrice)."""
        kunde, produkt, _ = self._sonderpreis(client)
        _q4_als("production_staff")

        r = client.get(f"/api/v1/products/{produkt['id']}/price", params={"customer_id": kunde["id"]})

        assert r.status_code == 403, r.text

    def test_planung_liest_den_katalogpreis_weiter(self, client):
        kunde, produkt, _ = self._sonderpreis(client)
        _q4_als("production_planner")

        r = client.get(f"/api/v1/products/{produkt['id']}/price", params={"customer_id": kunde["id"]})

        assert r.status_code == 200, r.text


class TestQ4DevRollen:
    """Abnahme ohne Keycloak: Im Dev-Modus (AUTH_DISABLED) lässt sich das Login
    auf einzelne Rollen einschränken. Ohne AUTH_DISABLED wirkt DEV_ROLES nicht."""

    def _login(self, monkeypatch, auth_disabled, dev_roles):
        import asyncio
        from types import SimpleNamespace
        from app.api import deps
        monkeypatch.setattr(deps.settings, "auth_disabled", auth_disabled)
        monkeypatch.setattr(deps.settings, "dev_roles", dev_roles)
        # Ohne Basic-Auth-Nutzer und ohne Token — wie ein Browser im Dev-Modus
        anfrage = SimpleNamespace(state=SimpleNamespace())
        return asyncio.run(deps.get_current_user(request=anfrage, token=None))

    def test_ohne_dev_roles_alle_rollen(self, monkeypatch):
        user = self._login(monkeypatch, True, "")
        assert user["roles"] == ["admin", "sales", "production_planner", "production_staff", "accounting"]

    def test_dev_roles_schraenkt_ein(self, monkeypatch):
        user = self._login(monkeypatch, True, " production_staff , ")
        assert user["roles"] == ["production_staff"]

    def test_dev_roles_ohne_auth_disabled_wirkungslos(self, monkeypatch):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as fehler:
            self._login(monkeypatch, False, "admin")
        assert fehler.value.status_code == 401


class TestQ4PositionsrabattImAudit:
    """Befund B3: Den Positionsrabatt übernimmt jede Rechnung aus der Bestellung
    (create_invoice_from_order, Sammellauf _aggregiere). Die Halle setzt ihn per
    API — beim Anlegen und nachträglich, auch nach der Bestätigung. Ob sie das
    darf, ist offen (Frage 4); nachvollziehbar ist es ab Q4.8."""

    def _bestaetigt(self, client):
        produkt = _q4_produkt(client)
        kunde = _q4_kunde(client)
        r = _q4_bestellung(client, kunde, produkt)
        assert r.status_code == 201, r.text
        r = client.post(f"/api/v1/sales/orders/{r.json()['id']}/confirm")
        assert r.status_code == 200, r.text
        return produkt, r.json()

    def _audit(self, client, bestellung, aktion):
        _q4_verwaltung()
        r = client.get(f"/api/v1/sales/orders/{bestellung['id']}/audit-log")
        assert r.status_code == 200, r.text
        eintraege = [e for e in r.json() if e["action"] == aktion]
        assert len(eintraege) == 1, eintraege
        return eintraege[0]

    def test_rabatt_aenderung_steht_im_audit(self, client):
        _, bestellung = self._bestaetigt(client)
        _q4_als("production_staff")

        r = client.patch(f"/api/v1/sales/orders/{bestellung['id']}/lines/{bestellung['lines'][0]['id']}",
                         json={"discount_percent": 50})

        assert r.status_code == 200, r.text  # erlaubt, offen: Frage 4
        eintrag = self._audit(client, bestellung, "UPDATE_LINE")
        assert Decimal(eintrag["old_values"]["discount_percent"]) == 0
        assert Decimal(eintrag["new_values"]["discount_percent"]) == 50

    def test_neue_position_mit_rabatt_steht_im_audit(self, client):
        produkt, bestellung = self._bestaetigt(client)
        _q4_als("production_staff")

        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/lines", json={
            "product_id": produkt["id"], "product_name": produkt["name"], "quantity": 1,
            "unit": "STK", "unit_price": "2.50", "discount_percent": 100})

        assert r.status_code == 201, r.text
        eintrag = self._audit(client, bestellung, "ADD_LINE")
        assert Decimal(eintrag["new_values"]["discount_percent"]) == 100


class TestQ4AltrechnungenEingefroren:
    """Befund B2 (GoBD), Rest nach Q1.6: Rechnungen, die vor dem Deploy von
    Paket 3 festgeschrieben wurden, haben keinen Empfänger-Snapshot. Ihr PDF
    folgte weiter dem Kundenstamm, den auch die Halle pflegt. _auto_migrate
    trägt beim Start den heutigen Stand nach (Paket 3, Q4.9)."""

    _VORHER = {"customer_number": "K-Q4-001", "ust_id": "DE111111111",
               "adresse": "Altweg 1, 80331 Muenchen", "skonto_percent": "2", "skonto_days": 10}

    def _altrechnung(self, client):
        """Festgeschrieben wie vor Paket 3: ohne Snapshot (billing_address leer)."""
        from app.models.invoice import Invoice
        kunde = _q1_kunde(client, "Fruchthof Nagel", **self._VORHER)
        rechnung = _q1_finalisieren(client, _q1_entwurf(client, kunde))
        with TestingSessionLocal() as db:
            db.get(Invoice, uuid.UUID(rechnung["id"])).billing_address = None
            db.commit()
        return kunde, rechnung

    def test_start_traegt_snapshot_nach_pdf_folgt_dem_kunden_nicht_mehr(self, client):
        from app.tenancy import _auto_migrate
        from tests.conftest import engine
        kunde, rechnung = self._altrechnung(client)
        entwurf = _q1_entwurf(client, kunde)

        _auto_migrate(engine)
        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}",
                         json={"name": "Fremdfirma GmbH", "ust_id": "DE999999999"})
        assert r.status_code == 200, r.text

        snapshot = client.get(f"/api/v1/invoices/{rechnung['id']}").json()["billing_address"]
        assert (snapshot["festgeschrieben"], snapshot["nachgetragen"], snapshot["name"]) == (
            True, True, "Fruchthof Nagel")
        text = _pdf_text(client.get(f"/api/v1/invoices/{rechnung['id']}/pdf").content)
        assert b"Fruchthof Nagel" in text and b"DE111111111" in text
        assert b"Fremdfirma" not in text and b"DE999999999" not in text
        entwurf_ba = client.get(f"/api/v1/invoices/{entwurf['id']}").json()["billing_address"]
        assert not (entwurf_ba or {}).get("festgeschrieben")

    def test_nachtragen_ist_idempotent_und_laesst_snapshots_stehen(self, client):
        from app.services.invoice_service import empfaenger_nachtragen
        kunde, _ = self._altrechnung(client)
        neu = _q1_finalisieren(client, _q1_entwurf(client, kunde))

        with TestingSessionLocal() as db:
            erster = empfaenger_nachtragen(db)
            db.commit()
        with TestingSessionLocal() as db:
            zweiter = empfaenger_nachtragen(db)

        assert (erster, zweiter) == (1, 0)
        assert "nachgetragen" not in client.get(f"/api/v1/invoices/{neu['id']}").json()["billing_address"]

    def test_verworfener_entwurf_bekommt_keinen_snapshot(self, client):
        """Ohne Stornorechnung verworfen: STORNIERT mit Platzhalter, nie ausgestellt."""
        from app.services.invoice_service import empfaenger_nachtragen
        entwurf = _q1_entwurf(client, _q1_kunde(client))
        r = client.post(f"/api/v1/invoices/{entwurf['id']}/cancel",
                        json={"reason": "Doppelt angelegt", "create_credit_note": False})
        assert r.status_code == 200, r.text

        with TestingSessionLocal() as db:
            assert empfaenger_nachtragen(db) == 0


# ============================================================
# Q3 — Dateinamen der Belege (B7)
#
# Ein Beleg heißt wie seine Nummer: RE-2026-00002.pdf, AB-…pdf, LS-…pdf,
# PL-…pdf. Der Server setzt den Namen (Content-Disposition mit filename und
# filename* nach RFC 6266/5987), das Frontend übernimmt ihn. Ein
# Rechnungsentwurf heißt Entwurf-<…>.pdf.
# ============================================================
# Importe im Abschnitt: doppelte Importe anderer Abschnitte sind harmlos.
import uuid  # noqa: E402
from datetime import date  # noqa: E402

from tests.conftest import TestingSessionLocal  # noqa: E402

# Form des Platzhalters aus Q1 / Spec-Entscheidung 2: "ENTWURF-" + 12 Zeichen
_Q3_PLATZHALTER = "ENTWURF-AB12CD34EF56"


class TestQ3Dateiname:
    """Die Namensregel, ohne Datenbank."""

    def test_nummer_wird_dateiname(self):
        from app.services.beleg_dateiname import beleg_dateiname
        assert beleg_dateiname("RE-2026-00002") == "RE-2026-00002.pdf"
        assert beleg_dateiname("AB-20261008-0001") == "AB-20261008-0001.pdf"

    def test_platzhalter_heisst_entwurf(self):
        from app.services.beleg_dateiname import beleg_dateiname
        assert beleg_dateiname(_Q3_PLATZHALTER) == "Entwurf-AB12CD34EF56.pdf"

    def test_alter_entwurf_mit_re_nummer(self):
        from app.services.beleg_dateiname import beleg_dateiname
        assert beleg_dateiname("RE-2026-00003", entwurf=True) == "Entwurf-RE-2026-00003.pdf"

    def test_pfadtrenner_und_anfuehrungszeichen_werden_ersetzt(self):
        from app.services.beleg_dateiname import beleg_dateiname
        assert beleg_dateiname('RE/2026\\00"1') == "RE_2026_00_1.pdf"
        assert beleg_dateiname("") == "Beleg.pdf"
        assert beleg_dateiname(None) == "Beleg.pdf"

    def test_kopf_mit_umlauten_und_sonderzeichen(self):
        """RFC 5987: filename* trägt UTF-8, filename einen ASCII-Ersatz. Der
        Kopf ist reines ASCII — Starlette kodiert Köpfe als latin-1, ein '€'
        im Kopf endete sonst mit 500 (UnicodeEncodeError)."""
        from app.services.beleg_dateiname import content_disposition
        kopf = content_disposition("Entwurf-Bäckerei „Süd“ €.pdf")
        assert kopf == (
            "attachment; filename=\"Entwurf-Backerei _Sud_ _.pdf\"; "
            "filename*=UTF-8''Entwurf-B%C3%A4ckerei%20%E2%80%9ES%C3%BCd%E2%80%9C%20%E2%82%AC.pdf"
        )
        kopf.encode("ascii")

    def test_kopf_inline(self):
        from app.services.beleg_dateiname import content_disposition
        assert content_disposition("RE-2026-00002.pdf", art="inline").startswith(
            'inline; filename="RE-2026-00002.pdf"')


_Q3_ZEILE = {"description": "Erbsen-Schale", "quantity": 4, "unit": "STK",
             "unit_price": 2.50, "tax_rate": "REDUZIERT"}


def _q3_kunde(client):
    r = client.post("/api/v1/sales/customers", json={"name": "Fruchthof Nagel", "typ": "HANDEL"})
    assert r.status_code == 201, r.text
    return r.json()


def _q3_rechnungsentwurf(client) -> dict:
    r = client.post("/api/v1/invoices", json={
        "customer_id": _q3_kunde(client)["id"],
        "invoice_date": date.today().isoformat(),
        "lines": [_Q3_ZEILE],
    })
    assert r.status_code == 201, r.text
    rechnung = r.json()
    assert rechnung["status"] == "ENTWURF", rechnung
    return rechnung


def _q3_nummer_setzen(invoice_id: str, nummer: str) -> None:
    """Setzt die Nummer eines Entwurfs direkt: Platzhalter wie nach Q1 oder
    RE-Nummer wie bei Alt-Entwürfen (Spec-Entscheidung 2). So gilt der Test
    vor und nach Q1."""
    from app.models.invoice import Invoice
    with TestingSessionLocal() as db:
        db.get(Invoice, uuid.UUID(invoice_id)).invoice_number = nummer
        db.commit()


def _q3_belegkette(client) -> tuple[dict, dict]:
    """Bestellung mit AB und Lieferschein (samt Packliste)."""
    from tests.test_documents_preise import _create_order
    order_id = _create_order(client, _q3_kunde(client)["id"])
    ab = client.post(f"/api/v1/sales/orders/{order_id}/confirmations", json={})
    assert ab.status_code == 201, ab.text
    ls = client.post(f"/api/v1/sales/orders/{order_id}/delivery-notes", json={})
    assert ls.status_code == 201, ls.text
    return ab.json(), ls.json()


def _q3_kopf(nummer_pdf: str) -> str:
    return f"attachment; filename=\"{nummer_pdf}\"; filename*=UTF-8''{nummer_pdf}"


def _q3_mail_abfangen(monkeypatch) -> dict:
    """Fängt den Mailversand ab und liefert die Argumente von send_email.

    Bis zum Versand-Abschnitt (Q2) rufen die Endpunkte send_email direkt.
    Q2 verschickt über app.services.belegversand und ändert dafür nur diesen
    Rumpf; die Tests bleiben gleich."""
    # Seit Q1 prüft "Mailen" eines Entwurfs vor dem Festschreiben die
    # SMTP-Einstellungen — hier über die Umgebung "konfiguriert".
    monkeypatch.setenv("SMTP_HOST", "smtp.farm.example")
    monkeypatch.setenv("SMTP_USER", "versand@farm.example")
    versendet = {}
    monkeypatch.setattr("app.api.v1.invoices.send_email", lambda **kw: versendet.update(kw))
    # Seit Q2.5 verschickt die AB über app.services.belegversand (erwartet ein VersandErgebnis);
    # die Rechnungszeile darüber zieht in Q2.7 um.
    monkeypatch.setattr("app.services.belegversand.send_email", _q2_attrappe(versendet))
    return versendet


class TestQ3Downloads:

    def test_rechnung_heisst_wie_ihre_nummer(self, client):
        """Bisher Rechnung_RE-….pdf — Gernot will die Nummer (B7)."""
        rechnung = _q3_rechnungsentwurf(client)
        assert client.post(f"/api/v1/invoices/{rechnung['id']}/finalize").status_code == 200
        nummer = client.get(f"/api/v1/invoices/{rechnung['id']}").json()["invoice_number"]

        r = client.get(f"/api/v1/invoices/{rechnung['id']}/pdf")

        assert r.status_code == 200, r.text
        assert r.headers["content-disposition"] == _q3_kopf(f"{nummer}.pdf")

    def test_rechnungsentwurf_heisst_entwurf(self, client):
        """Ein Entwurf darf im Download-Ordner nicht wie die ausgestellte
        Rechnung heißen — auch ein Alt-Entwurf mit RE-Nummer nicht."""
        rechnung = _q3_rechnungsentwurf(client)
        _q3_nummer_setzen(rechnung["id"], "RE-2026-00003")

        r = client.get(f"/api/v1/invoices/{rechnung['id']}/pdf")

        assert r.status_code == 200, r.text
        assert r.headers["content-disposition"] == _q3_kopf("Entwurf-RE-2026-00003.pdf")

    def test_entwurf_mit_platzhalter(self, client):
        rechnung = _q3_rechnungsentwurf(client)
        _q3_nummer_setzen(rechnung["id"], _Q3_PLATZHALTER)

        r = client.get(f"/api/v1/invoices/{rechnung['id']}/pdf")

        assert r.status_code == 200, r.text
        assert r.headers["content-disposition"] == _q3_kopf("Entwurf-AB12CD34EF56.pdf")

    def test_ab_lieferschein_und_packliste(self, client):
        """Name war schon die Nummer; neu ist filename* (RFC 5987)."""
        ab, ls = _q3_belegkette(client)

        r_ab = client.get(f"/api/v1/sales/confirmations/{ab['id']}/pdf")
        r_ls = client.get(f"/api/v1/sales/delivery-notes/{ls['id']}/pdf")
        r_pl = client.get(f"/api/v1/sales/delivery-notes/{ls['id']}/packing-list/pdf")

        assert r_ab.headers["content-disposition"] == _q3_kopf(f"{ab['confirmation_number']}.pdf")
        assert r_ls.headers["content-disposition"] == _q3_kopf(f"{ls['delivery_note_number']}.pdf")
        assert r_pl.headers["content-disposition"] == _q3_kopf(
            f"{ls['packing_list']['packing_list_number']}.pdf")

    def test_browser_darf_den_namen_lesen(self, client):
        """Im Entwicklungsbetrieb (Vite :5173 → API :8000) ist der Abruf
        cross-origin; ohne Expose-Header sieht das Frontend den Namen nicht."""
        rechnung = _q3_rechnungsentwurf(client)

        r = client.get(f"/api/v1/invoices/{rechnung['id']}/pdf",
                       headers={"Origin": "http://localhost:5173"})

        assert r.status_code == 200, r.text
        assert "content-disposition" in r.headers.get("access-control-expose-headers", "").lower()


class TestQ3Mailanhang:
    """Charakterisierung: Der Anhang hieß schon {Nummer}.pdf. Er muss so
    bleiben, wenn die Endpunkte auf beleg_dateiname umgestellt sind — und
    nach dem Versand-Abschnitt (Q2), der nur _q3_mail_abfangen umhängt."""

    def test_ausgestellte_rechnung_mailen(self, client, monkeypatch):
        rechnung = _q3_rechnungsentwurf(client)
        assert client.post(f"/api/v1/invoices/{rechnung['id']}/finalize").status_code == 200
        nummer = client.get(f"/api/v1/invoices/{rechnung['id']}").json()["invoice_number"]
        versendet = _q3_mail_abfangen(monkeypatch)

        r = client.post(f"/api/v1/invoices/{rechnung['id']}/send",
                        params={"to_email": "einkauf@fruchthof.example"})

        assert r.status_code == 200, r.text
        assert versendet["attachment_filename"] == f"{nummer}.pdf"

    def test_altentwurf_mailen(self, client, monkeypatch):
        """'Mailen' stellt einen Alt-Entwurf heute mit dem Versand aus
        (ENTWURF -> OFFEN). Der Anhang heißt wie die Rechnung, nie 'Entwurf-…':
        Der Mailweg nimmt beleg_dateiname(nummer), nicht rechnung_dateiname."""
        rechnung = _q3_rechnungsentwurf(client)
        _q3_nummer_setzen(rechnung["id"], "RE-2026-00003")
        versendet = _q3_mail_abfangen(monkeypatch)

        r = client.post(f"/api/v1/invoices/{rechnung['id']}/send",
                        params={"to_email": "einkauf@fruchthof.example"})

        assert r.status_code == 200, r.text
        assert versendet["attachment_filename"] == "RE-2026-00003.pdf"

    def test_ab_mailen(self, client, monkeypatch):
        ab, _ = _q3_belegkette(client)
        versendet = _q3_mail_abfangen(monkeypatch)

        r = client.patch(f"/api/v1/sales/confirmations/{ab['id']}/send",
                         json={"sent_to_email": "einkauf@fruchthof.example"})

        assert r.status_code == 200, r.text
        assert versendet["attachment_filename"] == f"{ab['confirmation_number']}.pdf"



# ============================================================
# Q2 — Belegversand: mehrere Empfänger, Versandprotokoll,
#      Lieferschein-Versand, sent_at nur bei Versand (B2/B3)
#
# Gernot (08.10.2026): EINE Mail, alle Adressen im An-Feld. Kein Test
# verschickt echte Mails: _q2_smtp ersetzt smtplib.SMTP und schreibt jede
# Nachricht samt SMTP-Umschlag mit.
# ============================================================
import hashlib
import uuid

import pytest

from tests.conftest import TestingSessionLocal


class _Q2FakeSMTP:
    """Ersetzt smtplib.SMTP: verschickt nichts, merkt sich Mail und Umschlag."""
    gesendet: list = []
    abzulehnen: dict = {}  # Adresse -> (Code, Antwort) für Teilablehnungen

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ehlo(self):
        pass

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg, from_addr=None, to_addrs=None):
        umschlag = list(to_addrs or [])
        type(self).gesendet.append({"msg": msg, "umschlag": umschlag})
        return {a: v for a, v in type(self).abzulehnen.items() if a in umschlag}


@pytest.fixture
def _q2_smtp(monkeypatch):
    """SMTP über Umgebungsvariablen 'konfiguriert', Versand abgefangen."""
    for schluessel, wert in {
        "SMTP_HOST": "smtp.farm.example", "SMTP_PORT": "587",
        "SMTP_USER": "versand@farm.example", "SMTP_USE_TLS": "false",
        "SMTP_USE_SSL": "false", "EMAILS_FROM_EMAIL": "versand@farm.example",
        "EMAILS_FROM_NAME": "Testfarm",
    }.items():
        monkeypatch.setenv(schluessel, wert)
    _Q2FakeSMTP.gesendet = []
    _Q2FakeSMTP.abzulehnen = {}
    monkeypatch.setattr("smtplib.SMTP", _Q2FakeSMTP)
    return _Q2FakeSMTP


@pytest.fixture
def _q2_ohne_smtp(monkeypatch):
    """Kein SMTP konfiguriert (auch nicht aus der Umgebung des Rechners)."""
    for schluessel in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "EMAILS_FROM_EMAIL"):
        monkeypatch.delenv(schluessel, raising=False)


@pytest.fixture
def _q2_rolle(client):
    """Setzt das Login für den Rest des Tests auf genau diese Rollen."""
    from app.api.deps import get_current_user
    from app.main import app

    vorher = app.dependency_overrides.get(get_current_user)

    def _als(rollen, name="mia"):
        async def override():
            return {"id": "123e4567-e89b-12d3-a456-426614174099", "username": name,
                    "email": f"{name}@farm.example", "roles": rollen}
        app.dependency_overrides[get_current_user] = override

    yield _als
    if vorher is not None:
        app.dependency_overrides[get_current_user] = vorher


def _q2_kunde(client, **extra):
    r = client.post("/api/v1/sales/customers",
                    json={"name": "Ökoring Handels GmbH", "typ": "HANDEL", **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _q2_bestellung(client, kunde):
    """Freitext-Position mit ausdrücklichem Satz, bestätigt (Quittieren und
    Lieferschein brauchen nach Paket 2 eine bestätigte Bestellung)."""
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"],
        "requested_delivery_date": "2026-03-05",
        "lines": [{"product_name": "Erbsen-Schale", "quantity": 10, "unit": "STK",
                   "unit_price": 2.50, "tax_rate": "REDUZIERT"}],
    })
    assert r.status_code == 201, r.text
    bestellung = r.json()
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/confirm")
    assert r.status_code == 200, r.text
    return bestellung


def _q2_position_nachtragen(client, bestellung):
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/lines", json={
        "product_name": "Rettich-Schale", "quantity": 2, "unit": "STK",
        "unit_price": 3.00, "tax_rate": "REDUZIERT",
    })
    assert r.status_code == 201, r.text


def _q2_ab(client, bestellung):
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/confirmations", json={})
    assert r.status_code == 201, r.text
    return r.json()


def _q2_ls(client, bestellung):
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes", json={})
    assert r.status_code == 201, r.text
    return r.json()


def _q2_rechnung(client, bestellung):
    r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")
    assert r.status_code == 201, r.text
    return r.json()


def _q2_ab_senden(client, ab, body):
    return client.patch(f"/api/v1/sales/confirmations/{ab['id']}/send", json=body)


def _q2_ls_senden(client, ls, body):
    return client.post(f"/api/v1/sales/delivery-notes/{ls['id']}/send", json=body)


def _q2_abs(client, bestellung):
    return client.get(f"/api/v1/sales/orders/{bestellung['id']}/confirmations").json()


def _q2_anhang(mail):
    """(Dateiname, Bytes) des einzigen Anhangs einer abgefangenen Mail."""
    teile = list(mail["msg"].iter_attachments())
    assert len(teile) == 1, teile
    return teile[0].get_filename(), teile[0].get_content()


def _q2_firmenname(name):
    from app.services.settings_service import set_setting
    with TestingSessionLocal() as db:
        set_setting(db, "COMPANY_NAME", name)
        db.commit()


def _q2_sha(daten: bytes) -> str:
    return hashlib.sha256(daten).hexdigest()


def _q2_attrappe(sammler: dict):
    """Ersatz für app.services.belegversand.send_email in Tests, die nur die
    Mail-Argumente prüfen (Paket 1, Q1, Q3, Q5, Q6; umgehängt in Q2.5/Q2.7):
    merkt sich die Argumente und antwortet wie ein Mailserver, der alle
    Empfänger annimmt."""
    from app.services.email_service import VersandErgebnis

    def senden(**kw):
        sammler.update(kw)
        return VersandErgebnis(message_id="<attrappe@test.example>")
    return senden


class TestQ2Adressen:
    """Eine Prüfregel für Kundenstamm und Versand (app.core.email_adressen)."""

    def test_normalisiert_und_entfernt_dubletten(self):
        from app.core.email_adressen import pruefe_empfaenger
        assert pruefe_empfaenger([
            " Rechnung@Kunde.example ", "rechnung@kunde.example", "", None, "einkauf@kunde.example",
        ]) == ["rechnung@kunde.example", "einkauf@kunde.example"]
        assert pruefe_empfaenger(None) == []
        assert pruefe_empfaenger("chef@kunde.example") == ["chef@kunde.example"]

    def test_umlaut_vor_dem_at_wird_abgelehnt(self):
        """Gernots Beispiel 'einkäufer@…' — ohne SMTPUTF8 bräche der Versand ab."""
        from app.core.email_adressen import pruefe_empfaenger
        with pytest.raises(ValueError, match="Umlaute"):
            pruefe_empfaenger(["einkäufer@kunde.example"])

    def test_umlaut_in_der_domain_geht_als_ascii(self):
        from app.core.email_adressen import pruefe_empfaenger
        assert pruefe_empfaenger(["info@müller.example"]) == ["info@xn--mller-kva.example"]

    @pytest.mark.parametrize("adresse", [
        "kein-at-zeichen", "a@b", "x@kunde.example\r\nBcc: fremd@boese.example", "a b@kunde.example",
    ])
    def test_ungueltige_adresse(self, adresse):
        from app.core.email_adressen import pruefe_empfaenger
        with pytest.raises(ValueError, match="keine gültige E-Mail-Adresse"):
            pruefe_empfaenger([adresse])

    def test_hoechstens_zehn(self):
        from app.core.email_adressen import pruefe_empfaenger
        assert len(pruefe_empfaenger([f"a{i}@kunde.example" for i in range(10)])) == 10
        with pytest.raises(ValueError, match="höchstens 10"):
            pruefe_empfaenger([f"a{i}@kunde.example" for i in range(11)])


class TestQ2Mailversand:
    """send_email: eine Mail, alle Empfänger im An-Feld, Cc, Message-ID, Ablehnungen."""

    def test_eine_mail_an_alle(self, client, _q2_smtp):
        from app.services.email_service import send_email
        with TestingSessionLocal() as db:
            ergebnis = send_email(
                db=db, to=["rechnung@kunde.example", "einkauf@kunde.example"],
                cc=["chef@kunde.example"], subject="Test", body="Hallo",
                attachment_bytes=b"%PDF-1.4 test", attachment_filename="AB-1.pdf",
            )

        assert len(_q2_smtp.gesendet) == 1
        mail = _q2_smtp.gesendet[0]
        assert mail["msg"]["To"] == "rechnung@kunde.example, einkauf@kunde.example"
        assert mail["msg"]["Cc"] == "chef@kunde.example"
        assert mail["umschlag"] == ["rechnung@kunde.example", "einkauf@kunde.example", "chef@kunde.example"]
        assert ergebnis.message_id == mail["msg"]["Message-ID"]
        assert ergebnis.message_id.endswith("@farm.example>")
        assert ergebnis.abgelehnt == {}

    def test_einzelne_ablehnung_wird_gemeldet(self, client, _q2_smtp):
        from app.services.email_service import send_email
        _q2_smtp.abzulehnen = {"alt@kunde.example": (550, b"5.1.1 User unknown")}
        with TestingSessionLocal() as db:
            ergebnis = send_email(db=db, to=["alt@kunde.example", "neu@kunde.example"],
                                  subject="Test", body="Hallo")

        assert ergebnis.abgelehnt == {"alt@kunde.example": "550 5.1.1 User unknown"}

    def test_eine_adresse_als_text_bleibt_moeglich(self, client, _q2_smtp):
        """admin.py (SMTP-Test) ruft weiter mit einem String auf."""
        from app.services.email_service import send_email
        with TestingSessionLocal() as db:
            send_email(db=db, to="admin@farm.example", subject="SMTP-Test", body="x")

        assert _q2_smtp.gesendet[0]["umschlag"] == ["admin@farm.example"]
        assert "Cc" not in _q2_smtp.gesendet[0]["msg"]




class TestQ2PdfReproduzierbar:
    """Gleicher Inhalt → byte-gleiches PDF. Erst damit belegt die SHA-256 im
    Versandprotokoll, was hinausging. Vorher trug jedes PDF Erzeugungszeit und
    eine zufällige ID: zwei Abrufe desselben Belegs waren nie gleich."""

    def test_ab_pdf_zweimal_gleich(self, client):
        ab = _q2_ab(client, _q2_bestellung(client, _q2_kunde(client)))

        eins = client.get(f"/api/v1/sales/confirmations/{ab['id']}/pdf").content
        zwei = client.get(f"/api/v1/sales/confirmations/{ab['id']}/pdf").content

        assert eins.startswith(b"%PDF")
        assert _q2_sha(eins) == _q2_sha(zwei)

    def test_ab_pdf_folgt_der_bestellung(self, client):
        bestellung = _q2_bestellung(client, _q2_kunde(client))
        ab = _q2_ab(client, bestellung)
        vorher = client.get(f"/api/v1/sales/confirmations/{ab['id']}/pdf").content

        _q2_position_nachtragen(client, bestellung)

        nachher = client.get(f"/api/v1/sales/confirmations/{ab['id']}/pdf").content
        assert _q2_sha(vorher) != _q2_sha(nachher)

    def test_lieferschein_und_rechnung_zweimal_gleich(self, client):
        bestellung = _q2_bestellung(client, _q2_kunde(client))
        ls = _q2_ls(client, bestellung)
        rechnung = _q2_rechnung(client, bestellung)

        for url in (f"/api/v1/sales/delivery-notes/{ls['id']}/pdf",
                    f"/api/v1/invoices/{rechnung['id']}/pdf"):
            eins, zwei = client.get(url).content, client.get(url).content
            assert eins.startswith(b"%PDF"), url
            assert _q2_sha(eins) == _q2_sha(zwei), url




class TestQ2Empfaengerlisten:
    """Empfänger je Kunde und Belegart (AB, Lieferschein, Rechnung)."""

    def test_anlage_und_aenderung(self, client):
        kunde = _q2_kunde(client, email="info@oekoring.example",
                          invoice_emails=["Rechnung@Oekoring.example", "rechnung@oekoring.example"])
        assert kunde["invoice_emails"] == ["rechnung@oekoring.example"]
        assert kunde["confirmation_emails"] == []
        assert kunde["delivery_note_emails"] == []

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={
            "confirmation_emails": ["einkauf@oekoring.example", "lager@oekoring.example"],
        })
        assert r.status_code == 200, r.text
        gelesen = client.get(f"/api/v1/sales/customers/{kunde['id']}").json()
        assert gelesen["confirmation_emails"] == ["einkauf@oekoring.example", "lager@oekoring.example"]
        assert gelesen["invoice_emails"] == ["rechnung@oekoring.example"]

    def test_null_leert_die_liste(self, client):
        kunde = _q2_kunde(client, delivery_note_emails=["lager@oekoring.example"])

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"delivery_note_emails": None})

        assert r.status_code == 200, r.text
        assert r.json()["delivery_note_emails"] == []

    @pytest.mark.parametrize("liste", [
        ["einkäufer@oekoring.example"],
        ["kein-at-zeichen"],
        [f"a{i}@oekoring.example" for i in range(11)],
    ])
    def test_ungueltige_liste_wird_abgewiesen(self, client, liste):
        kunde = _q2_kunde(client)

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"invoice_emails": liste})

        assert r.status_code == 422, r.text
        assert client.get(f"/api/v1/sales/customers/{kunde['id']}").json()["invoice_emails"] == []

    def test_bestandskunde_ohne_listen(self, client):
        """Altdaten: Spalten NULL → die API liefert leere Listen."""
        from app.models.customer import Customer
        kunde = _q2_kunde(client)
        with TestingSessionLocal() as db:
            k = db.get(Customer, uuid.UUID(kunde["id"]))
            k.confirmation_emails = k.delivery_note_emails = k.invoice_emails = None
            db.commit()

        gelesen = client.get(f"/api/v1/sales/customers/{kunde['id']}").json()
        assert (gelesen["confirmation_emails"], gelesen["delivery_note_emails"],
                gelesen["invoice_emails"]) == ([], [], [])

    def test_auto_migrate_ergaenzt_spalten(self, tmp_path):
        from sqlalchemy import create_engine, inspect, text
        from app.tenancy import _auto_migrate

        engine = create_engine(f"sqlite:///{tmp_path / 'alt.db'}")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE customers (id CHAR(32) PRIMARY KEY, name VARCHAR(200))"))
            conn.execute(text("INSERT INTO customers (id, name) VALUES ('a', 'Ökoring')"))

        _auto_migrate(engine)

        spalten = {c["name"] for c in inspect(engine).get_columns("customers")}
        assert {"confirmation_emails", "delivery_note_emails", "invoice_emails"} <= spalten
        with engine.connect() as conn:
            assert conn.execute(text("SELECT invoice_emails FROM customers")).scalar() is None
        engine.dispose()




class TestQ2Versandprotokoll:
    """Tabelle document_dispatches, Empfängerregel und Protokoll in den Antworten."""

    def test_belege_liefern_ihr_protokoll(self, client):
        bestellung = _q2_bestellung(client, _q2_kunde(client))
        _q2_ab(client, bestellung)
        _q2_ls(client, bestellung)
        rechnung = _q2_rechnung(client, bestellung)

        assert _q2_abs(client, bestellung)[0]["dispatches"] == []
        ls_liste = client.get(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes").json()
        assert ls_liste[0]["dispatches"] == []
        assert client.get(f"/api/v1/invoices/{rechnung['id']}").json()["dispatches"] == []
        assert client.get("/api/v1/invoices").json()[0]["dispatches"] == []

    def test_empfaenger_regel(self, client):
        from app.models.customer import Customer
        from app.models.enums import DispatchDocType
        from app.services.belegversand import KeinEmpfaenger, ermittle_empfaenger
        kunde = _q2_kunde(client, email="info@oekoring.example",
                          invoice_emails=["rechnung@oekoring.example"])
        with TestingSessionLocal() as db:
            k = db.get(Customer, uuid.UUID(kunde["id"]))
            # Ausdrücklich übergeben schlägt den Kundenstamm
            assert ermittle_empfaenger(k, DispatchDocType.RE, to=["x@kunde.example"],
                                       use_customer_recipients=True) == ["x@kunde.example"]
            assert ermittle_empfaenger(k, DispatchDocType.RE, to=None,
                                       use_customer_recipients=True) == ["rechnung@oekoring.example"]
            # Keine Liste für die Belegart: Haupt-E-Mail
            assert ermittle_empfaenger(k, DispatchDocType.AB, to=None,
                                       use_customer_recipients=True) == ["info@oekoring.example"]
            # Ohne Adressen und ohne Wunsch nach der Kundenliste: keine Mail
            assert ermittle_empfaenger(k, DispatchDocType.AB, to=None,
                                       use_customer_recipients=False) == []
            k.email = None
            with pytest.raises(KeinEmpfaenger):
                ermittle_empfaenger(k, DispatchDocType.LS, to=None, use_customer_recipients=True)

    def test_versand_schreibt_protokollzeile(self, client, _q2_smtp):
        from app.models.documents import DocumentDispatch
        from app.models.enums import DispatchDocType, DispatchStatus
        from app.services.belegversand import versende_beleg
        _q2_smtp.abzulehnen = {"alt@kunde.example": (550, b"User unknown")}

        with TestingSessionLocal() as db:
            eintrag = versende_beleg(
                db, doc_type=DispatchDocType.AB, document_number="AB-20261008-0001",
                an=["neu@kunde.example", "alt@kunde.example"], cc=["chef@kunde.example"],
                betreff="Auftragsbestätigung AB-20261008-0001", text="Hallo",
                pdf=b"%PDF-1.4 q2", user={"id": "basic-auth:anna", "username": "anna"},
            )
            db.commit()
            zeile = db.get(DocumentDispatch, eintrag.id)

            assert zeile.status == DispatchStatus.TEILWEISE
            assert zeile.to_addrs == ["neu@kunde.example", "alt@kunde.example"]
            assert zeile.cc_addrs == ["chef@kunde.example"]
            assert zeile.refused == {"alt@kunde.example": "550 User unknown"}
            assert zeile.attachment_filename == "AB-20261008-0001.pdf"
            assert zeile.attachment_sha256 == _q2_sha(b"%PDF-1.4 q2")
            assert (zeile.sent_by_id, zeile.sent_by_name) == ("basic-auth:anna", "anna")
            assert zeile.message_id == _q2_smtp.gesendet[0]["msg"]["Message-ID"]
        assert len(_q2_smtp.gesendet) == 1

    def test_gescheiterter_versand_hinterlaesst_keine_zeile(self, client, _q2_ohne_smtp):
        from app.models.documents import DocumentDispatch
        from app.models.enums import DispatchDocType
        from app.services.belegversand import versende_beleg
        from app.services.email_service import EmailNotConfiguredError

        with TestingSessionLocal() as db:
            with pytest.raises(EmailNotConfiguredError):
                versende_beleg(
                    db, doc_type=DispatchDocType.LS, document_number="LS-20261008-0001",
                    an=["lager@kunde.example"], cc=None, betreff="Lieferschein", text="Hallo",
                    pdf=b"%PDF-1.4 q2", user={"id": "1", "username": "anna"},
                )
            db.rollback()
            assert db.query(DocumentDispatch).count() == 0

    def test_cc_und_obergrenze_nach_der_kundenliste(self, client):
        """Die Schema-Prüfung sieht nur die übergebenen Adressen. Erst nach dem
        Auflösen der Kundenliste steht das An-Feld fest: Cc ohne Dubletten,
        An + Cc zusammen höchstens 10 — sonst ginge per API eine Mail an
        10 hinterlegte Adressen plus 10 Cc hinaus."""
        from app.models.customer import Customer
        from app.models.enums import DispatchDocType
        from app.services.belegversand import empfaenger_fuer_versand
        kunde = _q2_kunde(client, confirmation_emails=[f"a{i}@oekoring.example" for i in range(10)])
        with TestingSessionLocal() as db:
            k = db.get(Customer, uuid.UUID(kunde["id"]))
            an, cc = empfaenger_fuer_versand(
                k, DispatchDocType.AB, to=["x@kunde.example"],
                cc=["X@Kunde.example", "chef@kunde.example"], use_customer_recipients=False,
            )
            assert (an, cc) == (["x@kunde.example"], ["chef@kunde.example"])
            with pytest.raises(ValueError, match="Höchstens 10"):
                empfaenger_fuer_versand(
                    k, DispatchDocType.AB, to=None,
                    cc=["a0@oekoring.example", "b@kunde.example"], use_customer_recipients=True,
                )
            # Ohne Mail kein Cc
            assert empfaenger_fuer_versand(
                k, DispatchDocType.AB, to=None, cc=[], use_customer_recipients=False,
            ) == ([], [])




class TestQ2DemoReset:
    """Charakterisierung (T5-Risiko 11, behoben in Paket 1 d8e1db2): Der
    nächtliche Reset kopiert den Golden-Seed über die Demo-DB und gleicht danach
    das Schema an. Ein Seed von vor Q2 bekommt so die Empfängerlisten und das
    Versandprotokoll — sonst endete jede Kundenabfrage der Demo mit 500."""

    def test_reset_bringt_alten_seed_auf_den_aktuellen_stand(self, tmp_path, monkeypatch):
        from sqlalchemy import create_engine, inspect, text
        from app.services import demo_reset_service as drs

        live = tmp_path / "demo.db"
        alt = create_engine(f"sqlite:///{drs._seed_path(live)}")
        with alt.begin() as conn:
            conn.execute(text("CREATE TABLE customers (id CHAR(32) PRIMARY KEY, name VARCHAR(200))"))
        alt.dispose()
        live.write_bytes(drs._seed_path(live).read_bytes())

        engines = []

        class _Registry:
            def path_for(self, slug):
                return live

            def dispose_tenant(self, slug):
                for engine in engines:
                    engine.dispose()

            def get_engine(self, slug):
                engine = create_engine(f"sqlite:///{live}")
                engines.append(engine)
                return engine

        monkeypatch.setattr("app.tenancy.registry", _Registry(), raising=False)

        ergebnis = drs.reset_demo_from_seed("demo")
        assert (ergebnis["status"], ergebnis["migriert"]) == ("reset", True)

        pruef = create_engine(f"sqlite:///{live}")
        try:
            spalten = {c["name"] for c in inspect(pruef).get_columns("customers")}
            assert {"pfand_abrechnung", "confirmation_emails", "delivery_note_emails",
                    "invoice_emails"} <= spalten
            assert inspect(pruef).has_table("document_dispatches")
        finally:
            pruef.dispose()
            for engine in engines:
                engine.dispose()




def _q2_text(mail) -> str:
    return mail["msg"].get_body(preferencelist=("plain",)).get_content()


class TestQ2AbVersand:
    """PATCH /sales/confirmations/{id}/send — mehrere Empfänger, Protokoll, leerer Body."""

    def test_leerer_body_markiert_nur(self, client, _q2_smtp):
        """Die Bedeutung von {} bleibt (persönliche Übergabe) — auch wenn beim
        Kunden Adressen hinterlegt sind: KEINE Mail."""
        kunde = _q2_kunde(client, email="info@oekoring.example",
                          confirmation_emails=["einkauf@oekoring.example"])
        ab = _q2_ab(client, _q2_bestellung(client, kunde))

        r = _q2_ab_senden(client, ab, {})

        assert r.status_code == 200, r.text
        antwort = r.json()
        assert antwort["status"] == "VERSENDET"
        assert antwort["sent_at"] is None
        assert _q2_smtp.gesendet == []
        [zeile] = antwort["dispatches"]
        assert zeile["status"] == "NUR_MARKIERT"
        assert zeile["to_addrs"] == []
        assert zeile["sent_by_name"] == "testuser"
        pdf = client.get(f"/api/v1/sales/confirmations/{ab['id']}/pdf").content
        assert zeile["attachment_sha256"] == _q2_sha(pdf)

    def test_eine_mail_an_mehrere(self, client, _q2_smtp):
        ab = _q2_ab(client, _q2_bestellung(client, _q2_kunde(client)))

        r = _q2_ab_senden(client, ab, {
            "to": ["rechnung@oekoring.example", "einkauf@oekoring.example"],
            "cc": ["chef@oekoring.example"],
        })

        assert r.status_code == 200, r.text
        [mail] = _q2_smtp.gesendet
        assert mail["msg"]["To"] == "rechnung@oekoring.example, einkauf@oekoring.example"
        assert mail["msg"]["Cc"] == "chef@oekoring.example"
        dateiname, pdf = _q2_anhang(mail)
        assert dateiname == f"{ab['confirmation_number']}.pdf"
        antwort = r.json()
        assert antwort["status"] == "VERSENDET"
        assert antwort["sent_at"] is not None
        assert antwort["sent_to_email"] == "rechnung@oekoring.example, einkauf@oekoring.example"
        [zeile] = antwort["dispatches"]
        assert zeile["status"] == "GESENDET"
        assert zeile["to_addrs"] == ["rechnung@oekoring.example", "einkauf@oekoring.example"]
        assert zeile["cc_addrs"] == ["chef@oekoring.example"]
        assert zeile["attachment_sha256"] == _q2_sha(pdf)
        assert zeile["sent_by_name"] == "testuser"
        assert zeile["sent_at"].endswith(("Z", "+00:00"))

    def test_hinterlegte_empfaenger(self, client, _q2_smtp):
        kunde = _q2_kunde(client, email="info@oekoring.example",
                          confirmation_emails=["einkauf@oekoring.example", "lager@oekoring.example"])
        ab = _q2_ab(client, _q2_bestellung(client, kunde))

        r = _q2_ab_senden(client, ab, {"use_customer_recipients": True})

        assert r.status_code == 200, r.text
        assert _q2_smtp.gesendet[0]["umschlag"] == ["einkauf@oekoring.example", "lager@oekoring.example"]

    def test_ohne_hinterlegte_adresse_400(self, client, _q2_smtp):
        bestellung = _q2_bestellung(client, _q2_kunde(client))
        ab = _q2_ab(client, bestellung)

        r = _q2_ab_senden(client, ab, {"use_customer_recipients": True})

        assert r.status_code == 400, r.text
        assert _q2_smtp.gesendet == []
        assert _q2_abs(client, bestellung)[0]["status"] == "ENTWURF"

    def test_altes_feld_sent_to_email(self, client, _q2_smtp):
        """Ein nach dem Deploy noch offener Tab mit dem alten Frontend."""
        ab = _q2_ab(client, _q2_bestellung(client, _q2_kunde(client)))

        r = _q2_ab_senden(client, ab, {"sent_to_email": "Einkauf@Oekoring.example"})

        assert r.status_code == 200, r.text
        assert _q2_smtp.gesendet[0]["umschlag"] == ["einkauf@oekoring.example"]

    def test_ungueltige_adresse_422_ohne_mail(self, client, _q2_smtp):
        bestellung = _q2_bestellung(client, _q2_kunde(client))
        ab = _q2_ab(client, bestellung)

        r = _q2_ab_senden(client, ab, {"to": ["einkäufer@oekoring.example"]})

        assert r.status_code == 422, r.text
        assert _q2_smtp.gesendet == []
        assert _q2_abs(client, bestellung)[0]["status"] == "ENTWURF"

    def test_erneut_senden_an_vergessene_adresse(self, client, _q2_smtp):
        ab = _q2_ab(client, _q2_bestellung(client, _q2_kunde(client)))
        assert _q2_ab_senden(client, ab, {"to": ["einkauf@oekoring.example"]}).status_code == 200

        r = _q2_ab_senden(client, ab, {"to": ["lager@oekoring.example"]})

        assert r.status_code == 200, r.text
        assert len(_q2_smtp.gesendet) == 2
        erste, zweite = r.json()["dispatches"]
        assert erste["to_addrs"] == ["einkauf@oekoring.example"]
        assert zweite["to_addrs"] == ["lager@oekoring.example"]
        assert erste["attachment_sha256"] == zweite["attachment_sha256"]
        # Kurzanzeige und sent_at bleiben beim ersten Versand
        assert r.json()["sent_to_email"] == "einkauf@oekoring.example"

    def test_nach_bestellaenderung_409_ohne_mail(self, client, _q2_smtp):
        bestellung = _q2_bestellung(client, _q2_kunde(client))
        ab = _q2_ab(client, bestellung)
        assert _q2_ab_senden(client, ab, {"to": ["einkauf@oekoring.example"]}).status_code == 200
        _q2_position_nachtragen(client, bestellung)

        r = _q2_ab_senden(client, ab, {"to": ["lager@oekoring.example"]})

        assert r.status_code == 409, r.text
        assert "neue AB" in r.json()["detail"]
        assert len(_q2_smtp.gesendet) == 1
        assert len(_q2_abs(client, bestellung)[0]["dispatches"]) == 1

    def test_versendete_ab_nicht_nochmal_markieren(self, client, _q2_smtp):
        ab = _q2_ab(client, _q2_bestellung(client, _q2_kunde(client)))
        assert _q2_ab_senden(client, ab, {}).status_code == 200

        r = _q2_ab_senden(client, ab, {})

        assert r.status_code == 400, r.text

    def test_ohne_smtp_503_und_ab_bleibt_entwurf(self, client, _q2_ohne_smtp):
        bestellung = _q2_bestellung(client, _q2_kunde(client))
        ab = _q2_ab(client, bestellung)

        r = _q2_ab_senden(client, ab, {"to": ["einkauf@oekoring.example"]})

        assert r.status_code == 503, r.text
        gelesen = _q2_abs(client, bestellung)[0]
        assert (gelesen["status"], gelesen["sent_at"], gelesen["dispatches"]) == ("ENTWURF", None, [])

    def test_teilablehnung_steht_im_protokoll(self, client, _q2_smtp):
        _q2_smtp.abzulehnen = {"alt@oekoring.example": (550, b"5.1.1 User unknown")}
        ab = _q2_ab(client, _q2_bestellung(client, _q2_kunde(client)))

        r = _q2_ab_senden(client, ab, {"to": ["neu@oekoring.example", "alt@oekoring.example"]})

        assert r.status_code == 200, r.text
        [zeile] = r.json()["dispatches"]
        assert zeile["status"] == "TEILWEISE"
        assert zeile["refused"] == {"alt@oekoring.example": "550 5.1.1 User unknown"}

    def test_firmenname_aus_den_einstellungen(self, client, _q2_smtp):
        _q2_firmenname("Testfarm GmbH")
        ab = _q2_ab(client, _q2_bestellung(client, _q2_kunde(client)))

        assert _q2_ab_senden(client, ab, {"to": ["einkauf@oekoring.example"]}).status_code == 200

        [mail] = _q2_smtp.gesendet
        assert mail["msg"]["Subject"] == f"Auftragsbestätigung {ab['confirmation_number']} — Testfarm GmbH"
        assert _q2_text(mail).rstrip().endswith("Testfarm GmbH")

    def test_halle_darf_ab_senden(self, client, _q2_smtp, _q2_rolle):
        ab = _q2_ab(client, _q2_bestellung(client, _q2_kunde(client)))
        _q2_rolle(["production_staff"])

        r = _q2_ab_senden(client, ab, {"to": ["einkauf@oekoring.example"]})

        assert r.status_code == 200, r.text
        assert r.json()["dispatches"][0]["sent_by_name"] == "mia"

    def test_cc_ohne_adressen_aus_der_kundenliste(self, client, _q2_smtp):
        kunde = _q2_kunde(client, confirmation_emails=["einkauf@oekoring.example", "lager@oekoring.example"])
        ab = _q2_ab(client, _q2_bestellung(client, kunde))

        r = _q2_ab_senden(client, ab, {"use_customer_recipients": True,
                                       "cc": ["Einkauf@Oekoring.example", "chef@oekoring.example"]})

        assert r.status_code == 200, r.text
        [mail] = _q2_smtp.gesendet
        assert mail["msg"]["To"] == "einkauf@oekoring.example, lager@oekoring.example"
        assert mail["msg"]["Cc"] == "chef@oekoring.example"
        assert mail["umschlag"] == ["einkauf@oekoring.example", "lager@oekoring.example",
                                    "chef@oekoring.example"]

    def test_obergrenze_gilt_auch_fuer_die_kundenliste(self, client, _q2_smtp):
        """Missbrauch per API: 10 hinterlegte Adressen plus 10 Cc ergäben eine
        Mail an 20 Empfänger. Abgewiesen — keine Mail, AB bleibt Entwurf."""
        kunde = _q2_kunde(client, confirmation_emails=[f"a{i}@oekoring.example" for i in range(10)])
        bestellung = _q2_bestellung(client, kunde)
        ab = _q2_ab(client, bestellung)

        r = _q2_ab_senden(client, ab, {"use_customer_recipients": True,
                                       "cc": [f"b{i}@kunde.example" for i in range(10)]})

        assert r.status_code == 400, r.text
        assert "Höchstens 10" in r.json()["detail"]
        assert _q2_smtp.gesendet == []
        assert _q2_abs(client, bestellung)[0]["status"] == "ENTWURF"




class TestQ2LsVersand:
    """POST /sales/delivery-notes/{id}/send — neu, gleiche Regeln wie die AB."""

    def test_lieferschein_per_mail(self, client, _q2_smtp):
        bestellung = _q2_bestellung(client, _q2_kunde(client))
        ls = _q2_ls(client, bestellung)

        r = _q2_ls_senden(client, ls, {"to": ["lager@oekoring.example", "einkauf@oekoring.example"]})

        assert r.status_code == 200, r.text
        [mail] = _q2_smtp.gesendet
        assert mail["umschlag"] == ["lager@oekoring.example", "einkauf@oekoring.example"]
        dateiname, pdf = _q2_anhang(mail)
        assert dateiname == f"{ls['delivery_note_number']}.pdf"
        antwort = r.json()
        assert antwort["status"] == "AUSGESTELLT"
        [zeile] = antwort["dispatches"]
        assert (zeile["doc_type"], zeile["status"]) == ("LS", "GESENDET")
        assert zeile["attachment_sha256"] == _q2_sha(pdf)

    def test_hinterlegte_ls_empfaenger(self, client, _q2_smtp):
        kunde = _q2_kunde(client, email="info@oekoring.example",
                          confirmation_emails=["einkauf@oekoring.example"],
                          delivery_note_emails=["lager@oekoring.example"])
        ls = _q2_ls(client, _q2_bestellung(client, kunde))

        r = _q2_ls_senden(client, ls, {"use_customer_recipients": True})

        assert r.status_code == 200, r.text
        assert _q2_smtp.gesendet[0]["umschlag"] == ["lager@oekoring.example"]

    def test_leerer_body_stellt_nur_aus(self, client, _q2_smtp):
        ls = _q2_ls(client, _q2_bestellung(client, _q2_kunde(client, email="info@oekoring.example")))

        r = _q2_ls_senden(client, ls, {})

        assert r.status_code == 200, r.text
        assert r.json()["status"] == "AUSGESTELLT"
        assert r.json()["dispatches"][0]["status"] == "NUR_MARKIERT"
        assert _q2_smtp.gesendet == []
        assert _q2_ls_senden(client, ls, {}).status_code == 400

    def test_quittierter_lieferschein_geht_als_kopie(self, client, _q2_smtp):
        bestellung = _q2_bestellung(client, _q2_kunde(client))
        ls = _q2_ls(client, bestellung)
        r = client.patch(f"/api/v1/sales/delivery-notes/{ls['id']}/mark-delivered",
                         json={"signed_by": "Herr Kern"})
        assert r.status_code == 200, r.text

        r = _q2_ls_senden(client, ls, {"to": ["lager@oekoring.example"]})

        assert r.status_code == 200, r.text
        assert r.json()["status"] == "GELIEFERT"
        assert len(_q2_smtp.gesendet) == 1

    def test_nach_bestellaenderung_409(self, client, _q2_smtp):
        bestellung = _q2_bestellung(client, _q2_kunde(client))
        ls = _q2_ls(client, bestellung)
        assert _q2_ls_senden(client, ls, {"to": ["lager@oekoring.example"]}).status_code == 200
        _q2_position_nachtragen(client, bestellung)

        r = _q2_ls_senden(client, ls, {"to": ["einkauf@oekoring.example"]})

        assert r.status_code == 409, r.text
        assert len(_q2_smtp.gesendet) == 1

    def test_halle_darf_lieferschein_senden(self, client, _q2_smtp, _q2_rolle):
        ls = _q2_ls(client, _q2_bestellung(client, _q2_kunde(client)))
        _q2_rolle(["production_staff"])

        r = _q2_ls_senden(client, ls, {"to": ["lager@oekoring.example"]})

        assert r.status_code == 200, r.text
        assert r.json()["dispatches"][0]["sent_by_name"] == "mia"

    def test_obergrenze_gilt_auch_fuer_die_kundenliste(self, client, _q2_smtp):
        """10 hinterlegte Lieferschein-Adressen plus Cc: abgewiesen, keine Mail."""
        kunde = _q2_kunde(client, delivery_note_emails=[f"l{i}@oekoring.example" for i in range(10)])
        ls = _q2_ls(client, _q2_bestellung(client, kunde))

        r = _q2_ls_senden(client, ls, {"use_customer_recipients": True, "cc": ["chef@oekoring.example"]})

        assert r.status_code == 400, r.text
        assert _q2_smtp.gesendet == []
