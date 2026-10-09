"""
Rechnungs-Models: Invoice, InvoiceLine und Payment
Mit deutscher MwSt-Berechnung und DATEV-Export-Feldern
"""
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional
from sqlalchemy import String, Integer, Numeric, Boolean, DateTime, Date, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.types import Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.database import Base


from app.models.enums import InvoiceStatus, InvoiceType, TaxRate, PaymentMethod
from app.models.sepa_mandate import Zahlungsart, LastschriftStatus


def _cent(betrag: Decimal) -> Decimal:
    return betrag.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def steuer_je_satz(lines, discount_percent) -> list[dict]:
    """Entgelt und Steuer je Steuersatz — die eine Rechenregel für Rechnungssummen,
    PDF-Steuerblock und DATEV.

    § 14 Abs. 4 Nr. 8 UStG verlangt auf der Rechnung das Entgelt und den
    Steuerbetrag je Steuersatz; § 16 Abs. 1 UStG rechnet die Steuer auf die
    Summe der Entgelte je Satz. Regel:
      1. je Satz die (bereits auf den Cent gerundeten) Zeilenbeträge summieren,
      2. den Rechnungsrabatt je Satz auf den Cent runden und abziehen (= Entgelt),
      3. die Steuer auf dieses Entgelt rechnen und je Satz auf den Cent runden.
    Entgelt und Steuer je Satz folgen so aus den Positionen auf dem Beleg.
    Der Gesamtrabatt ist die Summe der Rabatte je Satz und kann deshalb 1 ct
    von "Zwischensumme × Rabattsatz" abweichen.

    Arbeitet auf allem, was `tax_rate` und `line_total` trägt (auch auf den
    Dummy-Zeilen der Vorlagen-Vorschau). Verändert nichts.
    Reihenfolge: aufsteigend nach Steuersatz (0 %, 7 %, 19 %).
    """
    rabatt_prozent = Decimal(str(discount_percent or 0))
    je_satz: dict = {}
    for line in lines:
        eintrag = je_satz.setdefault(line.tax_rate, {
            "rate": line.tax_rate,
            "percent": line.tax_rate.percent,
            "netto_vor_rabatt": Decimal("0.00"),
            "rabatt": Decimal("0.00"),
            "base": Decimal("0.00"),
            "tax": Decimal("0.00"),
        })
        eintrag["netto_vor_rabatt"] += Decimal(str(line.line_total or 0))

    for eintrag in je_satz.values():
        if rabatt_prozent > 0:
            eintrag["rabatt"] = _cent(eintrag["netto_vor_rabatt"] * rabatt_prozent / 100)
        eintrag["base"] = eintrag["netto_vor_rabatt"] - eintrag["rabatt"]
        eintrag["tax"] = _cent(eintrag["base"] * eintrag["rate"].rate)

    return sorted(je_satz.values(), key=lambda e: e["percent"])


def steuerausweis_stimmt(invoice) -> bool:
    """Ergibt die Aufteilung je Satz exakt die gespeicherten Rechnungssummen?

    Für jede mit calculate_totals() berechnete Rechnung ja. Nein nur bei
    Altrechnungen, deren Summen vor der Vereinheitlichung (Oktober 2026) mit
    einmaliger Rundung über alle Sätze festgeschrieben wurden — bei
    gemischten Sätzen oder Rechnungsrabatt kann das 1 ct abweichen.
    Versendete Rechnungen sind unveränderlich (GoBD); ihr PDF muss dann die
    festgeschriebenen Beträge zeigen, keine davon abweichende Aufteilung.
    """
    saetze = steuer_je_satz(invoice.lines, invoice.discount_percent)
    return (
        sum((s["base"] for s in saetze), Decimal("0")) == Decimal(str(invoice.subtotal or 0))
        and sum((s["tax"] for s in saetze), Decimal("0")) == Decimal(str(invoice.tax_amount or 0))
    )


class Invoice(Base):
    """
    Rechnung - Vollständige deutsche Rechnung mit MwSt und DATEV-Feldern
    """
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )

    # Rechnungsnummer (fortlaufend, Format: RE-2026-00001)
    invoice_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )

    # Rechnungstyp
    invoice_type: Mapped[InvoiceType] = mapped_column(
        SQLEnum(InvoiceType), default=InvoiceType.RECHNUNG
    )

    # Referenz auf Originalrechnung (bei Gutschrift)
    original_invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("invoices.id", ondelete="SET NULL")
    )

    # Kunde
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id"), nullable=False
    )

    # Bestellung (optional, Rechnung kann auch ohne Bestellung erstellt werden)
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="SET NULL", use_alter=True)
    )

    # Datum
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    delivery_date: Mapped[Optional[date]] = mapped_column(Date)  # Liefer-/Leistungsdatum
    due_date: Mapped[date] = mapped_column(Date, nullable=False)  # Fälligkeitsdatum
    # Leistungszeitraum (Sammelrechnung): umsatzsteuerlich gehört der Zeitraum
    # auf den Beleg, wenn über mehrere Lieferungen abgerechnet wird.
    service_period_start: Mapped[Optional[date]] = mapped_column(Date)
    service_period_end: Mapped[Optional[date]] = mapped_column(Date)

    # Status
    status: Mapped[InvoiceStatus] = mapped_column(
        SQLEnum(InvoiceStatus), default=InvoiceStatus.ENTWURF
    )

    # Adressen (als Snapshot zum Rechnungszeitpunkt)
    billing_address: Mapped[Optional[dict]] = mapped_column(JSON)
    shipping_address: Mapped[Optional[dict]] = mapped_column(JSON)

    # Beträge (werden bei Speichern berechnet)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))  # Netto
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))  # MwSt
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))  # Brutto

    # Rabatt auf Gesamtrechnung
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    # Bezahlt
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    # Pfand / Deposit (Teil von Total)
    total_deposit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    # Währung
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    # DATEV-Felder
    datev_exported: Mapped[bool] = mapped_column(Boolean, default=False)
    datev_export_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    buchungskonto: Mapped[Optional[str]] = mapped_column(String(10))  # Erlöskonto (z.B. 8400)

    # Lexware Office (lexoffice) — Übertragungsstatus
    lexoffice_id: Mapped[Optional[str]] = mapped_column(String(64))
    lexoffice_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Notizen
    header_text: Mapped[Optional[str]] = mapped_column(Text)  # Text vor Positionen
    footer_text: Mapped[Optional[str]] = mapped_column(Text)  # Text nach Positionen
    internal_notes: Mapped[Optional[str]] = mapped_column(Text)  # Interne Notizen

    # Mahnwesen / Dunning
    reminder_level: Mapped[int] = mapped_column(Integer, default=0)  # 0=keine, 1-3=Mahnstufe
    last_reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    next_reminder_date: Mapped[Optional[date]] = mapped_column(Date)

    # SEPA-Lastschrift (B10). Gesetzt erst beim Festschreiben (ENTWURF → OFFEN),
    # nie beim Anlegen: ein Entwurf kann noch den Kunden wechseln.
    # zahlungsart NULL = Überweisung (Altbestand).
    zahlungsart: Mapped[Optional[Zahlungsart]] = mapped_column(SQLEnum(Zahlungsart, length=20))
    sepa_mandat_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("sepa_mandates.id"))
    #: Vorabankündigung, beim Festschreiben eingefroren (GoBD): PDF und Mail
    #: lesen nur diesen Text, nie das Mandat. Enthält die IBAN nur maskiert.
    sepa_hinweis: Mapped[Optional[str]] = mapped_column(Text)
    lastschrift_status: Mapped[Optional[LastschriftStatus]] = mapped_column(SQLEnum(LastschriftStatus, length=20))
    #: Tag, an dem die Rechnung in einer Einreichungsdatei (CSV) an die Bank
    #: ging. Eine Rechnung wird nur einmal eingereicht (POST /sepa/einreichung).
    lastschrift_eingereicht_am: Mapped[Optional[date]] = mapped_column(Date)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)  # Wann versendet

    # Beziehungen
    customer: Mapped["Customer"] = relationship("Customer", back_populates="invoices")
    order: Mapped[Optional["Order"]] = relationship("Order", foreign_keys=[order_id])
    original_invoice: Mapped[Optional["Invoice"]] = relationship(
        "Invoice", remote_side=[id], foreign_keys=[original_invoice_id]
    )
    lines: Mapped[list["InvoiceLine"]] = relationship(
        "InvoiceLine", back_populates="invoice", cascade="all, delete-orphan",
        order_by="InvoiceLine.position"
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="invoice", cascade="all, delete-orphan"
    )
    # Versandprotokoll (Paket 3, Q2), älteste zuerst — Modell in models/documents.py
    dispatches: Mapped[list["DocumentDispatch"]] = relationship(
        "DocumentDispatch",
        foreign_keys="DocumentDispatch.invoice_id",
        order_by="DocumentDispatch.sent_at",
        lazy="selectin",
        viewonly=True,
    )

    def calculate_totals(self) -> None:
        """Berechnet Zwischensumme, Rabatt, MwSt und Gesamtbetrag.

        Alle Beträge kommen aus steuer_je_satz() — derselben Rechnung, die
        get_tax_summary() und der Steuerblock im PDF verwenden. Dadurch gilt
        für jede hier berechnete Rechnung: Summe der Netto je Satz = subtotal,
        Summe der Steuer je Satz = tax_amount. Früher rundete diese Methode
        die Steuer einmal über alle Sätze, get_tax_summary() je Satz — bei
        gemischten Sätzen lagen beide 1 ct auseinander.
        """
        for line in self.lines:
            line.calculate_line_total()
        saetze = steuer_je_satz(self.lines, self.discount_percent)

        self.discount_amount = sum((s["rabatt"] for s in saetze), Decimal("0.00"))
        self.subtotal = sum((s["base"] for s in saetze), Decimal("0.00"))
        self.tax_amount = sum((s["tax"] for s in saetze), Decimal("0.00"))
        self.total = self.subtotal + self.tax_amount

        # Pfand-Summe berechnen (Brutto)
        deposit_sum = sum((line.gross_total for line in self.lines if line.is_deposit), Decimal("0.00"))
        self.total_deposit = deposit_sum.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def remaining_amount(self) -> Decimal:
        """Offener Betrag"""
        return (self.total - self.paid_amount).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def is_paid(self) -> bool:
        """Rechnung vollständig bezahlt?"""
        return self.paid_amount >= self.total

    @property
    def is_overdue(self) -> bool:
        """Rechnung überfällig?"""
        if self.status in (InvoiceStatus.BEZAHLT, InvoiceStatus.STORNIERT):
            return False
        return date.today() > self.due_date

    # Kunde für Listen und Detail. InvoiceResponse kennt beide Felder seit
    # jeher (from_attributes), das Modell hatte sie nicht — die Spalte "Kunde"
    # blieb deshalb überall leer. Stammdaten-Stand wie im PDF
    # (pdf_service: invoice.customer.name). Listen laden den Kunden per
    # joinedload, sonst kostet jede Zeile eine eigene Abfrage.
    @property
    def customer_name(self) -> Optional[str]:
        """Name des Kunden (aktueller Stammdatenstand)."""
        return self.customer.name if self.customer else None

    @property
    def customer_number(self) -> Optional[str]:
        """Kundennummer (aktueller Stammdatenstand)."""
        return self.customer.customer_number if self.customer else None

    def get_tax_summary(self) -> list[dict]:
        """MwSt je Satz: Schlüssel rate, percent, base, tax, netto_vor_rabatt, rabatt.

        Gleiche Rechenregel wie calculate_totals(). Liest die gespeicherten
        Zeilenbeträge und verändert nichts — sicher auch für versendete
        Rechnungen (PDF-Abruf, DATEV-Export).
        """
        return steuer_je_satz(self.lines, self.discount_percent)

    def __repr__(self) -> str:
        return f"<Invoice(number='{self.invoice_number}', total={self.total})>"


class InvoiceLine(Base):
    """
    Rechnungsposition - Einzelne Zeile auf der Rechnung
    """
    __tablename__ = "invoice_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )

    # Position auf der Rechnung
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Produkt (optional, kann auch Freitext sein)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="SET NULL")
    )

    # Artikelbeschreibung (Snapshot oder Freitext)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sku: Mapped[Optional[str]] = mapped_column(String(50))  # Artikelnummer

    # Menge und Einheit
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # kg, Stk, Schale

    # Preise
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)  # Einzelpreis netto
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))

    # MwSt
    tax_rate: Mapped[TaxRate] = mapped_column(
        SQLEnum(TaxRate), default=TaxRate.REDUZIERT  # Lebensmittel = 7%
    )

    # Berechneter Zeilenbetrag (netto, nach Rabatt)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    # Referenz auf Order-Item (für Rückverfolgung)
    order_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("order_lines.id", ondelete="SET NULL")
    )

    # Chargen-Referenz (für Rückverfolgbarkeit)
    harvest_batch_ids: Mapped[Optional[list]] = mapped_column(JSON)  # Liste von Harvest-IDs

    # DATEV
    buchungskonto: Mapped[Optional[str]] = mapped_column(String(10))  # Erlöskonto

    # Pfand
    is_deposit: Mapped[bool] = mapped_column(Boolean, default=False)

    # Beziehungen
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="lines")
    product: Mapped[Optional["Product"]] = relationship("Product")

    def calculate_line_total(self) -> Decimal:
        """Berechnet Zeilenbetrag (netto, nach Positionsrabatt)"""
        total = self.quantity * self.unit_price
        if self.discount_percent > 0:
            total -= total * self.discount_percent / 100
        self.line_total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return self.line_total

    @property
    def tax_amount(self) -> Decimal:
        """MwSt-Betrag dieser Position"""
        return (self.line_total * self.tax_rate.rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def gross_total(self) -> Decimal:
        """Brutto-Zeilenbetrag"""
        return self.line_total + self.tax_amount

    def __repr__(self) -> str:
        return f"<InvoiceLine(pos={self.position}, desc='{self.description[:30]}...')>"


class Payment(Base):
    """
    Zahlung - Zahlungseingänge zu Rechnungen
    """
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )

    # Zahlungsdaten
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        SQLEnum(PaymentMethod), default=PaymentMethod.UEBERWEISUNG
    )

    # Referenz
    reference: Mapped[Optional[str]] = mapped_column(String(100))  # Überweisungsreferenz
    bank_reference: Mapped[Optional[str]] = mapped_column(String(100))  # Bank-Transaktions-ID

    # Notizen
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # DATEV
    datev_exported: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Beziehungen
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")

    def __repr__(self) -> str:
        return f"<Payment(amount={self.amount}, date={self.payment_date})>"


# Hilfsfunktion für Rechnungsnummer-Generierung
class InvoiceLineSource(Base):
    """Herkunft einer Sammelrechnungs-Position (R2.3).

    Eine aggregierte Position fasst Mengen aus mehreren Lieferscheinen
    zusammen — hier steht, welcher Lieferschein wie viel beigetragen hat.
    Damit bleibt die Rechnung drilldown-fähig und exportierbar.
    """
    __tablename__ = "invoice_line_sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invoice_line_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("invoice_lines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delivery_note_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("delivery_notes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)


def generate_invoice_number(year: int, sequence: int, prefix: str = "RE") -> str:
    """
    Generiert eine fortlaufende Rechnungsnummer.
    Format: RE-2026-00001
    """
    return f"{prefix}-{year}-{sequence:05d}"


#: Platzhalter-Präfix für Rechnungsentwürfe (Spec 08.10.2026, Entscheidung 2).
#: Die Rechnungsnummer vergibt erst InvoiceService.festschreiben. "ENTWURF-"
#: plus 12 Hexzeichen der Rechnungs-ID = 20 Zeichen, passt in
#: invoice_number (String(20), unique, NOT NULL).
ENTWURF_PRAEFIX = "ENTWURF-"


def entwurfsnummer(invoice_id: uuid.UUID) -> str:
    """Platzhalter eines Entwurfs, z. B. ENTWURF-1A2B3C4D5E6F."""
    return f"{ENTWURF_PRAEFIX}{invoice_id.hex[:12].upper()}"


def ist_entwurfsnummer(nummer: Optional[str]) -> bool:
    """True, solange die Rechnung noch keine Rechnungsnummer hat."""
    return bool(nummer) and nummer.startswith(ENTWURF_PRAEFIX)


# Standard-Buchungskonten (SKR03)
STANDARD_ACCOUNTS = {
    "erloes_7": "8300",      # Erlöse 7% USt
    "erloes_19": "8400",     # Erlöse 19% USt
    "erloes_steuerfrei": "8100",  # Steuerfreie Erlöse
    "forderungen": "1400",   # Forderungen aus L+L
    "bank": "1200",          # Bank
    "kasse": "1000",         # Kasse
}


# Imports für Type Hints
from app.models.customer import Customer
from app.models.order import Order
from app.models.product import Product
