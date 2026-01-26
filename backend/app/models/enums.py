from enum import Enum
from decimal import Decimal

class TaxRate(str, Enum):
    """Deutsche MwSt-Sätze"""
    STANDARD = "STANDARD"         # 19%
    REDUZIERT = "REDUZIERT"       # 7% (Lebensmittel)
    STEUERFREI = "STEUERFREI"     # 0% (z.B. EU-Lieferungen)

    @property
    def rate(self) -> Decimal:
        """Steuersatz als Dezimalzahl"""
        rates = {
            TaxRate.STANDARD: Decimal("0.19"),
            TaxRate.REDUZIERT: Decimal("0.07"),
            TaxRate.STEUERFREI: Decimal("0.00"),
        }
        return rates.get(self, Decimal("0.19"))

    @property
    def percent(self) -> int:
        """Steuersatz als Prozent"""
        percents = {
            TaxRate.STANDARD: 19,
            TaxRate.REDUZIERT: 7,
            TaxRate.STEUERFREI: 0,
        }
        return percents.get(self, 19)

class InvoiceStatus(str, Enum):
    """Rechnungsstatus"""
    ENTWURF = "ENTWURF"           # Noch nicht gesendet
    OFFEN = "OFFEN"               # Gesendet, wartet auf Zahlung
    TEILBEZAHLT = "TEILBEZAHLT"   # Teilweise bezahlt
    BEZAHLT = "BEZAHLT"           # Vollständig bezahlt
    UEBERFAELLIG = "UEBERFAELLIG" # Zahlungsziel überschritten
    STORNIERT = "STORNIERT"       # Storniert/Gutschrift
    MAHNVERFAHREN = "MAHNVERFAHREN"  # Im Mahnverfahren

class InvoiceType(str, Enum):
    """Rechnungstyp"""
    RECHNUNG = "RECHNUNG"         # Normale Rechnung
    GUTSCHRIFT = "GUTSCHRIFT"     # Gutschrift/Stornorechnung
    PROFORMA = "PROFORMA"         # Proforma-Rechnung
    ABSCHLAG = "ABSCHLAG"         # Abschlagsrechnung

class PaymentMethod(str, Enum):
    """Zahlungsmethode"""
    UEBERWEISUNG = "UEBERWEISUNG"  # Banküberweisung
    BAR = "BAR"                    # Barzahlung
    EC = "EC"                      # EC-Karte
    KREDITKARTE = "KREDITKARTE"   # Kreditkarte
    PAYPAL = "PAYPAL"             # PayPal
    LASTSCHRIFT = "LASTSCHRIFT"   # SEPA-Lastschrift

class OrderStatus(str, Enum):
    """Status einer Bestellung - vollständiger Lebenszyklus"""
    ENTWURF = "ENTWURF"              # Draft - kann bearbeitet werden
    BESTAETIGT = "BESTAETIGT"        # Confirmed - gesperrt
    IN_PRODUKTION = "IN_PRODUKTION"  # In Production
    GELIEFERT = "GELIEFERT"          # Delivered
    FAKTURIERT = "FAKTURIERT"        # Invoiced
    STORNIERT = "STORNIERT"          # Cancelled
