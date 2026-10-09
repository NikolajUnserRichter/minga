"""Monatliche Sammelrechnungen als Entwurf (B5, Spec 08.10.2026, Nachtrag T4).

Kunden mit ``invoice_mode = MONATLICH`` bekommen je Kalendermonat EINE
Sammelrechnung. Der Monatslauf legt sie am 1. des Folgemonats um 06:30
(Europe/Berlin) als **Entwurf** an — dazu die Leergutbelege der Kunden mit
``pfand_abrechnung = MONATLICH`` (leergut_service, Q6). Nichts wird
finalisiert oder versendet: Der Admin prüft und gibt frei; erst dann bekommt
die Rechnung ihre Nummer (InvoiceService.festschreiben, Q1).

Eine Regel für Vorschau, Monatslauf und Sammellauf: abgerechnet wird über
``_abrechenbare_lieferscheine`` und ``_aggregiere`` und angelegt über
``_sammelrechnung_anlegen`` (alle in ``app/api/v1/invoices.py``).

Schutz gegen doppelte Entwürfe, drei Ebenen:
1. ``billing_runs``: höchstens ein laufender Lauf je Monat (Teilindex),
2. ``invoices.batch_key``: höchstens eine aktive Monatsrechnung je Kunde und
   Monat (Teilindex ``ux_invoices_monatsrechnung``),
3. ``delivery_notes.invoice_id``: ein Lieferschein steckt in höchstens einer
   Rechnung.
Leergutbelege schützt Q6 selbst (Bewegungen mit invoice_id, höchstens ein
offener Leergutentwurf je Kunde); sie tragen keinen batch_key.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.billing_run import BillingRun
from app.models.customer import Customer, InvoiceMode
from app.models.documents import DeliveryNote
from app.models.enums import DeliveryNoteStatus, OrderStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.order import Order
from app.services.invoice_service import InvoiceService
from app.services.settings_service import get_setting

logger = logging.getLogger(__name__)

#: Mandanten-Schalter in app_settings, gepflegt unter Einstellungen.
SCHALTER = "MONATSRECHNUNG_AUTO"
ART_AUTO = "MONAT_AUTO"
ART_MANUELL = "MONAT_MANUELL"
#: Ein laufender Lauf gilt danach als verwaist (Absturz, Neustart mitten im Lauf).
VERWAIST_NACH = timedelta(minutes=60)
#: Der automatische Lauf holt den Vormonat nur in den ersten Tagen des Monats nach.
NACHHOLFENSTER_TAGE = 7
#: Hinweis "früherer Monat" schaut so weit zurück.
_FRUEHESTER_TAG = date(2000, 1, 1)


# ---------------------------------------------------------------------------
# Datum und Monat
# ---------------------------------------------------------------------------

def heute_berlin(jetzt: Optional[datetime] = None) -> date:
    """Kalendertag in Europe/Berlin — der Container läuft auf UTC.

    ``jetzt`` (mit Zeitzone) nur für Tests: 31.10. 23:30 UTC ist in Berlin
    schon der 1.11.
    """
    return (jetzt or datetime.now(timezone.utc)).astimezone(ZoneInfo("Europe/Berlin")).date()


def monat_grenzen(monat: str) -> tuple[date, date]:
    """'2026-10' -> (2026-10-01, 2026-10-31). ValueError bei anderem Format."""
    teile = monat.split("-") if isinstance(monat, str) else []
    if len(teile) != 2 or len(teile[0]) != 4 or len(teile[1]) != 2 or not all(t.isdigit() for t in teile):
        raise ValueError(f"Monat '{monat}' nicht im Format JJJJ-MM")
    try:
        start = date(int(teile[0]), int(teile[1]), 1)
    except ValueError:
        raise ValueError(f"Monat '{monat}' nicht im Format JJJJ-MM")
    folgemonat = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return start, folgemonat - timedelta(days=1)


def vormonat(heute: date) -> str:
    """Der Monat vor ``heute`` als JJJJ-MM."""
    letzter = heute.replace(day=1) - timedelta(days=1)
    return f"{letzter.year:04d}-{letzter.month:02d}"


def monatsschluessel(monat: str) -> str:
    """invoices.batch_key der Monatsrechnung, z. B. MONAT-2026-10."""
    return f"MONAT-{monat}"


def automatik_an(db: Session) -> bool:
    """Mandanten-Schalter. Bewusst ohne Rückfall auf Umgebungsvariablen: eine
    Container-Variable schaltete sonst alle Mandanten ein (Nachtrag T4, 1.5)."""
    return (get_setting(db, SCHALTER, env_fallback=False) or "").lower() in ("1", "true", "yes")


def _jetzt_utc_naiv() -> datetime:
    # SQLite speichert DateTime ohne Zeitzone; gespeichert und verglichen
    # wird deshalb durchgehend naive UTC.
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Bestand lesen
# ---------------------------------------------------------------------------

def _monatsrechnungen(db: Session, monat: str) -> list[Invoice]:
    """Nicht stornierte Monatsrechnungen (Ware) des Monats."""
    return db.execute(
        select(Invoice).where(
            Invoice.batch_key == monatsschluessel(monat),
            Invoice.status != InvoiceStatus.STORNIERT,
        ).order_by(Invoice.created_at)
    ).scalars().all()


def _leergutbelege(db: Session, monat: str) -> list[Invoice]:
    """Nicht stornierte Leergutbelege (Q6), deren Leistungszeitraum am
    Monatsende endet — so legt leergut_service.belege_anlegen sie an."""
    from app.services.leergut_service import BELEG_ART_LEERGUT
    _, ende = monat_grenzen(monat)
    return db.execute(
        select(Invoice).where(
            Invoice.beleg_art == BELEG_ART_LEERGUT,
            Invoice.service_period_end == ende,
            Invoice.status != InvoiceStatus.STORNIERT,
        ).order_by(Invoice.created_at)
    ).scalars().all()


def _monatskunden(db: Session) -> list[Customer]:
    return db.execute(
        select(Customer).where(Customer.invoice_mode == InvoiceMode.MONATLICH).order_by(Customer.name)
    ).scalars().all()


def _je_kunde(eintraege) -> dict:
    gruppen: dict = defaultdict(list)
    for note, leistungsdatum in eintraege:
        gruppen[note.order.customer_id].append((note, leistungsdatum))
    return gruppen


def _summe_netto(k: dict) -> Decimal:
    # Dieselbe Formel wie batch_run_preview
    return sum((pos["menge"] * key[2] * (1 - key[5] / 100) for key, pos in k["positionen"].items()),
               Decimal("0"))


def _beleg(inv: Invoice, art: str) -> dict:
    return {
        "invoice_id": str(inv.id),
        "invoice_number": inv.invoice_number,
        "customer_id": str(inv.customer_id),
        "customer_name": inv.customer.name if inv.customer else "—",
        "status": inv.status.value,
        "art": art,
        "subtotal": inv.subtotal,
        "total": inv.total,
    }


def _hinweis(art: str, kunde: Optional[Customer], text: str, belege: Optional[list[str]] = None) -> dict:
    return {
        "art": art,
        "customer_id": str(kunde.id) if kunde else None,
        "customer_name": kunde.name if kunde else None,
        "text": text,
        "belege": belege or [],
    }


def _hinweise(db: Session, monat: str, im_monat: dict, monatskunden: list[Customer],
              rechnungen: list[Invoice]) -> list[dict]:
    """Was die Monatsrechnung NICHT enthält und der Admin wissen muss.

    Berechnet beim Abruf, nicht beim Lauf: Nachgezogene Lieferscheine und
    neue Lieferungen sollen sofort sichtbar sein.
    """
    from app.api.v1.invoices import BatchRunRequest, _abrechenbare_lieferscheine

    start, ende = monat_grenzen(monat)
    hinweise: list[dict] = []
    kunden_ids = {k.id for k in monatskunden}
    mit_monatsrechnung = {r.customer_id for r in rechnungen}
    abgerechnet = InvoiceService(db).abgerechnete_bestellungen()

    # 1. Bestellungen ohne Lieferschein — der Monatslauf rechnet über
    #    Lieferscheine ab; ohne Lieferschein fehlt die Lieferung still.
    #    Alle nicht stornierten Status, nicht nur GELIEFERT: gelieferte
    #    Bestellungen bleiben heute oft auf BESTAETIGT stehen (Spec A1).
    liefertag = func.coalesce(Order.actual_delivery_date, Order.requested_delivery_date)
    ohne_ls = db.execute(
        select(Order).where(
            Order.customer_id.in_(kunden_ids),
            liefertag.between(start, ende),
            Order.status.notin_([OrderStatus.STORNIERT, OrderStatus.FAKTURIERT]),
            ~select(DeliveryNote.id).where(DeliveryNote.order_id == Order.id).exists(),
        ).order_by(Order.order_number)
    ).scalars().all() if kunden_ids else []
    for kunde in monatskunden:
        nummern = [o.order_number for o in ohne_ls if o.customer_id == kunde.id and o.id not in abgerechnet]
        if nummern:
            hinweise.append(_hinweis(
                "OHNE_LIEFERSCHEIN", kunde,
                f"{len(nummern)} Bestellung(en) mit Liefertermin im Monat ohne Lieferschein — "
                f"nicht in der Monatsrechnung. Lieferschein anlegen; liegt schon ein Entwurf "
                f"vor, ihn verwerfen und den Lauf erneut starten.",
                nummern,
            ))

    # 2. Lieferscheine nach dem Entwurf
    for kunde in monatskunden:
        if kunde.id in mit_monatsrechnung and im_monat.get(kunde.id):
            hinweise.append(_hinweis(
                "NACHGEKOMMEN", kunde,
                "Lieferscheine nach dem Anlegen der Monatsrechnung hinzugekommen. "
                "Entwurf verwerfen und den Lauf erneut starten; ist die Rechnung schon "
                "freigegeben, gehören sie in eine eigene Rechnung.",
                sorted(n.delivery_note_number for n, _ in im_monat[kunde.id]),
            ))

    # 3. Vergessene Lieferscheine aus früheren Monaten. Der Lauf für jenen
    #    Monat überspringt den Kunden, sobald dort eine Monatsrechnung steht
    #    (_anlegen: "Monatsrechnung vorhanden") — der Normalfall. Dann bleibt
    #    die Rechnung aus der Bestellung (Frage 10 an den Steuerberater offen).
    frueher = _je_kunde(_abrechenbare_lieferscheine(db, BatchRunRequest(
        period_from=_FRUEHESTER_TAG, period_to=start - timedelta(days=1))))
    for kunde in monatskunden:
        if frueher.get(kunde.id):
            hinweise.append(_hinweis(
                "FRUEHERER_MONAT", kunde,
                "Nicht abgerechnete Lieferscheine aus früheren Monaten — nicht in dieser "
                "Monatsrechnung. Ist die Monatsrechnung jenes Monats schon freigegeben: "
                "über die Bestellung einzeln abrechnen („Rechnung aus Bestellung“ in den "
                "Belegen der Bestellung). Liegt dort ein Entwurf vor: ihn verwerfen und "
                "den Lauf für jenen Monat erneut starten; ohne Monatsrechnung: Lauf für "
                "jenen Monat starten.",
                sorted(n.delivery_note_number for n, _ in frueher[kunde.id]),
            ))

    # 4. Inaktive Monatskunden mit Lieferungen
    for kunde in monatskunden:
        if not kunde.aktiv and im_monat.get(kunde.id):
            hinweise.append(_hinweis(
                "INAKTIV", kunde,
                "Kunde ist inaktiv, hat aber nicht abgerechnete Lieferungen im Monat — "
                "kein Entwurf angelegt.",
                sorted(n.delivery_note_number for n, _ in im_monat[kunde.id]),
            ))

    # 5. Lieferscheine ohne Quittung — vor dem Lauf (frei im Monat) und im
    #    Monatsentwurf. Abgerechnet wird die Bestellmenge (Nachtrag T4, Risiko 5).
    im_entwurf = {r.id: r.customer_id for r in rechnungen if r.status == InvoiceStatus.ENTWURF}
    ohne_quittung: dict = defaultdict(list)
    for kunde in monatskunden:
        if kunde.aktiv and kunde.id not in mit_monatsrechnung:
            ohne_quittung[kunde.id] += [n.delivery_note_number for n, _ in im_monat.get(kunde.id, [])
                                        if n.status != DeliveryNoteStatus.GELIEFERT]
    if im_entwurf:
        for n in db.execute(select(DeliveryNote).where(
            DeliveryNote.invoice_id.in_(list(im_entwurf)),
            DeliveryNote.status != DeliveryNoteStatus.GELIEFERT,
        )).scalars():
            ohne_quittung[im_entwurf[n.invoice_id]].append(n.delivery_note_number)
    for kunde in monatskunden:
        if ohne_quittung.get(kunde.id):
            hinweise.append(_hinweis(
                "NICHT_QUITTIERT", kunde,
                "Lieferscheine ohne Quittung — abgerechnet wird die Bestellmenge. "
                "Minder- oder Teillieferungen vor dem Freigeben in der Bestellung korrigieren.",
                sorted(ohne_quittung[kunde.id]),
            ))

    # 6. Monatskunden ohne Lieferungen
    for kunde in monatskunden:
        if kunde.aktiv and kunde.id not in mit_monatsrechnung and not im_monat.get(kunde.id):
            hinweise.append(_hinweis("KEINE_LIEFERUNGEN", kunde, "Keine abrechenbaren Lieferungen im Monat."))

    # 7. Einzelabrechnung — nicht im Monatslauf
    einzeln = [k for k in db.execute(select(Customer).where(
        Customer.invoice_mode == InvoiceMode.EINZELN, Customer.id.in_(list(im_monat.keys()))
    ).order_by(Customer.name)).scalars().all()] if im_monat else []
    for kunde in einzeln:
        hinweise.append(_hinweis(
            "EINZELABRECHNUNG", kunde,
            "Nicht abgerechnete Lieferscheine im Monat — nicht enthalten, weil der Kunde "
            "je Lieferung abgerechnet wird.",
            sorted(n.delivery_note_number for n, _ in im_monat[kunde.id]),
        ))
    return hinweise


def vorschau(db: Session, monat: str) -> dict:
    """Stand der Monatsrechnungen eines Monats. Schreibt nichts.

    Speist den Dialog „Monatsrechnungen", das Banner der Rechnungsseite und
    die Karte im Dashboard.
    """
    from app.api.v1.invoices import BatchRunRequest, _abrechenbare_lieferscheine, _aggregiere
    from app.services import leergut_service

    start, ende = monat_grenzen(monat)
    if start > heute_berlin():
        raise ValueError(f"Monat {monat} liegt in der Zukunft")
    monatskunden = _monatskunden(db)
    rechnungen = _monatsrechnungen(db, monat)
    mit_monatsrechnung = {r.customer_id for r in rechnungen}
    im_monat = _je_kunde(_abrechenbare_lieferscheine(db, BatchRunRequest(period_from=start, period_to=ende)))

    vorgeschlagen = []
    for kunde in monatskunden:
        if not kunde.aktiv or kunde.id in mit_monatsrechnung or not im_monat.get(kunde.id):
            continue
        k = _aggregiere(db, im_monat[kunde.id]).get(kunde.id)
        if not k:
            continue
        vorgeschlagen.append({
            "art": "WARE",
            "customer_id": str(kunde.id),
            "customer_name": kunde.name,
            "anzahl_lieferscheine": len(k["lieferscheine"]),
            "summe_netto": _summe_netto(k),
        })
    for k in leergut_service.vorschau(db, monat, None)["kunden"]:
        vorgeschlagen.append({
            "art": "LEERGUT",
            "customer_id": str(k["customer_id"]),
            "customer_name": k["customer_name"],
            "anzahl_lieferscheine": 0,
            "summe_netto": k["summe_netto"],
        })

    letzter = db.execute(
        select(BillingRun).where(BillingRun.monat == monat).order_by(BillingRun.gestartet_am.desc()).limit(1)
    ).scalar_one_or_none()

    return {
        "monat": monat,
        "zeitraum_von": start.isoformat(),
        "zeitraum_bis": ende.isoformat(),
        "automatik_an": automatik_an(db),
        "letzter_lauf": None if letzter is None else {
            "art": letzter.art,
            "status": letzter.status,
            "gestartet_am": letzter.gestartet_am.isoformat(),
            "beendet_am": letzter.beendet_am.isoformat() if letzter.beendet_am else None,
            "ausgeloest_von": letzter.ausgeloest_von,
        },
        "entwuerfe": [_beleg(r, "WARE") for r in rechnungen]
                     + [_beleg(b, "LEERGUT") for b in _leergutbelege(db, monat)],
        "vorgeschlagen": vorgeschlagen,
        "hinweise": _hinweise(db, monat, im_monat, monatskunden, rechnungen),
    }


# ---------------------------------------------------------------------------
# Lauf
# ---------------------------------------------------------------------------

def _sperren(db: Session, monat: str, art: str, ausgeloest_von: Optional[str],
             jetzt: datetime) -> Optional[BillingRun]:
    """Legt den Lauf als LAEUFT an. None, wenn für den Monat schon einer läuft.

    Ein LAEUFT-Eintrag, der älter ist als VERWAIST_NACH, stammt aus einem
    abgebrochenen Prozess: er wird auf FEHLER gesetzt und der Lauf übernimmt.
    Das bedingte UPDATE (… AND status = 'LAEUFT') entscheidet zwischen zwei
    Prozessen, die gleichzeitig übernehmen wollen.
    """
    for _ in range(2):
        lauf = BillingRun(monat=monat, art=art, status="LAEUFT",
                          gestartet_am=jetzt, ausgeloest_von=ausgeloest_von)
        db.add(lauf)
        try:
            db.commit()
            return lauf
        except IntegrityError:
            db.rollback()
        alt = db.execute(
            select(BillingRun).where(BillingRun.monat == monat, BillingRun.status == "LAEUFT")
        ).scalar_one_or_none()
        if alt is None or alt.gestartet_am > jetzt - VERWAIST_NACH:
            return None
        uebernommen = db.execute(
            update(BillingRun)
            .where(BillingRun.id == alt.id, BillingRun.status == "LAEUFT")
            .values(status="FEHLER", beendet_am=jetzt,
                    fehler="verwaist: Lauf nicht beendet (Neustart oder Absturz)")
        ).rowcount
        db.commit()
        if uebernommen != 1:
            return None
    return None


def _anlegen(db: Session, monat: str, heute: date, ausgeloest_von: Optional[str]) -> dict:
    from app.api.v1.invoices import BatchRunRequest, _abrechenbare_lieferscheine, _aggregiere, _sammelrechnung_anlegen
    from app.services import leergut_service

    start, ende = monat_grenzen(monat)
    angelegt, uebersprungen, fehler = [], [], []
    service = InvoiceService(db)
    anfrage = BatchRunRequest(period_from=start, period_to=ende, invoice_date=heute)

    vorhanden = {r.customer_id for r in _monatsrechnungen(db, monat)}
    im_monat = _je_kunde(_abrechenbare_lieferscheine(db, anfrage))

    for kunde in _monatskunden(db):
        if not kunde.aktiv:
            continue
        name = kunde.name
        if kunde.id in vorhanden:
            uebersprungen.append({"customer_id": str(kunde.id), "customer_name": name,
                                  "grund": "Monatsrechnung vorhanden"})
            continue
        k = _aggregiere(db, im_monat.get(kunde.id, [])).get(kunde.id)
        if not k:
            uebersprungen.append({"customer_id": str(kunde.id), "customer_name": name,
                                  "grund": "keine abrechenbaren Lieferungen"})
            continue
        try:
            invoice = _sammelrechnung_anlegen(db, service, k, anfrage)
            invoice.batch_key = monatsschluessel(monat)
            db.commit()
            angelegt.append({"invoice_id": str(invoice.id), "customer_id": str(kunde.id),
                             "customer_name": name, "art": "WARE"})
        except IntegrityError:
            db.rollback()
            uebersprungen.append({"customer_id": str(kunde.id), "customer_name": name,
                                  "grund": "Monatsrechnung parallel angelegt"})
        except Exception as e:  # ein Kunde blockiert nicht die übrigen
            db.rollback()
            logger.exception(f"[monatsrechnung] {monat} Kunde {name} fehlgeschlagen")
            fehler.append({"customer_id": str(kunde.id), "customer_name": name, "fehler": str(e)[:500]})

    # Leergut (Q6): je Kunde mit offenen Leergutbewegungen ein Beleg — auch
    # bei Einzelabrechnung der Ware. Q6 entscheidet, wer dran ist, und
    # schützt selbst vor doppelten Belegen. Je Kunde eine Transaktion.
    plan = leergut_service.vorschau(db, monat, None)
    for u in plan["uebersprungen"]:
        uebersprungen.append({"customer_id": str(u["customer_id"]), "customer_name": u["customer_name"],
                              "grund": u["grund"]})
    for k in plan["kunden"]:
        try:
            belege, _ = leergut_service.belege_anlegen(
                db, monat, [k["customer_id"]], erfasst_von=ausgeloest_von or "Monatslauf")
            db.commit()
            angelegt.extend({"invoice_id": str(b.id), "customer_id": str(b.customer_id),
                             "customer_name": k["customer_name"], "art": "LEERGUT"} for b in belege)
        except Exception as e:  # LeergutFehler und alles andere: nur dieser Kunde
            db.rollback()
            logger.exception(f"[monatsrechnung] {monat} Leergut {k['customer_name']} fehlgeschlagen")
            fehler.append({"customer_id": str(k["customer_id"]), "customer_name": k["customer_name"],
                           "fehler": str(e)[:500]})

    return {"angelegt": angelegt, "uebersprungen": uebersprungen, "fehler": fehler}


def monatslauf(db: Session, monat: str, art: str, ausgeloest_von: Optional[str] = None,
               heute: Optional[date] = None, jetzt: Optional[datetime] = None) -> dict:
    """Legt die Monatsentwürfe für ``monat`` an. Idempotent.

    Kunden mit vorhandenem Monatsbeleg werden übersprungen; ein erneuter
    Lauf ergänzt nur, was fehlt. Rückgabe ``status``: ``ok`` oder
    ``laeuft_bereits``.
    """
    monat_grenzen(monat)  # Format prüfen, bevor etwas geschrieben wird
    jetzt = jetzt or _jetzt_utc_naiv()
    heute = heute or heute_berlin()
    lauf = _sperren(db, monat, art, ausgeloest_von, jetzt)
    if lauf is None:
        return {"status": "laeuft_bereits", "monat": monat}
    lauf_id = lauf.id
    try:
        ergebnis = _anlegen(db, monat, heute, ausgeloest_von)
    except Exception as e:
        db.rollback()
        lauf = db.get(BillingRun, lauf_id)
        lauf.status, lauf.beendet_am, lauf.fehler = "FEHLER", _jetzt_utc_naiv(), str(e)[:2000]
        db.commit()
        raise
    lauf = db.get(BillingRun, lauf_id)
    lauf.status, lauf.beendet_am, lauf.ergebnis = "FERTIG", _jetzt_utc_naiv(), ergebnis
    db.commit()
    return {"status": "ok", "monat": monat, "lauf_id": str(lauf_id), **ergebnis}
