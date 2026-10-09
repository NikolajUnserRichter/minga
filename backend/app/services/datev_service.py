from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
import csv
from io import StringIO

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session, aliased

from app.models.invoice import (
    Invoice, InvoiceLine, InvoiceStatus, InvoiceType, Payment, PaymentMethod,
    TaxRate, STANDARD_ACCOUNTS, steuer_je_satz, ENTWURF_PRAEFIX,
)
from app.models.customer import Customer

# ---------------------------------------------------------------------------
# Kontierung des Rechnungsexports.
#
# VOR PRODUKTIVNUTZUNG VOM STEUERBERATER ZU BESTÄTIGEN (Spec 08.10.2026,
# Offene Entscheidung 5). Der EXTF-Kopf (Berater-/Mandantennummer, WJ-Beginn,
# Sachkontenlänge) ist NICHT Teil dieser Korrektur.
#
# - Je Rechnung und (Steuersatz, Erlöskonto) genau eine Buchungszeile.
# - Konto = Debitor, Gegenkonto = Erlöskonto, BU-Schlüssel leer:
#   8300/8400 sind in SKR03 Automatikkonten, DATEV rechnet die USt aus dem
#   Bruttobetrag heraus.
# - Umsatz immer positiv; die Richtung steht im Soll/Haben-Kennzeichen und
#   bezieht sich auf das Konto (den Debitor): Rechnung S, Gutschrift H.
# - Keine Zeile auf 1400: das Sammelkonto Forderungen führt DATEV aus den
#   Debitoren selbst. Die frühere Zeile "1400 an Debitor" schrieb die
#   Forderung gut, statt sie zu begründen.
# - Beträge nach der einen Rechenregel steuer_je_satz() (wie Rechnungssummen
#   und Steuerausweis): die Zeilen einer Rechnung ergeben genau ihr total.
# ---------------------------------------------------------------------------

DATEV_KOPF = [
    "Umsatz", "Soll/Haben", "WKZ", "Kurs", "Basisumsatz",
    "Konto", "Gegenkonto", "BU-Schlüssel", "Belegdatum",
    "Belegfeld 1", "Belegfeld 2", "Buchungstext",
]

#: Debitor für Kunden ohne hinterlegtes DATEV-Konto (Bestandsverhalten).
SAMMELDEBITOR = "10000"

ERLOESKONTO_JE_SATZ = {
    TaxRate.REDUZIERT: STANDARD_ACCOUNTS["erloes_7"],
    TaxRate.STANDARD: STANDARD_ACCOUNTS["erloes_19"],
    TaxRate.STEUERFREI: STANDARD_ACCOUNTS["erloes_steuerfrei"],
}

#: Proforma ist kein Buchungsbeleg; Abschlagsrechnungen brauchen eine eigene
#: Kontierung (erhaltene Anzahlungen) und sind in der Oberfläche nicht anlegbar.
EXPORTIERBARE_TYPEN = (InvoiceType.RECHNUNG, InvoiceType.GUTSCHRIFT)

_CENT = Decimal("0.01")


def erloeskonto_fuer(tax_rate: TaxRate) -> str:
    """Standard-Erlöskonto (SKR03) zum Steuersatz: 8300 / 8400 / 8100, unbekannt 8300."""
    return ERLOESKONTO_JE_SATZ.get(tax_rate, STANDARD_ACCOUNTS["erloes_7"])


def ist_standard_erloeskonto(konto: Optional[str]) -> bool:
    """Leer oder eines der drei Standardkonten: dann folgt das Konto dem Satz.

    Jedes andere Konto ist ein Sonderkonto und bleibt stehen — im Export
    (erloeskonto) wie beim Satzwechsel im Entwurf (update_invoice_line,
    Task 25). Bestätigung durch den Steuerberater steht aus.
    """
    return not konto or konto in ERLOESKONTO_JE_SATZ.values()


def erloeskonto(line: InvoiceLine) -> str:
    """Erlöskonto einer Rechnungsposition.

    Die drei Standardkonten folgen immer dem Steuersatz der Position: wird der
    Satz eines Entwurfs nachträglich geändert, bleibt das in add_line gesetzte
    Konto sonst auf dem alten Satz stehen. Ein ausdrücklich gesetztes
    Sonderkonto bleibt erhalten.
    """
    if ist_standard_erloeskonto(line.buchungskonto):
        return erloeskonto_fuer(line.tax_rate)
    return line.buchungskonto


def erloesgruppen(invoice: Invoice) -> list[dict]:
    """Netto, Steuer und Brutto je (Erlöskonto, Steuersatz), mit Vorzeichen.

    Rechenregel steuer_je_satz() aus app.models.invoice — dieselbe wie
    Invoice.calculate_totals() (total) und Invoice.get_tax_summary()
    (Steuerausweis): Rabatt je Satz auf den Cent runden, Entgelt = Netto
    minus Rabatt, Steuer auf das gerundete Entgelt.

    Normalfall: ein Konto je Satz, dann ist jede Gruppe genau der
    Steuerausweis des Satzes. Teilen sich mehrere Konten einen Satz
    (Sonderkonto einer Position neben dem Standardkonto), rundet jedes Konto
    für sich; den Rest-Cent gegenüber dem Steuerausweis des Satzes trägt die
    betragsgrößte Gruppe des Satzes. So ergeben die Zeilen je Satz immer den
    Steuerausweis und zusammen den Rechnungsbetrag.

    Liest nur gespeicherte Werte (line.line_total), ruft also nicht
    calculate_line_total() auf: der Export committet und darf keinen
    versendeten Beleg verändern.
    """
    rabatt = invoice.discount_percent
    zeilen_je_konto: dict[str, list[InvoiceLine]] = {}
    for line in invoice.lines:
        zeilen_je_konto.setdefault(erloeskonto(line), []).append(line)

    gruppen = [
        {"satz": s["rate"], "konto": konto, "netto": s["base"], "steuer": s["tax"]}
        for konto, zeilen in zeilen_je_konto.items()
        for s in steuer_je_satz(zeilen, rabatt)
    ]

    # Rest-Cent-Ausgleich je Satz (bei einem Konto je Satz immer 0).
    for ausweis in steuer_je_satz(invoice.lines, rabatt):
        teile = [g for g in gruppen if g["satz"] == ausweis["rate"]]
        groesste = max(teile, key=lambda g: (abs(g["netto"]), g["konto"]))
        groesste["netto"] += ausweis["base"] - sum(g["netto"] for g in teile)
        groesste["steuer"] += ausweis["tax"] - sum(g["steuer"] for g in teile)

    for g in gruppen:
        g["brutto"] = g["netto"] + g["steuer"]
    return sorted(gruppen, key=lambda g: (g["konto"], g["satz"].value))


def _betrag(wert: Decimal) -> str:
    """DATEV-Betrag: zwei Nachkommastellen, Dezimalkomma, ohne Tausenderpunkt."""
    return f"{Decimal(wert).quantize(_CENT, rounding=ROUND_HALF_UP):.2f}".replace(".", ",")


def _richtung(invoice: Invoice, brutto: Decimal) -> str:
    """Soll/Haben aus Sicht des Debitors.

    Eine Gutschrift mindert immer (H) — die Stornorechnung trägt negative
    Mengen, die von Hand angelegte Gutschrift positive; beide sind Minderungen.
    Eine Rechnung bucht S, ein (heute nicht erzeugbarer) negativer Betrag H.
    """
    if invoice.invoice_type == InvoiceType.GUTSCHRIFT:
        return "H"
    return "S" if brutto >= 0 else "H"


def _debitor(customer: Customer) -> str:
    return customer.datev_account or SAMMELDEBITOR


class DatevService:
    """
    Service für DATEV-Exporte.
    Centralized logic for exporting Invoices, Payments, and Customer Data.
    """

    def __init__(self, db: Session):
        self.db = db

    def _rechnungen(
        self, from_date: date, to_date: date, erneut_exportieren: bool = False
    ) -> list[Invoice]:
        """Buchungsrelevante Belege im Zeitraum.

        - Entwürfe nie, Proforma/Abschlag nie.
        - Eine Stornorechnung (GUTSCHRIFT mit original_invoice_id) immer,
          gleich mit welchem Status: der Storno-Abschnitt setzt sie auf
          STORNIERT, sie bleibt trotzdem ein Beleg.
        - Eine stornierte RECHNUNG nur, wenn eine Stornorechnung existiert:
          dann sind beide Belege und heben sich in DATEV auf. Ohne Gegenbeleg
          (Storno ohne Stornorechnung, per PATCH stornierter Entwurf) gäbe es
          nur Umsatz, den es nie gab.
        - Eine stornierte Gutschrift von Hand (verworfener Entwurf) nie.
        - Bereits exportierte nur mit erneut_exportieren=True.
        """
        storno = aliased(Invoice)
        hat_stornorechnung = (
            select(storno.id)
            .where(
                storno.original_invoice_id == Invoice.id,
                storno.invoice_type == InvoiceType.GUTSCHRIFT,
                storno.status != InvoiceStatus.ENTWURF,
            )
            .exists()
        )
        ist_stornorechnung = and_(
            Invoice.invoice_type == InvoiceType.GUTSCHRIFT,
            Invoice.original_invoice_id.isnot(None),
        )
        query = select(Invoice).where(
            Invoice.invoice_date.between(from_date, to_date),
            Invoice.status != InvoiceStatus.ENTWURF,
            # Nie ein Beleg ohne Rechnungsnummer (Platzhalter ENTWURF-…),
            # gleich in welchem Status (Spec 08.10.2026, Entscheidung 2).
            ~Invoice.invoice_number.startswith(ENTWURF_PRAEFIX),
            Invoice.invoice_type.in_(EXPORTIERBARE_TYPEN),
            or_(
                ist_stornorechnung,
                Invoice.status != InvoiceStatus.STORNIERT,
                hat_stornorechnung,
            ),
        )
        if not erneut_exportieren:
            query = query.where(Invoice.datev_exported == False)  # noqa: E712
        return self.db.execute(query.order_by(Invoice.invoice_number)).scalars().all()

    def export_invoices_csv(
        self,
        from_date: date,
        to_date: date,
        include_payments: bool = True,
        erneut_exportieren: bool = False,
    ) -> tuple[str, int, Decimal]:
        """
        Exportiert Rechnungen und optional Zahlungen im DATEV-Format (CSV Buchungsstapel).
        Gibt CSV-Content, Anzahl Records und den Saldo der Rechnungszeilen
        (S positiv, H negativ, brutto) zurück.

        Markiert genau die exportierten Rechnungen/Zahlungen (datev_exported,
        datev_export_date) in derselben Transaktion. erneut_exportieren=True
        nimmt bereits exportierte im Zeitraum wieder auf — für eine verlorene
        oder vom Steuerberater zurückgewiesene Datei.
        """
        invoices = self._rechnungen(from_date, to_date, erneut_exportieren)

        output = StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(DATEV_KOPF)

        record_count = 0
        total_amount = Decimal("0")
        jetzt = datetime.now(timezone.utc)

        for invoice in invoices:
            customer = self.db.get(Customer, invoice.customer_id)
            debitor = _debitor(customer)
            if invoice.invoice_type == InvoiceType.GUTSCHRIFT:
                original = invoice.original_invoice
                art = f"Storno {original.invoice_number}" if original else "Gutschrift"
            else:
                art = "Rechnung"

            for gruppe in erloesgruppen(invoice):
                if gruppe["brutto"] == 0:
                    continue
                sh = _richtung(invoice, gruppe["brutto"])
                betrag = abs(gruppe["brutto"])
                zeile = [
                    _betrag(betrag),                           # Umsatz (immer positiv)
                    sh,                                         # Soll/Haben (bezogen auf Konto)
                    "EUR", "", "",                              # WKZ, Kurs, Basisumsatz
                    debitor,                                    # Konto
                    gruppe["konto"],                            # Gegenkonto (Erlöskonto)
                    "",                                         # BU-Schlüssel (Automatikkonto)
                    invoice.invoice_date.strftime("%d%m"),      # Belegdatum
                    invoice.invoice_number,                     # Belegfeld 1
                    "",                                         # Belegfeld 2
                    f"{art} {gruppe['satz'].percent} % {customer.name}"[:60],
                ]
                writer.writerow(zeile)
                record_count += 1
                total_amount += betrag if sh == "S" else -betrag

            invoice.datev_exported = True
            invoice.datev_export_date = jetzt

        # Payments Export
        if include_payments:
            query = (
                select(Payment)
                .join(Invoice)
                .where(Payment.payment_date.between(from_date, to_date))
                .order_by(Payment.payment_date, Invoice.invoice_number)
            )
            if not erneut_exportieren:
                query = query.where(Payment.datev_exported == False)  # noqa: E712
            payments = self.db.execute(query).scalars().all()

            for payment in payments:
                invoice = payment.invoice
                customer = self.db.get(Customer, invoice.customer_id)

                bank_account = STANDARD_ACCOUNTS.get("bank", "1200")
                if payment.payment_method == PaymentMethod.BAR:
                    bank_account = STANDARD_ACCOUNTS.get("kasse", "1000")

                # Booking: Bank (1200) S an Debitor H
                row_payment = [
                    # Rücklastschrift (B10): Gegenbuchung mit negativem Betrag.
                    # DATEV erwartet den Umsatz positiv; die Richtung steht im
                    # Soll/Haben-Kennzeichen (Bank H an Debitor).
                    _betrag(abs(payment.amount)),
                    "H" if payment.amount < 0 else "S",
                    "EUR", "", "",
                    bank_account,
                    _debitor(customer),
                    "",
                    payment.payment_date.strftime("%d%m"),
                    invoice.invoice_number,
                    payment.reference or "",
                    f"Zahlung {customer.name}"[:60],
                ]
                writer.writerow(row_payment)
                record_count += 1

                payment.datev_exported = True

        return output.getvalue(), record_count, total_amount

    def export_customers_csv(self) -> str:
        """
        Exportiert Stammdaten der Kunden für DATEV (Debitoren-Import).
        Format: Debitor-Nr, Name, Strasse, PLZ, Ort, USt-IdNr
        """
        customers = self.db.execute(
            select(Customer)
            .where(Customer.aktiv == True)
            .order_by(Customer.customer_number)
        ).scalars().all()

        output = StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

        # DATEV Customer Import Header (Simplified)
        header = ["Konto", "Name", "Strasse", "PLZ", "Ort", "Land", "USt-IdNr", "IBAN"]
        writer.writerow(header)

        for cust in customers:
            # Address fallback
            addr = cust.billing_address
            # Note: billing_address is a property that iterates relationship.
            
            row = [
                cust.datev_account or cust.customer_number or "10000",
                cust.name,
                addr.strasse if addr else "",
                addr.plz if addr else "",
                addr.ort if addr else "",
                addr.land if addr else "DE",
                cust.ust_id or "",
                "" # IBAN if we had it
            ]
            writer.writerow(row)
            
        return output.getvalue()
