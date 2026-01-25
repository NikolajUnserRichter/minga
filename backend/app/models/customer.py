"""
Kunden-Models: Customer, CustomerAddress und Subscription
ERP-erweitert mit Payment Terms, Kreditlimit und Steuer-IDs
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional
from sqlalchemy import String, Integer, Numeric, Boolean, DateTime, Date, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB

from app.database import Base


class CustomerType(str, Enum):
    """Kundentyp"""
    GASTRO = "GASTRO"
    HANDEL = "HANDEL"
    PRIVAT = "PRIVAT"


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


class CustomerAddress(Base):
    """
    Kundenadresse - Separate Rechnungs- und Lieferadressen
    """
    __tablename__ = "customer_addresses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )

    # Adresstyp
    address_type: Mapped[AddressType] = mapped_column(
        SQLEnum(AddressType), nullable=False, default=AddressType.BOTH
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    # Adressdaten
    name: Mapped[str | None] = mapped_column(String(200))  # Abweichender Name
    strasse: Mapped[str] = mapped_column(String(200), nullable=False)
    hausnummer: Mapped[str | None] = mapped_column(String(20))
    adresszusatz: Mapped[str | None] = mapped_column(String(200))  # c/o, Etage, etc.
    plz: Mapped[str] = mapped_column(String(10), nullable=False)
    ort: Mapped[str] = mapped_column(String(100), nullable=False)
    land: Mapped[str] = mapped_column(String(2), default="DE")  # ISO 3166-1 alpha-2

    # Lieferhinweise
    lieferhinweise: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
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
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Kundennummer (für Buchhaltung/DATEV)
    customer_number: Mapped[str | None] = mapped_column(
        String(20), unique=True, index=True
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    typ: Mapped[CustomerType] = mapped_column(SQLEnum(CustomerType), nullable=False)

    # Kontakt (Hauptkontakt)
    email: Mapped[str | None] = mapped_column(String(200))
    telefon: Mapped[str | None] = mapped_column(String(50))
    adresse: Mapped[str | None] = mapped_column(Text)  # Legacy, nutze addresses

    # Ansprechpartner
    ansprechpartner_name: Mapped[str | None] = mapped_column(String(200))
    ansprechpartner_email: Mapped[str | None] = mapped_column(String(200))
    ansprechpartner_telefon: Mapped[str | None] = mapped_column(String(50))

    # Liefertage (0=Montag, 6=Sonntag)
    liefertage: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))

    # Steuer-IDs (Deutschland)
    ust_id: Mapped[str | None] = mapped_column(String(20))  # USt-IdNr. (DE123456789)
    steuernummer: Mapped[str | None] = mapped_column(String(20))  # Finanzamt-Steuernummer

    # Zahlungsbedingungen
    payment_terms: Mapped[PaymentTerms] = mapped_column(
        SQLEnum(PaymentTerms), default=PaymentTerms.NET_14
    )
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))  # Kreditlimit in EUR

    # Preisgruppe (FK zu PriceList)
    price_list_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_lists.id", ondelete="SET NULL")
    )

    # Rabatt
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))

    # DATEV-Kontonummer (Debitor)
    datev_account: Mapped[str | None] = mapped_column(String(10))  # z.B. 10001

    # Notizen
    notizen: Mapped[str | None] = mapped_column(Text)

    # Status
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Beziehungen
    orders: Mapped[list["Order"]] = relationship(
        "Order", back_populates="kunde", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="kunde", cascade="all, delete-orphan"
    )
    addresses: Mapped[list["CustomerAddress"]] = relationship(
        "CustomerAddress", back_populates="customer", cascade="all, delete-orphan"
    )
    price_list: Mapped[Optional["PriceList"]] = relationship("PriceList")
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice", back_populates="customer", cascade="all, delete-orphan"
    )

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


class Subscription(Base):
    """
    Abonnement - Wiederkehrende Bestellungen.
    Wichtig für Forecast-Berechnung.
    """
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kunde_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    seed_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seeds.id"), nullable=False
    )

    # Bestellmenge
    menge: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    einheit: Mapped[str] = mapped_column(String(20), nullable=False)  # GRAMM, BUND, SCHALE

    # Intervall
    intervall: Mapped[SubscriptionInterval] = mapped_column(
        SQLEnum(SubscriptionInterval), nullable=False
    )
    liefertage: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))

    # Gültigkeit
    gueltig_von: Mapped[date] = mapped_column(Date, nullable=False)
    gueltig_bis: Mapped[date | None] = mapped_column(Date)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Beziehungen
    kunde: Mapped["Customer"] = relationship("Customer", back_populates="subscriptions")
    seed: Mapped["Seed"] = relationship("Seed")

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
from app.models.product import PriceList
from app.models.invoice import Invoice
