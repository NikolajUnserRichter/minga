from typing import Optional
"""
Rechnungs-Service - Business Logic für Rechnungen
Mit deutscher MwSt-Berechnung und DATEV-Export
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from io import StringIO
import csv
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_

from app.models.invoice import (
    Invoice, InvoiceLine, InvoiceLineSource, Payment,
    InvoiceStatus, InvoiceType, TaxRate, PaymentMethod,
    generate_invoice_number, STANDARD_ACCOUNTS
)
from app.models.customer import Customer, AddressType, PfandAbrechnung
from app.models.order import Order, OrderLine, OrderStatus
from app.models.product import Product
from app.models.documents import DeliveryNote
from app.models.enums import DeliveryNoteStatus
from app.services.steuersatz import produkt_der_position, steuersatz_der_position
from app.services.datev_service import erloeskonto_fuer


def _euro(betrag: Decimal) -> str:
    """Betrag mit deutschem Dezimalkomma: Decimal("5") -> "5,00 €"."""
    return f"{Decimal(betrag):.2f} €".replace(".", ",")


class BestellungStorniert(ValueError):
    """Eine stornierte Bestellung darf nicht berechnet werden."""


class BereitsAbgerechnet(ValueError):
    """Zur Bestellung gibt es schon eine nicht stornierte Rechnung.

    Unterklasse von ValueError: bestehende Aufrufer, die ValueError fangen,
    funktionieren weiter. Die API macht daraus 409 statt 400.
    """


def waehle_vertreter(lieferscheine):
    """Der Lieferschein, der eine Bestellung in der Abrechnung vertritt.

    Der älteste quittierte (Liefernachweis, tatsächliches Lieferdatum), sonst
    der älteste überhaupt. Die Nummer LS-JJJJMMTT-NNNN sortiert chronologisch
    und ist — anders als created_at — nie mal naiv, mal mit Zeitzone.

    Genau EIN Vertreter je Bestellung: die PDF-Tabelle "Enthaltene
    Lieferscheine" (pdf_service) zeigt je Lieferschein die volle
    Bestellsumme; zwei Einträge würden sie doppelt ausweisen.
    """
    if not lieferscheine:
        return None
    return min(
        lieferscheine,
        key=lambda n: (n.status != DeliveryNoteStatus.GELIEFERT, n.delivery_note_number),
    )


def ist_clearing_pfand(db: Session, kunde: Optional[Customer], line: OrderLine) -> bool:
    """Gehört diese Bestellposition NICHT auf die Rechnung?

    Kunden mit pfand_abrechnung = KEINE (z. B. Ökoring, Bodan) rechnen das
    Pfand für IFCO-Kisten über das IFCO-Clearing ab, nicht über Minga Greens.
    Die Pfandposition bleibt auf Bestellung und Lieferschein (Nachweis der
    gelieferten Kisten), fehlt aber auf der Rechnung. Erkannt wird Pfand am
    Produktstamm (is_deposit) — Freitext-Pfandzeilen ohne Produkt bleiben
    stehen, weil nichts sie als Pfand ausweist. MONATLICH (Leergutkonto)
    kommt mit Paket 3 und muss hier ergänzt werden.
    """
    if kunde is None or kunde.pfand_abrechnung != PfandAbrechnung.KEINE:
        return False
    produkt = produkt_der_position(db, line.product_id, line.product_variant_id)
    return produkt is not None and bool(produkt.is_deposit)


def netto_je_lieferschein(db: Session, invoice: Invoice, lieferscheine: list[DeliveryNote]) -> dict[UUID, Decimal]:
    """Abgerechneter Nettobetrag je Lieferschein dieser Rechnung.

    Für die Anlage "Enthaltene Lieferscheine" im Rechnungs-PDF und für
    GET /invoices/{id}/delivery-notes. Gerechnet wird aus den Positionen
    DIESER Rechnung, nicht aus der Bestellung: Clearing-Pfand steht auf
    Bestellung und Lieferschein, aber nicht auf der Rechnung — die Anlage
    muss zur Rechnung passen. Bewusst nicht über ist_clearing_pfand: Das PDF
    entsteht bei jedem Abruf neu, ein später geändertes Kundenfeld
    änderte sonst die Anlage einer versendeten Rechnung (GoBD).

    - Sammelrechnung: invoice_line_sources (Menge je Lieferschein) mal
      Einzelpreis der Position, nach Positionsrabatt.
    - Rechnung aus Bestellung (S6 hängt genau einen Lieferschein an, ohne
      invoice_line_sources): die Positionen, deren order_item_id zur
      Bestellung des Lieferscheins gehört.
    Der Rabatt auf die ganze Rechnung (Kopfrabatt) bleibt wie bisher außen vor.
    """
    betraege = {n.id: Decimal("0") for n in lieferscheine}
    mit_quelle = set()
    quellen = db.execute(
        select(InvoiceLineSource.delivery_note_id, InvoiceLineSource.quantity,
               InvoiceLine.unit_price, InvoiceLine.discount_percent)
        .join(InvoiceLine, InvoiceLineSource.invoice_line_id == InvoiceLine.id)
        .where(InvoiceLine.invoice_id == invoice.id)
    ).all()
    for note_id, menge, preis, rabatt in quellen:
        if note_id in betraege:
            betraege[note_id] += menge * preis * (1 - (rabatt or Decimal("0")) / 100)
            mit_quelle.add(note_id)
    for note in lieferscheine:
        if note.id in mit_quelle or note.order is None:
            continue
        bestellzeilen = {l.id for l in note.order.lines}
        betraege[note.id] = sum(
            (l.line_total for l in invoice.lines if l.order_item_id in bestellzeilen),
            Decimal("0"),
        )
    return {nid: b.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) for nid, b in betraege.items()}


class InvoiceService:
    """Service für Rechnungs-Operationen"""

    def __init__(self, db: Session):
        self.db = db

    def create_invoice(
        self,
        customer_id: UUID,
        invoice_date: Optional[date] = None,
        delivery_date: Optional[date] = None,
        order_id: Optional[UUID] = None,
        invoice_type: InvoiceType = InvoiceType.RECHNUNG,
        original_invoice_id: Optional[UUID] = None,
        discount_percent: Decimal = Decimal("0"),
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None,
        internal_notes: Optional[str] = None,
        due_date: Optional[date] = None,
        buchungskonto: Optional[str] = None,
    ) -> Invoice:
        """
        Erstellt eine neue Rechnung.
        """
        customer = self.db.get(Customer, customer_id)
        if not customer:
            raise ValueError("Kunde nicht gefunden")

        # Doppelabrechnung: je Bestellung höchstens eine nicht stornierte
        # Rechnung. Gilt für "Rechnung aus Bestellung" und für manuell
        # angelegte Rechnungen mit Bestellbezug. Vor dem Anlegen der neuen
        # Rechnung — danach fände die Abfrage sie selbst.
        if order_id is not None and invoice_type == InvoiceType.RECHNUNG:
            vorhandene = self.aktive_rechnung_zur_bestellung(order_id)
            if vorhandene is not None:
                order = self.db.get(Order, order_id)
                raise BereitsAbgerechnet(
                    f"Zur Bestellung {order.order_number if order else order_id} gibt es "
                    f"bereits die Rechnung {vorhandene.invoice_number} "
                    f"({vorhandene.status.value}). Eine zweite Rechnung ist nicht möglich. "
                    f"Zur Korrektur die Rechnung stornieren und danach neu ausstellen."
                )

        # Rechnungsnummer generieren
        invoice_number = self._generate_next_invoice_number(invoice_type)

        # Fälligkeitsdatum berechnen
        inv_date = invoice_date or date.today()
        if due_date is None:
            due_date = inv_date + timedelta(days=customer.payment_days)

        # Customer-Default-Rabatt anwenden, falls nicht überschrieben
        if discount_percent == Decimal("0") and getattr(customer, "discount_percent", 0):
            discount_percent = customer.discount_percent

        # Adressen als Snapshot speichern
        billing_addr = None
        shipping_addr = None
        if customer.billing_address:
            billing_addr = {
                "name": customer.billing_address.name or customer.name,
                "strasse": customer.billing_address.strasse,
                "hausnummer": customer.billing_address.hausnummer,
                "plz": customer.billing_address.plz,
                "ort": customer.billing_address.ort,
                "land": customer.billing_address.land,
            }
        if customer.shipping_address:
            shipping_addr = {
                "name": customer.shipping_address.name or customer.name,
                "strasse": customer.shipping_address.strasse,
                "hausnummer": customer.shipping_address.hausnummer,
                "plz": customer.shipping_address.plz,
                "ort": customer.shipping_address.ort,
                "land": customer.shipping_address.land,
            }

        invoice = Invoice(
            invoice_number=invoice_number,
            invoice_type=invoice_type,
            customer_id=customer_id,
            order_id=order_id,
            original_invoice_id=original_invoice_id,
            invoice_date=inv_date,
            delivery_date=delivery_date,
            due_date=due_date,
            status=InvoiceStatus.ENTWURF,
            billing_address=billing_addr,
            shipping_address=shipping_addr,
            discount_percent=discount_percent,
            header_text=header_text,
            footer_text=footer_text,
            internal_notes=internal_notes,
            # Kein Kopf-Default mehr: das Erlöskonto steht je Position
            # (InvoiceLine.buchungskonto, aus dem Steuersatz). Der frühere
            # Default 8300 ließ im DATEV-Export 19 % auf 8300 landen.
            buchungskonto=buchungskonto,
        )

        self.db.add(invoice)
        self.db.flush()

        return invoice

    def add_line(
        self,
        invoice_id: UUID,
        description: str,
        quantity: Decimal,
        unit: str,
        unit_price: Decimal,
        product_id: Optional[UUID] = None,
        sku: Optional[str] = None,
        discount_percent: Decimal = Decimal("0"),
        tax_rate: TaxRate = TaxRate.REDUZIERT,
        order_item_id: Optional[UUID] = None,
        harvest_batch_ids: Optional[list[UUID]] = None,
        buchungskonto: Optional[str] = None,
    ) -> InvoiceLine:
        """
        Fügt eine Position zur Rechnung hinzu.
        """
        invoice = self.db.get(Invoice, invoice_id)
        if not invoice:
            raise ValueError("Rechnung nicht gefunden")

        if invoice.status != InvoiceStatus.ENTWURF:
            raise ValueError("Nur Entwürfe können bearbeitet werden")

        # Position ermitteln
        max_pos = self.db.execute(
            select(func.max(InvoiceLine.position))
            .where(InvoiceLine.invoice_id == invoice_id)
        ).scalar() or 0

        # Buchungskonto basierend auf Steuersatz — dieselbe Regel wie der
        # DATEV-Export (datev_service.erloeskonto_fuer)
        if not buchungskonto:
            buchungskonto = erloeskonto_fuer(tax_rate)

        line = InvoiceLine(
            invoice_id=invoice_id,
            position=max_pos + 1,
            product_id=product_id,
            description=description,
            sku=sku,
            quantity=quantity,
            unit=unit,
            unit_price=unit_price,
            discount_percent=discount_percent,
            tax_rate=tax_rate,
            order_item_id=order_item_id,
            harvest_batch_ids=[str(h) for h in harvest_batch_ids] if harvest_batch_ids else None,
            buchungskonto=buchungskonto,
            is_deposit=True if (product_id and self.db.get(Product, product_id).is_deposit) else False
        )

        # Zeilenbetrag berechnen
        line.calculate_line_total()

        self.db.add(line)
        # Summen über ALLE Positionen — invoice.lines trägt nach dem ersten
        # Zugriff sonst den alten Stand (siehe recalculate_totals).
        self.recalculate_totals(invoice)

        return line

    def recalculate_totals(self, invoice: Invoice) -> Invoice:
        """Summen einer Rechnung aus dem aktuellen Stand ihrer Positionen.

        Pflicht nach jedem Anlegen oder Löschen einer Position. Die Session
        läuft mit autoflush=False, und invoice.lines bleibt nach dem ersten
        Zugriff geladen: Positionen, die danach über invoice_id angelegt oder
        per db.delete entfernt werden, sähe calculate_totals sonst nicht.
        Deshalb erst schreiben, dann die Positionen neu laden, dann rechnen.
        """
        self.db.flush()
        self.db.refresh(invoice, ["lines"])
        invoice.calculate_totals()
        return invoice

    def create_invoice_from_order(self, order_id: UUID) -> Invoice:
        """
        Erstellt eine Rechnung aus einer Bestellung.

        - Steuersatz: bei Positionen mit Produkt (direkt oder über die
          Variante) der Satz des Produktstamms, nicht der gespeicherte Satz
          der Bestellposition — den setzte das Bestellformular bis 08.10.2026
          fest auf 7 % (A3). Freitextpositionen behalten ihren Satz.
        - Positionsrabatt wird übernommen (fehlte bisher still).
        - Leistungsdatum: das tatsächliche Lieferdatum des Lieferscheins,
          ersatzweise das tatsächliche oder das Wunschlieferdatum der
          Bestellung — dieselbe Regel wie die Sammelrechnung.
        """
        order = self.db.get(Order, order_id)
        if not order:
            raise ValueError("Bestellung nicht gefunden")
        if order.status == OrderStatus.STORNIERT:
            raise BestellungStorniert("Bestellung ist storniert")

        # Pfand über IFCO-Clearing bleibt auf dem Lieferschein, nicht auf der
        # Rechnung. Vor dem Anlegen prüfen: eine reine Pfandbestellung ergäbe
        # sonst eine leere Rechnung (und verbrauchte eine Nummer).
        positionen = [l for l in order.lines if not ist_clearing_pfand(self.db, order.customer, l)]
        if order.lines and not positionen:
            raise ValueError(
                "Die Bestellung enthält nur Pfandpositionen. Dieser Kunde rechnet Pfand "
                "über IFCO-Clearing ab — es gibt nichts zu fakturieren."
            )

        offene = self.db.execute(
            select(DeliveryNote).where(
                DeliveryNote.order_id == order_id,
                DeliveryNote.invoice_id.is_(None),
            )
        ).scalars().all()
        vertreter = waehle_vertreter(offene)
        leistungsdatum = (
            (vertreter.actual_delivery_date if vertreter is not None else None)
            or order.actual_delivery_date or order.requested_delivery_date
        )

        # Rechnung erstellen
        invoice = self.create_invoice(
            customer_id=order.customer_id,
            order_id=order_id,
            delivery_date=leistungsdatum,
        )

        # Positionen aus Bestellung übernehmen
        for line in positionen:
            # Beschreibung wie bisher aus dem direkt verknüpften Produkt — bei
            # reinen Variantenpositionen bleibt der gespeicherte Name stehen.
            direkt = self.db.get(Product, line.product_id) if line.product_id else None
            # Pfandkennzeichen und SKU aus dem Produkt hinter der Position,
            # auch wenn nur die Variante gesetzt ist.
            produkt = produkt_der_position(self.db, line.product_id, line.product_variant_id)

            self.add_line(
                invoice_id=invoice.id,
                description=direkt.name if direkt else (line.beschreibung or f"Position {line.id}"),
                quantity=line.quantity,
                unit=line.unit,
                unit_price=line.unit_price or Decimal("0"),
                product_id=produkt.id if produkt else None,
                sku=produkt.sku if produkt else None,
                discount_percent=line.discount_percent or Decimal("0"),
                # Dieselbe Satzregel wie in der Bestellung (Task 1) — nicht hier
                # nachgebaut, damit sie nur an einer Stelle steht.
                tax_rate=steuersatz_der_position(
                    self.db, line.product_id, line.product_variant_id, line.tax_rate
                ),
                order_item_id=line.id,
                harvest_batch_ids=[line.harvest_id] if line.harvest_id else None,
            )

        # Lines-Relationship neu laden + Summen final berechnen
        # (add_line() callte calculate_totals() pro Line, aber invoice.lines
        # ist nach jedem flush stale — der letzte Aufruf hätte nur eine Line gesehen)
        self.db.refresh(invoice, ["lines"])
        invoice.calculate_totals()

        # Abrechnungsstatus am Lieferschein (R2.5). Ohne diese Zuordnung sah
        # der Sammellauf die Bestellung als offen. Nur ein noch nicht
        # zugeordneter Lieferschein, genau einer je Bestellung.
        if vertreter is not None:
            vertreter.invoice_id = invoice.id
            self.db.flush()

        return invoice

    def aktive_rechnung_zur_bestellung(
        self, order_id: UUID, *, ohne_rechnung_id: Optional[UUID] = None,
        nur_festgeschrieben: bool = False,
    ) -> Optional[Invoice]:
        """Die nicht stornierte Rechnung, in der die Bestellung steckt, sonst None.

        Zwei Wege führen von der Bestellung zur Rechnung:
        - Rechnung aus Bestellung: Invoice.order_id
        - Sammelrechnung: ein Lieferschein der Bestellung trägt invoice_id
        Nur Typ RECHNUNG zählt: Gutschriften (Storno), Proforma und
        Abschlagsrechnungen sperren nicht.
        """
        return self.db.execute(
            select(Invoice)
            .where(
                Invoice.invoice_type == InvoiceType.RECHNUNG,
                Invoice.status != InvoiceStatus.STORNIERT,
                Invoice.id != ohne_rechnung_id if ohne_rechnung_id else True,
                Invoice.status != InvoiceStatus.ENTWURF if nur_festgeschrieben else True,
                or_(
                    Invoice.order_id == order_id,
                    Invoice.id.in_(
                        select(DeliveryNote.invoice_id).where(
                            DeliveryNote.order_id == order_id,
                            DeliveryNote.invoice_id.is_not(None),
                        )
                    ),
                ),
            )
            .order_by(Invoice.invoice_number)
            .limit(1)
        ).scalars().first()

    def abgerechnete_bestellungen(self) -> set[UUID]:
        """IDs aller Bestellungen mit nicht stornierter Rechnung.

        Dieselbe Regel wie aktive_rechnung_zur_bestellung, als Menge für den
        Sammellauf (eine Abfrage je Weg statt einer je Bestellung).
        """
        aktiv = (
            Invoice.invoice_type == InvoiceType.RECHNUNG,
            Invoice.status != InvoiceStatus.STORNIERT,
        )
        ueber_bestellung = self.db.execute(
            select(Invoice.order_id).where(Invoice.order_id.is_not(None), *aktiv)
        ).scalars().all()
        ueber_lieferschein = self.db.execute(
            select(DeliveryNote.order_id)
            .join(Invoice, DeliveryNote.invoice_id == Invoice.id)
            .where(*aktiv)
        ).scalars().all()
        return set(ueber_bestellung) | set(ueber_lieferschein)

    def pruefe_festschreibung(self, invoice: Invoice) -> None:
        order_ids = set(self.db.execute(
            select(DeliveryNote.order_id).where(DeliveryNote.invoice_id == invoice.id)
        ).scalars().all())
        if invoice.order_id is not None:
            order_ids.add(invoice.order_id)
        for order_id in sorted(order_ids):
            order = self.db.execute(
                select(Order).where(Order.id == order_id).with_for_update()
            ).scalar_one_or_none()
            andere = self.aktive_rechnung_zur_bestellung(
                order_id, ohne_rechnung_id=invoice.id, nur_festgeschrieben=True,
            )
            if andere is not None:
                raise BereitsAbgerechnet(
                    f"Zur Bestellung {order.order_number if order else order_id} gibt es schon die Rechnung "
                    f"{andere.invoice_number} — diesen Entwurf verwerfen oder die andere Rechnung erst stornieren"
                )

    def finalize_invoice(self, invoice_id: UUID) -> Invoice:
        """
        Finalisiert eine Rechnung (Entwurf -> Offen).
        """
        invoice = self.db.get(Invoice, invoice_id)
        if not invoice:
            raise ValueError("Rechnung nicht gefunden")

        if invoice.status != InvoiceStatus.ENTWURF:
            raise ValueError("Nur Entwürfe können finalisiert werden")

        self.pruefe_festschreibung(invoice)

        if not invoice.lines:
            raise ValueError("Rechnung hat keine Positionen")

        # Summen final berechnen
        invoice.calculate_totals()

        # Status ändern
        invoice.status = InvoiceStatus.OFFEN
        invoice.sent_at = datetime.now(timezone.utc)

        return invoice

    def record_payment(
        self,
        invoice_id: UUID,
        amount: Decimal,
        payment_date: Optional[date] = None,
        payment_method: PaymentMethod = PaymentMethod.UEBERWEISUNG,
        reference: Optional[str] = None,
        bank_reference: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Payment:
        """
        Erfasst eine Zahlung für eine Rechnung.
        """
        invoice = self.db.get(Invoice, invoice_id)
        if not invoice:
            raise ValueError("Rechnung nicht gefunden")

        if invoice.status == InvoiceStatus.STORNIERT:
            raise ValueError("Stornierte Rechnungen können nicht bezahlt werden")

        payment = Payment(
            invoice_id=invoice_id,
            payment_date=payment_date or date.today(),
            amount=amount,
            payment_method=payment_method,
            reference=reference,
            bank_reference=bank_reference,
            notes=notes,
        )

        self.db.add(payment)
        self.db.flush()

        # Bezahlten Betrag aktualisieren
        invoice.paid_amount = sum(p.amount for p in invoice.payments)

        # Status aktualisieren
        if invoice.paid_amount >= invoice.total:
            invoice.status = InvoiceStatus.BEZAHLT
        elif invoice.paid_amount > 0:
            invoice.status = InvoiceStatus.TEILBEZAHLT

        return payment

    def cancel_invoice(
        self,
        invoice_id: UUID,
        reason: str,
        create_credit_note: bool = True
    ) -> tuple[Invoice, Optional[Invoice]]:
        """
        Storniert eine Rechnung und erstellt optional eine Stornorechnung.

        Die Stornorechnung ist das exakte Spiegelbild des Originals: gleiche
        Positionen mit negativer Menge, gleiche Steuersätze, Konten,
        Pfandkennzeichen und derselbe Rechnungsrabatt. Original und
        Stornorechnung gleichen sich aus und stehen danach beide auf
        STORNIERT — damit fallen sie aus Überfälligkeit, Mahnlauf, offenen
        Posten und Umsatzauswertungen heraus.
        """
        invoice = self.db.get(Invoice, invoice_id)
        if not invoice:
            raise ValueError("Rechnung nicht gefunden")

        # R1.7 vor der Statusprüfung: auch die Stornorechnung steht auf
        # STORNIERT, die Meldung soll trotzdem den eigentlichen Grund nennen.
        # Der Storno eines Stornos würde die Beträge wieder aufleben lassen —
        # der Weg ist eine neue, korrigierte Rechnung.
        if invoice.invoice_type == InvoiceType.GUTSCHRIFT:
            raise ValueError("Eine Stornorechnung kann nicht storniert werden")

        if invoice.status == InvoiceStatus.STORNIERT:
            raise ValueError("Rechnung ist bereits storniert")

        # Ein Entwurf ging nie an den Kunden — eine Stornorechnung dazu wäre
        # ein Beleg über nichts. Verwerfen geht nur ohne Stornorechnung.
        if invoice.status == InvoiceStatus.ENTWURF and create_credit_note:
            raise ValueError(
                "Ein Entwurf wurde nie ausgestellt und bekommt keine Stornorechnung — "
                "Entwurf korrigieren und finalisieren oder ohne Stornorechnung verwerfen"
            )

        # DATEV kennt die Rechnung schon. Ohne Stornorechnung fiele sie aus
        # jedem weiteren Export, ihr Umsatz bliebe in DATEV still stehen.
        if invoice.datev_exported and not create_credit_note:
            raise ValueError(
                "Die Rechnung wurde bereits an DATEV exportiert und kann nur mit "
                "Stornorechnung storniert werden"
            )

        # Original stornieren
        invoice.status = InvoiceStatus.STORNIERT
        invoice.internal_notes = f"{invoice.internal_notes or ''}\n\nStorniert: {reason}".strip()

        # Bereits eingegangenes Geld bleibt am stornierten Beleg stehen — es
        # gehört auf die Neuausstellung oder zurück an den Kunden. Das muss in
        # die Akte; die API meldet es zusätzlich (storno_warnungen).
        if invoice.paid_amount and invoice.paid_amount > 0:
            invoice.internal_notes += (
                f"\nBei Storno bereits gezahlt: {_euro(invoice.paid_amount)} — "
                "auf die Neuausstellung umbuchen oder erstatten."
            )

        # R1.6: zugeordnete Lieferscheine wieder abrechenbar machen — sie
        # gehören in die nächste, korrigierte (Sammel-)Rechnung.
        from app.models.documents import DeliveryNote
        for note in self.db.execute(
            select(DeliveryNote).where(DeliveryNote.invoice_id == invoice_id)
        ).scalars().all():
            note.invoice_id = None

        credit_note = None
        if create_credit_note and invoice.total > 0:
            credit_note = self.create_invoice(
                customer_id=invoice.customer_id,
                invoice_type=InvoiceType.GUTSCHRIFT,
                original_invoice_id=invoice_id,
                delivery_date=invoice.delivery_date,
                # Nichts zu zahlen: fällig am Ausstellungstag.
                due_date=date.today(),
                buchungskonto=invoice.buchungskonto,
                header_text=(
                    f"Stornorechnung zur Rechnung Nr. {invoice.invoice_number} "
                    f"vom {invoice.invoice_date.strftime('%d.%m.%Y')}"
                ),
            )
            # Der Grund gehört an beide Belege — beim Prüfen liegt oft nur einer vor.
            credit_note.internal_notes = f"Storno zu {invoice.invoice_number}: {reason}"
            # Spiegelbild: create_invoice setzt sonst den heutigen Kundenrabatt.
            credit_note.discount_percent = invoice.discount_percent
            credit_note.service_period_start = invoice.service_period_start
            credit_note.service_period_end = invoice.service_period_end

            # Positionen 1:1 mit negativer Menge kopieren. Bewusst nicht über
            # add_line: die Stornorechnung muss Steuersatz, Konto und
            # Pfandkennzeichen des Originals tragen, nicht den heutigen
            # Produktstamm.
            for line in invoice.lines:
                self.db.add(InvoiceLine(
                    invoice_id=credit_note.id,
                    position=line.position,
                    product_id=line.product_id,
                    description=line.description,
                    sku=line.sku,
                    quantity=-line.quantity,
                    unit=line.unit,
                    unit_price=line.unit_price,
                    discount_percent=line.discount_percent,
                    tax_rate=line.tax_rate,
                    buchungskonto=line.buchungskonto,
                    is_deposit=line.is_deposit,
                ))
            self.recalculate_totals(credit_note)

            # Ausgeglichen: STORNIERT ist der einzige bestehende Status, den
            # Überfälligkeit, Mahnlauf, offene Posten, Umsatzauswertungen,
            # Zahlungserfassung und lexoffice-Übertragung gleichermaßen
            # auslassen. PDF und Versand per API bleiben möglich
            # (invoices.py /pdf und /send).
            credit_note.status = InvoiceStatus.STORNIERT
            credit_note.sent_at = datetime.now(timezone.utc)

        return invoice, credit_note

    @staticmethod
    def storno_warnungen(invoice: Invoice) -> list[str]:
        """Was der Storno nicht selbst lösen kann — die Oberfläche zeigt es an."""
        warnungen = []
        if invoice.paid_amount and invoice.paid_amount > 0:
            warnungen.append(
                f"Auf {invoice.invoice_number} sind bereits {_euro(invoice.paid_amount)} gezahlt. "
                "Die Zahlung bleibt am stornierten Beleg stehen — bei der Neuausstellung "
                "als Zahlung erfassen oder dem Kunden erstatten."
            )
        if invoice.lexoffice_id:
            warnungen.append(
                f"{invoice.invoice_number} wurde an lexoffice übertragen. Dort von Hand "
                "stornieren bzw. den Entwurf löschen — die Stornorechnung wird nicht übertragen."
            )
        return warnungen

    #: Rechnung ist überfällig, wenn sie raus ist und noch Geld offen steht.
    #: ENTWURF (nie versendet), BEZAHLT und STORNIERT gehören nicht dazu.
    OVERDUE_STATES = (
        InvoiceStatus.OFFEN,
        InvoiceStatus.TEILBEZAHLT,
        InvoiceStatus.UEBERFAELLIG,
        InvoiceStatus.MAHNVERFAHREN,
    )

    def check_overdue_invoices(self) -> list[Invoice]:
        """
        Prüft und markiert überfällige Rechnungen.

        Gibt ALLE überfälligen Rechnungen zurück, nicht nur die in diesem
        Aufruf frisch markierten: sonst leert sich die Liste beim zweiten
        Aufruf, weil die Rechnungen dann schon UEBERFAELLIG sind und nicht
        mehr auf OFFEN matchen — der Reiter "Überfällig" und die Kennzahl
        standen dadurch auf 0, während die Rechnung unter "Alle" sichtbar
        als überfällig markiert war.
        """
        today = date.today()
        overdue = self.db.execute(
            select(Invoice)
            .where(
                Invoice.status.in_(self.OVERDUE_STATES),
                Invoice.due_date < today,
                # Eine Gutschrift/Stornorechnung ist nie überfällig — auch
                # kein Altbestand, den der frühere Storno auf OFFEN setzte.
                Invoice.invoice_type != InvoiceType.GUTSCHRIFT,
            )
        ).scalars().all()

        for invoice in overdue:
            # TEILBEZAHLT und MAHNVERFAHREN behalten ihren Status — er sagt
            # mehr aus als "überfällig" und geht sonst verloren.
            if invoice.status == InvoiceStatus.OFFEN:
                invoice.status = InvoiceStatus.UEBERFAELLIG

        return overdue

    # export_datev wurde in DatevService ausgelagert


    def get_revenue_summary(self, from_date: date, to_date: date) -> dict:
        """
        Umsatzübersicht für Zeitraum.
        """
        result = self.db.execute(
            select(
                func.sum(Invoice.total).label("total"),
                func.sum(Invoice.paid_amount).label("paid"),
                func.count(Invoice.id).label("count")
            )
            .where(
                Invoice.invoice_date.between(from_date, to_date),
                Invoice.status.notin_([InvoiceStatus.ENTWURF, InvoiceStatus.STORNIERT])
            )
        ).first()

        open_amount = self.db.execute(
            select(func.sum(Invoice.total - Invoice.paid_amount))
            .where(
                Invoice.status.in_([InvoiceStatus.OFFEN, InvoiceStatus.TEILBEZAHLT, InvoiceStatus.UEBERFAELLIG])
            )
        ).scalar() or Decimal("0")

        return {
            "total_revenue": result.total or Decimal("0"),
            "total_paid": result.paid or Decimal("0"),
            "invoice_count": result.count or 0,
            "open_amount": open_amount,
        }

    def _generate_next_invoice_number(self, invoice_type: InvoiceType) -> str:
        """
        Generiert die nächste Rechnungsnummer.
        Format: RE-2026-00001 oder GS-2026-00001 (Gutschrift)

        Uses SELECT ... FOR UPDATE to prevent duplicate numbers under
        concurrent access.
        """
        year = date.today().year
        # Auch die Stornorechnung (GUTSCHRIFT) läuft im regulären Kreis (R1.1):
        # EIN lückenloser, fortlaufender Nummernkreis für alle Belege — keine
        # eigene GS-Nummernwelt. Alt-Belege mit GS-Präfix bleiben unberührt.
        prefix = "RE"

        # Lock the latest invoice row to prevent concurrent duplicates
        last_invoice = self.db.execute(
            select(Invoice)
            .where(Invoice.invoice_number.like(f"{prefix}-{year}-%"))
            .order_by(Invoice.invoice_number.desc())
            .with_for_update()
            .limit(1)
        ).scalar_one_or_none()

        if last_invoice:
            sequence = int(last_invoice.invoice_number.split("-")[-1]) + 1
        else:
            sequence = 1

        return generate_invoice_number(year, sequence, prefix)
