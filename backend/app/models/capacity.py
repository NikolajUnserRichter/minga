"""
Kapazitäts-Model für Ressourcenplanung
"""
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import String, Integer, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class ResourceType(str, Enum):
    """Typ der Ressource"""
    REGAL = "REGAL"
    TRAY = "TRAY"
    ARBEITSZEIT = "ARBEITSZEIT"


class Capacity(Base):
    """
    Kapazität - Verfügbare Ressourcen für Produktion.
    """
    __tablename__ = "capacities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Ressourcen-Info
    ressource_typ: Mapped[ResourceType] = mapped_column(
        SQLEnum(ResourceType), nullable=False
    )
    name: Mapped[str | None] = mapped_column(String(100))

    # Kapazitätswerte
    max_kapazitaet: Mapped[int] = mapped_column(Integer, nullable=False)
    aktuell_belegt: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    @property
    def verfuegbar(self) -> int:
        """Berechnet verfügbare Kapazität"""
        return max(0, self.max_kapazitaet - self.aktuell_belegt)

    @property
    def auslastung_prozent(self) -> float:
        """Berechnet Auslastung in Prozent"""
        if self.max_kapazitaet == 0:
            return 0.0
        return (self.aktuell_belegt / self.max_kapazitaet) * 100

    @property
    def ist_ueberlastet(self) -> bool:
        """Prüft ob Kapazität überlastet ist"""
        return self.aktuell_belegt > self.max_kapazitaet

    def __repr__(self) -> str:
        return f"<Capacity(typ={self.ressource_typ.value}, belegt={self.aktuell_belegt}/{self.max_kapazitaet})>"
