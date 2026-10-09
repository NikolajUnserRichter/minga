"""SEPA-Lastschriftmandate (B10, Gernot 08.10.2026).

Bankdaten liegen bewusst NICHT am Kunden: Die Kunden-Endpunkte erreicht auch
die Halle (production_staff, lesend und schreibend). Mandate pflegt nur die
Geldseite über den eigenen Router /api/v1/sepa (Admin und Buchhaltung).

Die Gläubiger-ID gehört MingaGreens, nicht dem Kunden — sie steht einmal in
den Firmeneinstellungen (app_settings: COMPANY_SEPA_GLAEUBIGER_ID).
"""
import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Enum as SQLEnum, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.database import Base


class Zahlungsart(str, Enum):
    """Wie ein Kunde zahlt. NULL am Kunden und an der Rechnung = Überweisung
    (Altbestand vor B10)."""
    UEBERWEISUNG = "UEBERWEISUNG"
    LASTSCHRIFT = "LASTSCHRIFT"


class Mandatsart(str, Enum):
    """CORE = SEPA-Basislastschrift, B2B = SEPA-Firmenlastschrift."""
    CORE = "CORE"
    B2B = "B2B"


class LastschriftStatus(str, Enum):
    """Stand des Einzugs einer Lastschriftrechnung.

    AUSSTEHEND: festgeschrieben, Einzug steht aus — nicht mahnfähig.
    EINGEZOGEN: Einzug als Zahlung gebucht.
    RUECKLASTSCHRIFT: Einzug zurückgegeben — ab jetzt normal mahnfähig.
    """
    AUSSTEHEND = "AUSSTEHEND"
    EINGEZOGEN = "EINGEZOGEN"
    RUECKLASTSCHRIFT = "RUECKLASTSCHRIFT"


class SepaMandat(Base):
    """Ein Lastschriftmandat eines Kunden. Höchstens eines je Kunde ist aktiv."""
    __tablename__ = "sepa_mandates"
    __table_args__ = (
        # Höchstens ein aktives Mandat je Kunde: partieller Unique-Index.
        # create_all legt ihn mit der (neuen) Tabelle an.
        Index(
            "uq_sepa_mandates_aktiv_je_kunde", "customer_id",
            unique=True, sqlite_where=text("aktiv = 1"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Kein Cascade: Der Gläubiger muss den Mandatsnachweis aufbewahren. Ein
    # Kunde mit Mandat wird deshalb nur deaktiviert (Customer.can_be_deleted).
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id"), nullable=False, index=True
    )
    mandatsreferenz: Mapped[str] = mapped_column(String(35), nullable=False, unique=True)
    mandatsart: Mapped[Mandatsart] = mapped_column(
        SQLEnum(Mandatsart, length=4), nullable=False, default=Mandatsart.CORE
    )
    unterschrieben_am: Mapped[date] = mapped_column(Date, nullable=False)
    kontoinhaber: Mapped[str] = mapped_column(String(70), nullable=False)
    iban: Mapped[str] = mapped_column(String(34), nullable=False)
    bic: Mapped[Optional[str]] = mapped_column(String(11))
    bank_name: Mapped[Optional[str]] = mapped_column(String(100))
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    widerrufen_am: Mapped[Optional[date]] = mapped_column(Date)
    letzter_einzug_am: Mapped[Optional[date]] = mapped_column(Date)
    #: Änderungsprotokoll, nur anhängen: {am, von, feld, alt, neu}; IBAN maskiert.
    #: JSON-Spalte ohne Mutationserkennung — immer eine NEUE Liste zuweisen.
    aenderungen: Mapped[Optional[list]] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(100))

    customer: Mapped["Customer"] = relationship("Customer", back_populates="sepa_mandate")

    def __repr__(self) -> str:
        return f"<SepaMandat(ref='{self.mandatsreferenz}', aktiv={self.aktiv})>"
