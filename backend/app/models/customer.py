"""
Kunden-Models: Customer, CustomerAddress und Subscription
ERP-erweitert mit Payment Terms, Kreditlimit und Steuer-IDs
"""
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from sqlalchemy import String, Integer, Numeric, Boolean, DateTime, Date, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.types import Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from zoneinfo import ZoneInfo


from app.database import Base
from app.models.sepa_mandate import Zahlungsart


class CustomerType(str, Enum):
    """Kundentyp - B2B/B2C Klassifikation"""
    # B2B Typen
    GASTRO = "GASTRO"      # B2B: Gastronomie
    HANDEL = "HANDEL"      # B2B: Handel/Großhandel
    GEWERBE = "GEWERBE"    # B2B: Sonstiges Gewerbe
    # B2C Typen
    PRIVAT = "PRIVAT"      # B2C: Privatkunde

    @property
    def is_b2b(self) -> bool:
        """Prüft ob B2B-Kunde"""
        return self in (CustomerType.GASTRO, CustomerType.HANDEL, CustomerType.GEWERBE)

    @property
    def is_b2c(self) -> bool:
        """Prüft ob B2C-Kunde"""
        return self == CustomerType.PRIVAT


class PaymentTerms(str, Enum):
    """Zahlungsbedingungen"""
    PREPAID = "PREPAID"          # Vorkasse
    COD = "COD"                  # Zahlung bei Lieferung (Cash on Delivery)
    NET_7 = "NET_7"              # 7 Tage netto
    NET_14 = "NET_14"            # 14 Tage netto
    NET_30 = "NET_30"            # 30 Tage netto
    NET_60 = "NET_60"            # 60 Tage netto


class AddressType(str, Enum):
    """Adresstyp"""
    BILLING = "BILLING"          # Rechnungsadresse
    SHIPPING = "SHIPPING"        # Lieferadresse
    BOTH = "BOTH"                # Beides


class SubscriptionInterval(str, Enum):
    """Intervall für wiederkehrende Bestellungen"""
    TAEGLICH = "TAEGLICH"
    WOECHENTLICH = "WOECHENTLICH"
    ZWEIWOECHENTLICH = "ZWEIWOECHENTLICH"
    MONATLICH = "MONATLICH"


class PfandAbrechnung(str, Enum):
    """Wie das Pfand (Produkt mit is_deposit) eines Kunden abgerechnet wird.

    JE_LIEFERUNG: Pfandpositionen stehen auf jeder Rechnung (z. B. Knuspr).
    KEINE: Pfand läuft über das IFCO-Clearing — Pfandpositionen stehen auf
        Bestellung und Lieferschein, aber nicht auf der Rechnung (z. B. Ökoring).
    MONATLICH: Pfandpositionen gehen ab dem Stichtag pfand_monatlich_ab ins
        Leergutkonto (ausgegeben minus Retouren) und werden einmal im Monat
        mit einem eigenen Leergutbeleg abgerechnet, nicht auf der
        Lieferrechnung (Paket 3, Q6).
    """
    JE_LIEFERUNG = "JE_LIEFERUNG"
    KEINE = "KEINE"
    MONATLICH = "MONATLICH"


def _heute_berlin() -> date:
    """Kalendertag in München — der Server läuft in UTC."""
    return datetime.now(ZoneInfo("Europe/Berlin")).date()


class InvoiceMode(str, Enum):
    """Abrechnungsart eines Kunden (B5, Spec 08.10.2026).

    EINZELN: Rechnung je Lieferung bzw. Bestellung (bisheriges Verhalten).
    MONATLICH: eine Sammelrechnung je Kalendermonat; der Monatslauf legt sie
        am 1. des Folgemonats als Entwurf an (monatsrechnung_service).
    """
    EINZELN = "EINZELN"
    MONATLICH = "MONATLICH"


class CustomerAddress(Base):
    """
    Kundenadresse - Separate Rechnungs- und Lieferadressen
    """
    __tablename__ = "customer_addresses"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )

    # Adresstyp
    address_type: Mapped[AddressType] = mapped_column(
        SQLEnum(AddressType), nullable=False, default=AddressType.BOTH
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    # Adressdaten
    name: Mapped[Optional[str]] = mapped_column(String(200))  # Abweichender Name
    strasse: Mapped[str] = mapped_column(String(200), nullable=False)
    hausnummer: Mapped[Optional[str]] = mapped_column(String(20))
    adresszusatz: Mapped[Optional[str]] = mapped_column(String(200))  # c/o, Etage, etc.
    plz: Mapped[str] = mapped_column(String(10), nullable=False)
    ort: Mapped[str] = mapped_column(String(100), nullable=False)
    land: Mapped[str] = mapped_column(String(2), default="DE")  # ISO 3166-1 alpha-2

    # Lieferhinweise
    lieferhinweise: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Beziehungen
    customer: Mapped["Customer"] = relationship("Customer", back_populates="addresses")

    @property
    def full_address(self) -> str:
        """Formatierte Adresse"""
        parts = []
        if self.name:
            parts.append(self.name)
        street = f"{self.strasse} {self.hausnummer or ''}".strip()
        parts.append(street)
        if self.adresszusatz:
            parts.append(self.adresszusatz)
        parts.append(f"{self.plz} {self.ort}")
        if self.land != "DE":
            parts.append(self.land)
        return "\n".join(parts)

    def __repr__(self) -> str:
        return f"<CustomerAddress(type={self.address_type.value}, city='{self.ort}')>"


class Customer(Base):
    """
    Kunde - B2B und B2C Kunden mit vollständigen ERP-Daten.
    """
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )

    # Kundennummer (für Buchhaltung/DATEV)
    customer_number: Mapped[Optional[str]] = mapped_column(
        String(20), unique=True, index=True
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    typ: Mapped[CustomerType] = mapped_column(SQLEnum(CustomerType), nullable=False)

    # Kontakt (Hauptkontakt)
    email: Mapped[Optional[str]] = mapped_column(String(200))
    telefon: Mapped[Optional[str]] = mapped_column(String(50))
    adresse: Mapped[Optional[str]] = mapped_column(Text)  # Legacy, nutze addresses
    # Mehrere Ansprechpartner mit Abteilung über `Contact` (siehe unten)

    # Ansprechpartner
    ansprechpartner_name: Mapped[Optional[str]] = mapped_column(String(200))
    ansprechpartner_email: Mapped[Optional[str]] = mapped_column(String(200))
    ansprechpartner_telefon: Mapped[Optional[str]] = mapped_column(String(50))

    # Liefertage (0=Montag, 6=Sonntag)
    liefertage: Mapped[Optional[list[int]]] = mapped_column(JSON)

    # Steuer-IDs (Deutschland)
    ust_id: Mapped[Optional[str]] = mapped_column(String(20))  # USt-IdNr. (DE123456789)
    steuernummer: Mapped[Optional[str]] = mapped_column(String(20))  # Finanzamt-Steuernummer

    # Zahlungsbedingungen
    payment_terms: Mapped[PaymentTerms] = mapped_column(
        SQLEnum(PaymentTerms), default=PaymentTerms.NET_14
    )
    credit_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))  # Kreditlimit in EUR

    # Preisgruppe (FK zu PriceList)
    price_list_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("price_lists.id", ondelete="SET NULL")
    )

    # Rabatt (Jahresrabatt %)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))

    # Skonto (Frühzahler-Rabatt)
    skonto_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    skonto_days: Mapped[int] = mapped_column(Integer, default=0)

    # Verpackungsgebühr (Fixbetrag in EUR pro Rechnung)
    packaging_fee_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    # Verpackungsrabatt (% auf Verpackungsanteil — optional)
    packaging_fee_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))

    # Preise auf Lieferschein andrucken (Kundenwunsch, z.B. für Weiterberechnung)
    show_prices_on_delivery_note: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    # Pfandabrechnung (Spec 08.10.2026, Variante C): JE_LIEFERUNG oder KEINE
    # (IFCO-Clearing). Wirkt nur auf neu erzeugte Rechnungen.
    pfand_abrechnung: Mapped[PfandAbrechnung] = mapped_column(
        SQLEnum(PfandAbrechnung, length=20), nullable=False,
        default=PfandAbrechnung.JE_LIEFERUNG, server_default=PfandAbrechnung.JE_LIEFERUNG.value,
    )
    # Stichtag des Leergutkontos (Q6): ab diesem Liefertag gehen Pfandpositionen
    # ins Konto statt auf die Rechnung. Setzt nur der Wechsel auf MONATLICH
    # (_stichtag_leergutkonto) — nicht per API änderbar. Was davor geliefert
    # wurde, bleibt in der alten Abrechnungsart (keine Doppel-, keine
    # Nichtabrechnung beim Wechsel; importierte Altbestellungen bleiben draußen).
    pfand_monatlich_ab: Mapped[Optional[date]] = mapped_column(Date)

    # Zahlungsart (B10 SEPA). NULL = Überweisung (Altkunden). Nur über
    # PUT /api/v1/sepa/kunden/{id}/zahlungsart änderbar — bewusst NICHT in
    # CustomerCreate/CustomerUpdate, sonst könnte die Halle sie umschalten.
    zahlungsart: Mapped[Optional[Zahlungsart]] = mapped_column(
        SQLEnum(Zahlungsart, length=20), nullable=True
    )

    # Abrechnungsart (B5): EINZELN oder MONATLICH (Monats-Sammelrechnung als
    # Entwurf am 1. des Folgemonats). Abrechnungsrelevant — Feldschutz wie
    # pfand_abrechnung (app/core/rollen.py).
    invoice_mode: Mapped[InvoiceMode] = mapped_column(
        SQLEnum(InvoiceMode, length=20), nullable=False,
        default=InvoiceMode.EINZELN, server_default=InvoiceMode.EINZELN.value,
    )

    # DATEV-Kontonummer (Debitor)
    datev_account: Mapped[Optional[str]] = mapped_column(String(10))  # z.B. 10001

    # Belegversand (Paket 3, Q2): Empfänger je Belegart, eine Mail an alle.
    # Leer/NULL = Haupt-E-Mail (email). Geprüft über app.core.email_adressen.
    confirmation_emails: Mapped[Optional[list[str]]] = mapped_column(JSON)
    delivery_note_emails: Mapped[Optional[list[str]]] = mapped_column(JSON)
    invoice_emails: Mapped[Optional[list[str]]] = mapped_column(JSON)

    # Notizen
    notizen: Mapped[Optional[str]] = mapped_column(Text)

    # Status
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Beziehungen
    # WICHTIG: Orders und Invoices haben KEINE cascade delete!
    # Kunden mit Bestellungen/Rechnungen können nur deaktiviert (soft delete) werden.
    orders: Mapped[list["Order"]] = relationship(
        "Order", back_populates="customer"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="kunde", cascade="all, delete-orphan"
    )
    addresses: Mapped[list["CustomerAddress"]] = relationship(
        "CustomerAddress", back_populates="customer", cascade="all, delete-orphan"
    )
    contacts: Mapped[list["Contact"]] = relationship(
        "Contact", back_populates="customer", cascade="all, delete-orphan"
    )
    price_list: Mapped[Optional["PriceList"]] = relationship("PriceList")
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice", back_populates="customer"
    )
    # SEPA-Mandate: kein Cascade — der Mandatsnachweis muss erhalten bleiben.
    sepa_mandate: Mapped[list["SepaMandat"]] = relationship(
        "SepaMandat", back_populates="customer"
    )

    @validates("pfand_abrechnung")
    def _stichtag_leergutkonto(self, key, wert):
        """Wechsel auf MONATLICH setzt den Stichtag auf heute (Berlin), ein
        Wechsel weg davon löscht ihn. Gleicher Wert ändert nichts — das
        Kundenformular schickt bei jedem Speichern alle Felder mit."""
        neu = PfandAbrechnung(wert) if wert is not None else None
        if neu == PfandAbrechnung.MONATLICH:
            if self.pfand_abrechnung != PfandAbrechnung.MONATLICH:
                self.pfand_monatlich_ab = _heute_berlin()
        else:
            self.pfand_monatlich_ab = None
        return wert

    def can_be_deleted(self) -> bool:
        """
        Prüft ob Kunde gelöscht werden kann.
        Kunden mit Bestellungen oder Rechnungen können nur deaktiviert werden.
        Kunden mit SEPA-Mandat ebenfalls: der Mandatsnachweis muss bleiben.
        """
        return len(self.orders) == 0 and len(self.invoices) == 0 and len(self.sepa_mandate) == 0

    def deactivate(self) -> None:
        """Deaktiviert den Kunden (Soft Delete)"""
        self.aktiv = False

    def reactivate(self) -> None:
        """Reaktiviert den Kunden"""
        self.aktiv = True

    @property
    def billing_address(self) -> Optional["CustomerAddress"]:
        """Standard-Rechnungsadresse"""
        for addr in self.addresses:
            if addr.address_type in (AddressType.BILLING, AddressType.BOTH) and addr.is_default:
                return addr
        # Fallback: erste passende Adresse
        for addr in self.addresses:
            if addr.address_type in (AddressType.BILLING, AddressType.BOTH):
                return addr
        return None

    @property
    def shipping_address(self) -> Optional["CustomerAddress"]:
        """Standard-Lieferadresse"""
        for addr in self.addresses:
            if addr.address_type in (AddressType.SHIPPING, AddressType.BOTH) and addr.is_default:
                return addr
        # Fallback: erste passende Adresse
        for addr in self.addresses:
            if addr.address_type in (AddressType.SHIPPING, AddressType.BOTH):
                return addr
        return None

    @property
    def payment_days(self) -> int:
        """Zahlungsziel in Tagen"""
        mapping = {
            PaymentTerms.PREPAID: 0,
            PaymentTerms.COD: 0,
            PaymentTerms.NET_7: 7,
            PaymentTerms.NET_14: 14,
            PaymentTerms.NET_30: 30,
            PaymentTerms.NET_60: 60,
        }
        return mapping.get(self.payment_terms, 14)

    def __repr__(self) -> str:
        return f"<Customer(name='{self.name}', typ={self.typ.value})>"


class Contact(Base):
    """
    Ansprechpartner pro Kunde.
    Mehrere Personen mit Rollen: ALLGEMEIN, EINKAUF, VERTRIEB, BUCHHALTUNG, TECHNIK
    """
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(200))
    telefon: Mapped[Optional[str]] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(30), default="ALLGEMEIN")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    notizen: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    customer: Mapped["Customer"] = relationship("Customer", back_populates="contacts")

    def __repr__(self) -> str:
        return f"<Contact(name='{self.name}', role='{self.role}')>"


class Subscription(Base):
    """
    Abonnement - Wiederkehrende Bestellungen.
    Wichtig für Forecast-Berechnung.
    """
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    kunde_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id"), nullable=False
    )
    # Legacy: seed_id (für Migration). Neue Abos referenzieren Produkt + ggf. Variante.
    seed_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("seeds.id"), nullable=True
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="SET NULL")
    )
    product_variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("product_variants.id", ondelete="SET NULL")
    )

    # Bestellmenge
    menge: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    einheit: Mapped[str] = mapped_column(String(20), nullable=False)  # GRAMM, BUND, SCHALE

    # Intervall
    intervall: Mapped[SubscriptionInterval] = mapped_column(
        SQLEnum(SubscriptionInterval), nullable=False
    )
    liefertage: Mapped[Optional[list[int]]] = mapped_column(JSON)

    # Gültigkeit
    gueltig_von: Mapped[date] = mapped_column(Date, nullable=False)
    gueltig_bis: Mapped[Optional[date]] = mapped_column(Date)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Beziehungen
    kunde: Mapped["Customer"] = relationship("Customer", back_populates="subscriptions")
    seed: Mapped["Seed"] = relationship("Seed")
    # product_id war bisher nur eine FK-Spalte ohne Relation — dadurch konnte
    # die Abo-Liste den Produktnamen nicht auflösen.
    product: Mapped[Optional["Product"]] = relationship("Product", foreign_keys=[product_id])

    @property
    def ist_aktiv(self) -> bool:
        """Prüft ob Abo aktuell gültig ist"""
        today = date.today()
        if not self.aktiv:
            return False
        if today < self.gueltig_von:
            return False
        if self.gueltig_bis and today > self.gueltig_bis:
            return False
        return True

    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, kunde_id={self.kunde_id})>"


# Imports für Type Hints (am Ende um zirkuläre Imports zu vermeiden)
from app.models.order import Order
from app.models.seed import Seed
from app.models.product import PriceList, Product
from app.models.invoice import Invoice
