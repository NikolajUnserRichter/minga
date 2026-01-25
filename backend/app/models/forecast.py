"""
Forecast-Models: Forecast, ForecastAccuracy, ProductionSuggestion
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from sqlalchemy import String, Integer, Numeric, DateTime, Date, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class ForecastModelType(str, Enum):
    """Typ des Forecasting-Modells"""
    PROPHET = "PROPHET"
    ARIMA = "ARIMA"
    ENSEMBLE = "ENSEMBLE"
    MANUAL = "MANUAL"


class SuggestionStatus(str, Enum):
    """Status eines Produktionsvorschlags"""
    VORGESCHLAGEN = "VORGESCHLAGEN"
    GENEHMIGT = "GENEHMIGT"
    ABGELEHNT = "ABGELEHNT"
    UMGESETZT = "UMGESETZT"


class WarningType(str, Enum):
    """Typen von Produktionswarnungen"""
    UNTERDECKUNG = "UNTERDECKUNG"
    UEBERPRODUKTION = "UEBERPRODUKTION"
    KAPAZITAET = "KAPAZITAET"
    SAATGUT_NIEDRIG = "SAATGUT_NIEDRIG"


class Forecast(Base):
    """
    Absatzprognose - KI-generierte oder manuelle Vorhersage.
    """
    __tablename__ = "forecasts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    seed_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seeds.id"), nullable=False
    )
    kunde_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id")
    )

    # Prognosedatum und Horizont
    datum: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    horizont_tage: Mapped[int] = mapped_column(Integer, nullable=False)

    # Prognosewerte
    prognostizierte_menge: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    konfidenz_untergrenze: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    konfidenz_obergrenze: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    # Modell-Info
    modell_typ: Mapped[ForecastModelType] = mapped_column(
        SQLEnum(ForecastModelType), nullable=False
    )

    # Override durch Benutzer
    override_menge: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    override_grund: Mapped[str | None] = mapped_column(Text)
    override_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Beziehungen
    seed: Mapped["Seed"] = relationship("Seed")
    kunde: Mapped["Customer | None"] = relationship("Customer")
    accuracy: Mapped["ForecastAccuracy | None"] = relationship(
        "ForecastAccuracy", back_populates="forecast", uselist=False
    )
    suggestions: Mapped[list["ProductionSuggestion"]] = relationship(
        "ProductionSuggestion", back_populates="forecast"
    )

    @property
    def effektive_menge(self) -> Decimal:
        """Liefert Override-Menge falls vorhanden, sonst prognostizierte Menge"""
        return self.override_menge if self.override_menge is not None else self.prognostizierte_menge

    def __repr__(self) -> str:
        return f"<Forecast(id={self.id}, datum={self.datum}, menge={self.prognostizierte_menge})>"


class ForecastAccuracy(Base):
    """
    Forecast-Genauigkeit - Vergleich Prognose vs. Ist.
    """
    __tablename__ = "forecast_accuracy"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    forecast_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forecasts.id"), nullable=False, unique=True
    )

    # Ist-Werte
    ist_menge: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Berechnete Abweichungen
    abweichung_absolut: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    abweichung_prozent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # MAPE (Mean Absolute Percentage Error)
    mape: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Timestamp
    ausgewertet_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Beziehung
    forecast: Mapped["Forecast"] = relationship("Forecast", back_populates="accuracy")

    def berechne_abweichungen(self) -> None:
        """Berechnet Abweichungen basierend auf Forecast und Ist-Menge"""
        prognose = self.forecast.effektive_menge
        self.abweichung_absolut = self.ist_menge - prognose
        if prognose != 0:
            self.abweichung_prozent = (self.abweichung_absolut / prognose) * 100
            self.mape = abs(self.abweichung_prozent)
        else:
            self.abweichung_prozent = Decimal("0")
            self.mape = Decimal("0")

    def __repr__(self) -> str:
        return f"<ForecastAccuracy(id={self.id}, mape={self.mape})>"


class ProductionSuggestion(Base):
    """
    Produktionsvorschlag - Automatisch aus Forecast abgeleitet.
    """
    __tablename__ = "production_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    forecast_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forecasts.id"), nullable=False
    )
    seed_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seeds.id"), nullable=False
    )

    # Vorschlag
    empfohlene_trays: Mapped[int] = mapped_column(Integer, nullable=False)
    aussaat_datum: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    erwartete_ernte_datum: Mapped[date] = mapped_column(Date, nullable=False)

    # Status
    status: Mapped[SuggestionStatus] = mapped_column(
        SQLEnum(SuggestionStatus), default=SuggestionStatus.VORGESCHLAGEN
    )

    # Warnungen (JSON Array)
    warnungen: Mapped[dict | None] = mapped_column(JSONB, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    genehmigt_am: Mapped[datetime | None] = mapped_column(DateTime)
    genehmigt_von: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Beziehungen
    forecast: Mapped["Forecast"] = relationship("Forecast", back_populates="suggestions")
    seed: Mapped["Seed"] = relationship("Seed")

    def hat_warnung(self, typ: WarningType) -> bool:
        """Prüft ob eine bestimmte Warnung vorliegt"""
        if not self.warnungen:
            return False
        return any(w.get("typ") == typ.value for w in self.warnungen)

    def __repr__(self) -> str:
        return f"<ProductionSuggestion(id={self.id}, trays={self.empfohlene_trays})>"


# Imports für Type Hints
from app.models.seed import Seed
from app.models.customer import Customer
