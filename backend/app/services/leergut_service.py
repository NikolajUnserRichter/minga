"""Leergutkonto (Paket 3, Q6) — alle Regeln an einer Stelle.

Kunden mit pfand_abrechnung = MONATLICH bekommen Pfandkisten nicht auf der
Lieferrechnung berechnet. Ab dem Stichtag (Customer.pfand_monatlich_ab)
gilt:

- Lieferung: Beim Übergang nach GELIEFERT bucht deduct_inventory_for_order
  je Pfandposition eine AUSGABE (buche_ausgaben) — in derselben Transaktion
  wie der Bestandsabzug.
- Rückgabe: als Stückzahl erfasst (RUECKNAHME), ohne Geldbetrag.
- Monatsabrechnung: ein Leergutbeleg je Kunde mit "ausgegeben" und
  "zurückgenommen" je Pfandartikel. Gelieferte Bestellungen ohne Ausgabe
  (Statuswege ohne GELIEFERT) bucht erst das Anlegen der Belege nach, nie die
  Vorschau.

Doppelabrechnungsschutz beim Wechsel der Abrechnungsart, in beide Richtungen:
- Eine Pfandposition, die schon auf einer gültigen Rechnung steht, bekommt
  keine Ausgabe (pfandzeile_fakturiert).
- Eine Pfandposition mit Ausgabe kommt nie mehr auf eine Lieferrechnung,
  gleich wie der Kunde heute steht (invoice_service.ist_clearing_pfand).
- Was vor dem Stichtag geliefert wurde, bleibt in der alten Abrechnungsart.

Steuerlich offen (Steuerberater): Einordnung der Kiste, Saldierung, Beleg bei
Saldo 0, Bezeichnung des Minderungsbelegs.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer import Customer, PfandAbrechnung
from app.models.documents import DeliveryNote
from app.models.enums import InvoiceStatus, InvoiceType, OrderStatus
from app.models.invoice import Invoice, InvoiceLine, InvoiceLineSource
from app.models.leergut import LeergutArt, LeergutBewegung
from app.models.order import Order, OrderLine
from app.models.product import Product
from app.services.steuersatz import produkt_der_position

#: Invoice.beleg_art des monatlichen Leergutbelegs
BELEG_ART_LEERGUT = "LEERGUT"
SYSTEM_LIEFERUNG = "System (Lieferung)"
SYSTEM_MONATSABRECHNUNG = "System (Monatsabrechnung)"

#: Bestellungen, deren Pfand der Monatslauf nachbucht, wenn die Lieferung
#: keine Ausgabe gebucht hat (z. B. weil die Bestellung nie GELIEFERT wurde).
_NACHZUG_STATUS = (
    OrderStatus.BESTAETIGT, OrderStatus.IN_PRODUKTION,
    OrderStatus.GELIEFERT, OrderStatus.FAKTURIERT,
)


class LeergutFehler(ValueError):
    """Fachlich unzulässig — die API antwortet mit 400."""


def heute_berlin() -> date:
    """Kalendertag in München — der Server läuft in UTC."""
    return datetime.now(ZoneInfo("Europe/Berlin")).date()


def ist_pfandartikel(produkt: Optional[Product]) -> bool:
    return produkt is not None and bool(produkt.is_deposit)


def pfandwert(produkt: Product) -> Decimal:
    """Pfandwert je Stück: deposit_value, ersatzweise base_price — für Ausgabe
    und Rücknahme dieselbe Quelle, nie der (Kunden-)Preis der Bestellzeile."""
    wert = produkt.deposit_value if produkt.deposit_value is not None else produkt.base_price
    return Decimal(str(wert or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def konto(db: Session, kunde: Customer) -> dict:
    """Kistensaldo je Pfandartikel (alle Bewegungen) und die Bewegungen."""
    bewegungen = db.execute(
        select(LeergutBewegung)
        .where(LeergutBewegung.customer_id == kunde.id)
        .order_by(LeergutBewegung.leistungsdatum.desc(), LeergutBewegung.erfasst_am.desc())
    ).scalars().all()
    salden: dict = {}
    for b in bewegungen:
        s = salden.setdefault(b.product_id, {
            "product_id": b.product_id, "artikel": b.product.name,
            "stueck": 0, "wert": Decimal("0.00"),
            "offen_stueck": 0, "offen_wert": Decimal("0.00"),
        })
        s["stueck"] += b.stueck_mit_vorzeichen
        s["wert"] += b.stueck_mit_vorzeichen * b.einzelwert
        if b.abrechenbar:
            s["offen_stueck"] += b.stueck_mit_vorzeichen
            s["offen_wert"] += b.stueck_mit_vorzeichen * b.einzelwert
    return {
        "customer_id": kunde.id,
        "customer_name": kunde.name,
        "pfand_abrechnung": kunde.pfand_abrechnung,
        "pfand_monatlich_ab": kunde.pfand_monatlich_ab,
        "salden": sorted(salden.values(), key=lambda s: s["artikel"]),
        "bewegungen": bewegungen,
    }


def kunden_mit_konto(db: Session) -> list[dict]:
    """Aktive Kunden mit Leergutkonto und ihr Kistensaldo — für die Auswahl in der Halle."""
    kunden = db.execute(
        select(Customer).where(Customer.aktiv.is_(True)).order_by(Customer.name)
    ).scalars().all()
    stueck: dict = {}
    for b in db.execute(select(LeergutBewegung)).scalars():
        stueck[b.customer_id] = stueck.get(b.customer_id, 0) + b.stueck_mit_vorzeichen
    return [
        {"customer_id": k.id, "name": k.name, "pfand_abrechnung": k.pfand_abrechnung,
         "stueck_beim_kunden": stueck.get(k.id, 0)}
        for k in kunden
        if k.pfand_abrechnung == PfandAbrechnung.MONATLICH or k.id in stueck
    ]


def leistungsdatum(order: Order) -> date:
    """Liefertag der Bestellung: tatsächlich (setzen Quittieren und Statuswechsel
    nach GELIEFERT), ersatzweise gewünscht."""
    return order.actual_delivery_date or order.requested_delivery_date


def im_leergutkonto(kunde: Optional[Customer], order: Order) -> bool:
    """Gehört das Pfand dieser Bestellung ins Leergutkonto?
    MONATLICH und Lieferung ab dem Stichtag des Kunden."""
    if kunde is None or kunde.pfand_abrechnung != PfandAbrechnung.MONATLICH:
        return False
    return kunde.pfand_monatlich_ab is None or leistungsdatum(order) >= kunde.pfand_monatlich_ab


def hat_bewegung(db: Session, order_line_id: UUID) -> bool:
    return db.execute(
        select(LeergutBewegung.id).where(LeergutBewegung.order_line_id == order_line_id).limit(1)
    ).first() is not None


def pfandzeile_fakturiert(db: Session, line: OrderLine) -> bool:
    """Steht diese Bestellposition schon auf einer gültigen Rechnung?

    Rechnung aus Bestellung: über InvoiceLine.order_item_id. Sammelrechnung:
    über invoice_line_sources (Lieferschein der Bestellung) und das Produkt
    der Rechnungszeile. Stornierte Rechnungen zählen nicht — ihr Pfand ist
    wieder offen.
    """
    gueltig = (Invoice.status != InvoiceStatus.STORNIERT, Invoice.invoice_type == InvoiceType.RECHNUNG)
    if db.execute(
        select(InvoiceLine.id)
        .join(Invoice, InvoiceLine.invoice_id == Invoice.id)
        .where(InvoiceLine.order_item_id == line.id, *gueltig)
        .limit(1)
    ).first() is not None:
        return True
    produkt = produkt_der_position(db, line.product_id, line.product_variant_id)
    if produkt is None:
        return False
    return db.execute(
        select(InvoiceLine.id)
        .join(Invoice, InvoiceLine.invoice_id == Invoice.id)
        .join(InvoiceLineSource, InvoiceLineSource.invoice_line_id == InvoiceLine.id)
        .join(DeliveryNote, InvoiceLineSource.delivery_note_id == DeliveryNote.id)
        .where(DeliveryNote.order_id == line.order_id, InvoiceLine.product_id == produkt.id, *gueltig)
        .limit(1)
    ).first() is not None


def _stueck(menge) -> int:
    return int(Decimal(str(menge)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def ausgabe_faellig(db: Session, order: Order, line: OrderLine) -> Optional[Product]:
    """Der Pfandartikel, wenn für diese Position eine AUSGABE fällig ist, sonst None."""
    produkt = produkt_der_position(db, line.product_id, line.product_variant_id)
    if not ist_pfandartikel(produkt) or not im_leergutkonto(order.customer, order):
        return None
    if _stueck(line.quantity) <= 0 or hat_bewegung(db, line.id) or pfandzeile_fakturiert(db, line):
        return None
    return produkt


def buche_ausgaben(db: Session, order: Order, *, erfasst_von: str) -> list[LeergutBewegung]:
    """AUSGABE je fälliger Pfandposition. Idempotent (eine Bewegung je
    Bestellposition), committet nicht."""
    neu = []
    for line in order.lines:
        produkt = ausgabe_faellig(db, order, line)
        if produkt is None:
            continue
        bewegung = LeergutBewegung(
            customer_id=order.customer_id, product_id=produkt.id, art=LeergutArt.AUSGABE,
            menge=_stueck(line.quantity), einzelwert=pfandwert(produkt),
            leistungsdatum=leistungsdatum(order), order_line_id=line.id,
            erfasst_von=erfasst_von,
        )
        db.add(bewegung)
        neu.append(bewegung)
    if neu:
        db.flush()
    return neu


def hat_leergutkonto(db: Session, kunde: Customer) -> bool:
    return kunde.pfand_abrechnung == PfandAbrechnung.MONATLICH or db.execute(
        select(LeergutBewegung.id).where(LeergutBewegung.customer_id == kunde.id).limit(1)
    ).first() is not None


def erfasse(
    db: Session,
    kunde: Customer,
    art: LeergutArt,
    positionen: list[tuple[UUID, int]],
    *,
    tag: Optional[date],
    erfasst_von: Optional[str],
    notiz: Optional[str] = None,
    delivery_note_id: Optional[UUID] = None,
    bereits_berechnet: bool = False,
) -> list[LeergutBewegung]:
    """Rücknahme, Korrektur oder Anfangsbestand von Hand. Committet nicht."""
    if art == LeergutArt.AUSGABE:
        raise LeergutFehler("Ausgaben entstehen aus Lieferungen")
    if not hat_leergutkonto(db, kunde):
        raise LeergutFehler(
            f"{kunde.name} rechnet Pfand nicht über das Leergutkonto ab — "
            "erst die Pfandabrechnung des Kunden auf „monatlich“ stellen"
        )
    tag = tag or heute_berlin()
    if tag > heute_berlin():
        raise LeergutFehler(f"Datum {tag:%d.%m.%Y} liegt in der Zukunft")
    if delivery_note_id is not None:
        note = db.get(DeliveryNote, delivery_note_id)
        if note is None or note.order is None or note.order.customer_id != kunde.id:
            raise LeergutFehler("Lieferschein gehört nicht zu diesem Kunden")
    neu = []
    for product_id, menge in positionen:
        produkt = db.get(Product, product_id)
        if not ist_pfandartikel(produkt):
            raise LeergutFehler("Kein Pfandartikel")
        bewegung = LeergutBewegung(
            customer_id=kunde.id, product_id=produkt.id, art=art, menge=menge,
            einzelwert=pfandwert(produkt), leistungsdatum=tag,
            delivery_note_id=delivery_note_id, erfasst_von=erfasst_von, notiz=notiz,
            bereits_berechnet=bereits_berechnet and art == LeergutArt.ANFANGSBESTAND,
        )
        db.add(bewegung)
        neu.append(bewegung)
    db.flush()
    return neu


# ------------------------------------------------------------ Monatsabrechnung

def monatsgrenzen(monat: Optional[str]) -> tuple[str, date, date]:
    """'YYYY-MM' → (monat, erster, letzter Tag). Ohne Angabe der Vormonat (Berlin)."""
    heute = heute_berlin()
    if monat is None:
        vormonat_letzter = heute.replace(day=1).toordinal() - 1
        erster = date.fromordinal(vormonat_letzter).replace(day=1)
    else:
        jahr, mon = (int(t) for t in monat.split("-"))
        erster = date(jahr, mon, 1)
    letzter = erster.replace(day=monthrange(erster.year, erster.month)[1])
    if erster > heute:
        raise LeergutFehler(f"{erster:%m/%Y} liegt in der Zukunft")
    return f"{erster:%Y-%m}", erster, letzter


def _offener_entwurf(db: Session, customer_id: UUID) -> Optional[Invoice]:
    return db.execute(
        select(Invoice).where(
            Invoice.customer_id == customer_id,
            Invoice.beleg_art == BELEG_ART_LEERGUT,
            Invoice.status == InvoiceStatus.ENTWURF,
        ).limit(1)
    ).scalar_one_or_none()


def _plane(db: Session, monat: Optional[str], customer_ids: Optional[list[UUID]]) -> dict:
    """Was der Lauf abrechnen würde — rechnet nur, schreibt nichts."""
    monat, von, bis = monatsgrenzen(monat)
    kunden: dict = {}

    def eintrag(kunde: Customer) -> dict:
        return kunden.setdefault(kunde.id, {"kunde": kunde, "bewegungen": [], "nachzug": []})

    abfrage = select(LeergutBewegung).where(
        LeergutBewegung.invoice_id.is_(None),
        LeergutBewegung.bereits_berechnet.is_(False),
        LeergutBewegung.leistungsdatum <= bis,
    )
    if customer_ids is not None:
        abfrage = abfrage.where(LeergutBewegung.customer_id.in_(customer_ids))
    for b in db.execute(abfrage).scalars():
        eintrag(db.get(Customer, b.customer_id))["bewegungen"].append(b)

    # Nachzug: geliefert (oder fällig), aber ohne Ausgabe — nur bis heute
    grenze = min(bis, heute_berlin())
    monatskunden = select(Customer).where(Customer.pfand_abrechnung == PfandAbrechnung.MONATLICH)
    if customer_ids is not None:
        monatskunden = monatskunden.where(Customer.id.in_(customer_ids))
    for kunde in db.execute(monatskunden).scalars():
        for order in db.execute(
            select(Order).where(Order.customer_id == kunde.id, Order.status.in_(_NACHZUG_STATUS))
        ).scalars():
            if leistungsdatum(order) > grenze:
                continue
            for line in order.lines:
                produkt = ausgabe_faellig(db, order, line)
                if produkt is not None:
                    eintrag(kunde)["nachzug"].append((order, line, produkt))

    uebersprungen = []
    plaene = []
    for k in sorted(kunden.values(), key=lambda k: k["kunde"].name):
        entwurf = _offener_entwurf(db, k["kunde"].id)
        if entwurf is not None:
            uebersprungen.append({
                "customer_id": k["kunde"].id, "customer_name": k["kunde"].name,
                "grund": f"Leergutbeleg {entwurf.invoice_number} ist noch ein Entwurf — "
                         "erst freigeben oder verwerfen",
            })
            continue
        positionen: dict = {}
        for b in k["bewegungen"]:
            p = positionen.setdefault((b.product_id, b.einzelwert), {
                "produkt": b.product, "aus": 0, "zurueck": 0})
            if b.art.vorzeichen > 0:
                p["aus"] += b.menge
            else:
                p["zurueck"] += b.menge
        for order, line, produkt in k["nachzug"]:
            p = positionen.setdefault((produkt.id, pfandwert(produkt)), {
                "produkt": produkt, "aus": 0, "zurueck": 0})
            p["aus"] += _stueck(line.quantity)
        tage = [b.leistungsdatum for b in k["bewegungen"]] + [leistungsdatum(o) for o, _, _ in k["nachzug"]]
        plaene.append({**k, "positionen": positionen, "von": min([von, *tage]), "bis": bis})
    return {"monat": monat, "von": von, "bis": bis, "plaene": plaene, "uebersprungen": uebersprungen}


def vorschau(db: Session, monat: Optional[str], customer_ids: Optional[list[UUID]]) -> dict:
    plan = _plane(db, monat, customer_ids)
    kunden = []
    for p in plan["plaene"]:
        positionen = []
        for (product_id, wert), pos in sorted(p["positionen"].items(), key=lambda e: e[1]["produkt"].name):
            positionen.append({
                "product_id": product_id, "artikel": pos["produkt"].name, "einzelwert": wert,
                "ausgegeben": pos["aus"], "zurueckgenommen": pos["zurueck"],
                "betrag_netto": (pos["aus"] - pos["zurueck"]) * wert,
            })
        summe = sum((x["betrag_netto"] for x in positionen), Decimal("0.00"))
        kunden.append({
            "customer_id": p["kunde"].id, "customer_name": p["kunde"].name,
            "pfand_abrechnung": p["kunde"].pfand_abrechnung,
            "leistungszeitraum": [p["von"], p["bis"]],
            "positionen": positionen, "summe_netto": summe, "minderung": summe < 0,
            "nachzug": [{"order_number": o.order_number, "leistungsdatum": leistungsdatum(o),
                         "artikel": produkt.name, "menge": _stueck(l.quantity)}
                        for o, l, produkt in p["nachzug"]],
        })
    return {"monat": plan["monat"], "period_from": plan["von"], "period_to": plan["bis"],
            "kunden": kunden, "uebersprungen": plan["uebersprungen"]}


def belege_anlegen(
    db: Session, monat: Optional[str], customer_ids: Optional[list[UUID]], *, erfasst_von: Optional[str],
) -> tuple[list[Invoice], list[dict]]:
    """Je Kunde ein Leergutbeleg als ENTWURF. Bucht den Nachzug, reserviert
    die Bewegungen (invoice_id). Committet nicht."""
    from app.services.invoice_service import InvoiceService

    plan = _plane(db, monat, customer_ids)
    service = InvoiceService(db)
    belege = []
    for p in plan["plaene"]:
        kunde = p["kunde"]
        bewegungen = list(p["bewegungen"])
        for order, line, produkt in p["nachzug"]:
            nachgebucht = LeergutBewegung(
                customer_id=kunde.id, product_id=produkt.id, art=LeergutArt.AUSGABE,
                menge=_stueck(line.quantity), einzelwert=pfandwert(produkt),
                leistungsdatum=leistungsdatum(order), order_line_id=line.id,
                erfasst_von=SYSTEM_MONATSABRECHNUNG,
                notiz=f"Nachgebucht aus {order.order_number} ({erfasst_von or 'unbekannt'})",
            )
            db.add(nachgebucht)
            bewegungen.append(nachgebucht)
        db.flush()

        beleg = service.create_invoice(
            customer_id=kunde.id,
            header_text=(f"Leergutabrechnung — Leistungszeitraum "
                         f"{p['von']:%d.%m.%Y}–{p['bis']:%d.%m.%Y}"),
        )
        # Kein Jahresrabatt auf Pfand: create_invoice setzt ihn sonst
        # automatisch (eine übergebene 0 gilt als "nicht überschrieben").
        beleg.discount_percent = Decimal("0")
        beleg.beleg_art = BELEG_ART_LEERGUT
        beleg.service_period_start = p["von"]
        beleg.service_period_end = p["bis"]
        for (product_id, wert), pos in sorted(p["positionen"].items(), key=lambda e: e[1]["produkt"].name):
            produkt = pos["produkt"]
            for text, menge in (("Leergut ausgegeben", pos["aus"]), ("Leergut zurückgenommen", -pos["zurueck"])):
                if menge:
                    service.add_line(
                        invoice_id=beleg.id, description=f"{text}: {produkt.name}",
                        quantity=Decimal(menge), unit="STK", unit_price=wert,
                        product_id=produkt.id, sku=produkt.sku, tax_rate=produkt.tax_rate,
                    )
        for b in bewegungen:
            b.invoice_id = beleg.id
        service.recalculate_totals(beleg)
        belege.append(beleg)
    return belege, plan["uebersprungen"]


# ------------------------------------------------------------ Schutz des Belegs

#: Antwort (409) auf Änderungen an Positionen oder Kunde eines Leergutbelegs
LEERGUTBELEG_FEST = (
    "Leergutbeleg: Positionen und Kunde ergeben sich aus dem Leergutkonto und lassen "
    "sich hier nicht ändern. Zum Korrigieren den Entwurf verwerfen, im Leergutkonto "
    "korrigieren und die Leergutabrechnung neu anlegen."
)


def ist_leergutbeleg(invoice: Optional[Invoice]) -> bool:
    """Leergutbeleg oder dessen Stornorechnung (cancel_invoice übernimmt beleg_art)."""
    return invoice is not None and invoice.beleg_art == BELEG_ART_LEERGUT


def gib_bewegungen_frei(db: Session, invoice_id: UUID) -> int:
    """Storno oder Verwerfen eines Leergutbelegs: seine Bewegungen sind
    wieder offen, der nächste Monatslauf rechnet sie ab."""
    bewegungen = db.execute(
        select(LeergutBewegung).where(LeergutBewegung.invoice_id == invoice_id)
    ).scalars().all()
    for b in bewegungen:
        b.invoice_id = None
    return len(bewegungen)


def mailtext(invoice: Invoice, *, zusatz: str, gruss: str, zahlungszeile: str) -> tuple[str, str]:
    """Betreff und Text der Mail zu einem Leergutbeleg (nicht zu seiner
    Stornorechnung — die schreibt send_invoice_email selbst).

    zusatz (" — Firmenname") und gruss kommen aus app.services.belegversand
    (Q2), zahlungszeile aus sepa_service.zahlungszeile_fuer_mail (Q5) — wie
    in der Rechnungsmail. Saldo > 0: Betrag und Zahlungszeile; < 0: der
    Betrag steht dem Kunden zu (Minderung); 0: nichts zu zahlen.
    """
    kunde = invoice.customer.name if invoice.customer else ""
    betreff = f"Leergutabrechnung {invoice.invoice_number}{zusatz}"
    if invoice.total > 0:
        mitte = (
            f"anbei finden Sie die Leergutabrechnung {invoice.invoice_number} über\n"
            f"{invoice.total:.2f} {invoice.currency}.\n\n"
            f"{zahlungszeile}\n\n"
        )
    elif invoice.total < 0:
        mitte = (
            f"anbei finden Sie die Leergutabrechnung {invoice.invoice_number}.\n"
            f"Für zurückgenommenes Leergut steht Ihnen ein Betrag von "
            f"{abs(invoice.total):.2f} {invoice.currency} zu.\n\n"
        )
    else:
        mitte = (
            f"anbei finden Sie die Leergutabrechnung {invoice.invoice_number}.\n"
            f"Ausgegebenes und zurückgenommenes Leergut gleichen sich aus — es ist nichts zu zahlen.\n\n"
        )
    return betreff, f"Sehr geehrte Damen und Herren bei {kunde},\n\n" + mitte + gruss
