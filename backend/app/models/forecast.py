from typing import Optional
"""
Forecast-Models: Forecast, ForecastManualAdjustment, ForecastAccuracy, ProductionSuggestion
Erweitert um vollständige Manual-Input-Funktionalität nach ERP-Anforderungen.
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from sqlalchemy import String, Integer, Numeric, DateTime, Date, ForeignKey, Text, Enum as SQLEnum, Boolean
from sqlalchemy.types import Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.database import Base


class ForecastModelType(str, Enum):
    """Typ des Forecasting-Modells"""
    PROPHET = "PROPHET"
    ARIMA = "ARIMA"
    ENSEMBLE = "ENSEMBLE"
    MANUAL = "MANUAL"


class AdjustmentType(str, Enum):
    """Typ der manuellen Anpassung"""
    ABSOLUTE = "ABSOLUTE"              # Absoluter Wert überschreibt
    PERCENTAGE_INCREASE = "PERCENTAGE_INCREASE"    # Prozentuale Erhöhung
    PERCENTAGE_DECREASE = "PERCENTAGE_DECREASE"    # Prozentuale Verringerung
    ADDITION = "ADDITION"              # Absoluter Wert wird addiert
    SUBTRACTION = "SUBTRACTION"        # Absoluter Wert wird subtrahiert


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

    Die Forecast-Entität speichert:
    - Automatisch berechnete Prognose (prognostizierte_menge)
    - Manuelle Anpassungen (über ForecastManualAdjustment)
    - Effektive Menge (nach Anwendung aller Anpassungen)
    """
    __tablename__ = "forecasts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )

    # Referenzen
    seed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seeds.id"), nullable=False, index=True
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("products.id"), index=True
    )
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("customers.id"), index=True
    )

    # Prognosedatum und Horizont
    datum: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    horizont_tage: Mapped[int] = mapped_column(Integer, nullable=False)

    # ==================== AUTOMATISCHE PROGNOSE ====================
    # Rohwert vom ML-Modell
    prognostizierte_menge: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    konfidenz_untergrenze: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    konfidenz_obergrenze: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    # Modell-Info
    modell_typ: Mapped[ForecastModelType] = mapped_column(
        SQLEnum(ForecastModelType), nullable=False
    )

    # ==================== EFFEKTIVE WERTE ====================
    # Diese Felder werden nach Anwendung manueller Anpassungen berechnet
    effektive_menge: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    hat_manuelle_anpassung: Mapped[bool] = mapped_column(Boolean, default=False)

    # ==================== DATENQUELLEN ====================
    # Welche Daten flossen in die Prognose ein
    basiert_auf_historisch: Mapped[bool] = mapped_column(Boolean, default=True)
    basiert_auf_abonnements: Mapped[bool] = mapped_column(Boolean, default=True)
    basiert_auf_saisonalitaet: Mapped[bool] = mapped_column(Boolean, default=True)
    basiert_auf_wochentag: Mapped[bool] = mapped_column(Boolean, default=True)

    # Anzahl historischer Datenpunkte
    historische_datenpunkte: Mapped[Optional[int]] = mapped_column(Integer)

    # ==================== LEGACY OVERRIDE FIELDS ====================
    # Für Rückwärtskompatibilität - neue Implementierung nutzt ForecastManualAdjustment
    override_menge: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    override_grund: Mapped[Optional[str]] = mapped_column(Text)
    override_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    override_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # ==================== BEZIEHUNGEN ====================
    seed: Mapped["Seed"] = relationship("Seed")
    product: Mapped[Optional["Product"]] = relationship("Product")
    customer: Mapped[Optional["Customer"]] = relationship("Customer")
    accuracy: Mapped[Optional["ForecastAccuracy"]] = relationship(
        "ForecastAccuracy", back_populates="forecast", uselist=False
    )
    suggestions: Mapped[list["ProductionSuggestion"]] = relationship(
        "ProductionSuggestion", back_populates="forecast"
    )
    manual_adjustments: Mapped[list["ForecastManualAdjustment"]] = relationship(
        "ForecastManualAdjustment",
        back_populates="forecast",
        cascade="all, delete-orphan",
        order_by="ForecastManualAdjustment.created_at.desc()"
    )

    def apply_manual_adjustments(self) -> None:
        """
        Wendet alle aktiven manuellen Anpassungen an und berechnet die effektive Menge.
        """
        result = self.prognostizierte_menge

        # Nur aktive (nicht rückgängig gemachte) Anpassungen anwenden
        active_adjustments = [adj for adj in self.manual_adjustments if adj.is_active]

        for adjustment in sorted(active_adjustments, key=lambda x: x.created_at):
            result = adjustment.apply_to(result)

        self.effektive_menge = result.quantize(Decimal("0.01"))
        self.hat_manuelle_anpassung = len(active_adjustments) > 0

    def get_forecast_breakdown(self) -> dict:
        """
        Gibt eine Aufschlüsselung der Forecast-Komponenten zurück:
        - Automatische Prognose
        - Manuelle Anpassungen
        - Finale effektive Menge
        """
        active_adjustments = [adj for adj in self.manual_adjustments if adj.is_active]

        return {
            "automatic_forecast": float(self.prognostizierte_menge),
            "confidence_lower": float(self.konfidenz_untergrenze) if self.konfidenz_untergrenze else None,
            "confidence_upper": float(self.konfidenz_obergrenze) if self.konfidenz_obergrenze else None,
            "model_type": self.modell_typ.value,
            "manual_adjustments": [
                {
                    "id": str(adj.id),
                    "type": adj.adjustment_type.value,
                    "value": float(adj.adjustment_value),
                    "reason": adj.reason,
                    "user": adj.user_name,
                    "timestamp": adj.created_at.isoformat(),
                }
                for adj in active_adjustments
            ],
            "effective_forecast": float(self.effektive_menge),
            "has_manual_adjustment": self.hat_manuelle_anpassung,
        }

    def __repr__(self) -> str:
        return f"<Forecast(id={self.id}, datum={self.datum}, effektiv={self.effektive_menge})>"


class ForecastManualAdjustment(Base):
    """
    Manuelle Forecast-Anpassung mit vollständigem Audit-Trail.

    Ermöglicht:
    - Absolute Wert-Überschreibung
    - Prozentuale Erhöhung/Verringerung
    - Pflichtkommentar für jede Anpassung
    - Rückgängig-Machung von Anpassungen
    """
    __tablename__ = "forecast_manual_adjustments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    forecast_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("forecasts.id", ondelete="CASCADE"), nullable=False
    )

    # ==================== ANPASSUNGSTYP ====================
    adjustment_type: Mapped[AdjustmentType] = mapped_column(
        SQLEnum(AdjustmentType), nullable=False
    )

    # Wert der Anpassung (Bedeutung abhängig vom Typ)
    # ABSOLUTE: Neuer absoluter Wert
    # PERCENTAGE_INCREASE/DECREASE: Prozentsatz (z.B. 10 für 10%)
    # ADDITION/SUBTRACTION: Absoluter Wert zum Addieren/Subtrahieren
    adjustment_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # ==================== BEGRÜNDUNG (PFLICHT) ====================
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # ==================== GÜLTIGKEITSBEREICH ====================
    # Optional: Anpassung nur für bestimmten Zeitraum
    valid_from: Mapped[Optional[date]] = mapped_column(Date)
    valid_until: Mapped[Optional[date]] = mapped_column(Date)

    # ==================== STATUS ====================
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    reverted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    reverted_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    revert_reason: Mapped[Optional[str]] = mapped_column(Text)

    # ==================== AUDIT ====================
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    user_name: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Beziehung
    forecast: Mapped["Forecast"] = relationship("Forecast", back_populates="manual_adjustments")

    def apply_to(self, base_value: Decimal) -> Decimal:
        """
        Wendet diese Anpassung auf einen Basiswert an.

        Args:
            base_value: Der Ausgangswert

        Returns:
            Decimal: Der angepasste Wert
        """
        if self.adjustment_type == AdjustmentType.ABSOLUTE:
            return self.adjustment_value

        elif self.adjustment_type == AdjustmentType.PERCENTAGE_INCREASE:
            multiplier = 1 + (self.adjustment_value / 100)
            return base_value * multiplier

        elif self.adjustment_type == AdjustmentType.PERCENTAGE_DECREASE:
            multiplier = 1 - (self.adjustment_value / 100)
            return max(base_value * multiplier, Decimal("0"))

        elif self.adjustment_type == AdjustmentType.ADDITION:
            return base_value + self.adjustment_value

        elif self.adjustment_type == AdjustmentType.SUBTRACTION:
            return max(base_value - self.adjustment_value, Decimal("0"))

        return base_value

    def revert(self, user_id: uuid.UUID = None, user_name: str = None, reason: str = None) -> None:
        """
        Macht diese Anpassung rückgängig.
        """
        self.is_active = False
        self.reverted_at = datetime.utcnow()
        self.reverted_by = user_id
        self.revert_reason = reason

    def __repr__(self) -> str:
        return f"<ForecastManualAdjustment(type={self.adjustment_type.value}, value={self.adjustment_value})>"


class ForecastAccuracy(Base):
    """
    Forecast-Genauigkeit - Vergleich Prognose vs. Ist.
    """
    __tablename__ = "forecast_accuracy"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    forecast_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("forecasts.id"), nullable=False, unique=True
    )

    # Ist-Werte
    ist_menge: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Berechnete Abweichungen (gegen effektive Menge)
    abweichung_absolut: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    abweichung_prozent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # MAPE (Mean Absolute Percentage Error)
    mape: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # War manuelle Anpassung aktiv?
    hatte_manuelle_anpassung: Mapped[bool] = mapped_column(Boolean, default=False)

    # Ursprüngliche Prognose (ohne manuelle Anpassung) - für Vergleich
    urspruengliche_prognose: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    abweichung_ohne_anpassung: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Timestamp
    ausgewertet_am: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Beziehung
    forecast: Mapped["Forecast"] = relationship("Forecast", back_populates="accuracy")

    def berechne_abweichungen(self) -> None:
        """Berechnet Abweichungen basierend auf Forecast und Ist-Menge"""
        # Gegen effektive Menge (mit manueller Anpassung)
        prognose = self.forecast.effektive_menge
        self.abweichung_absolut = self.ist_menge - prognose

        if prognose != 0:
            self.abweichung_prozent = (self.abweichung_absolut / prognose) * 100
            self.mape = abs(self.abweichung_prozent)
        else:
            self.abweichung_prozent = Decimal("0")
            self.mape = Decimal("0")

        # Speichere ob manuelle Anpassung aktiv war
        self.hatte_manuelle_anpassung = self.forecast.hat_manuelle_anpassung
        self.urspruengliche_prognose = self.forecast.prognostizierte_menge

        # Berechne auch Abweichung ohne manuelle Anpassung (für Vergleich)
        if self.forecast.prognostizierte_menge != 0:
            self.abweichung_ohne_anpassung = abs(
                (self.ist_menge - self.forecast.prognostizierte_menge)
                / self.forecast.prognostizierte_menge * 100
            )

    def __repr__(self) -> str:
        return f"<ForecastAccuracy(id={self.id}, mape={self.mape})>"


class ProductionSuggestion(Base):
    """
    Produktionsvorschlag - Automatisch aus Forecast abgeleitet.
    """
    __tablename__ = "production_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    forecast_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("forecasts.id"), nullable=False
    )
    seed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seeds.id"), nullable=False
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("products.id")
    )

    # Vorschlag
    empfohlene_trays: Mapped[int] = mapped_column(Integer, nullable=False)
    aussaat_datum: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    erwartete_ernte_datum: Mapped[date] = mapped_column(Date, nullable=False)

    # Berechnete Mengen
    erwartete_menge_gramm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    benoetigte_menge_gramm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    # Status
    status: Mapped[SuggestionStatus] = mapped_column(
        SQLEnum(SuggestionStatus), default=SuggestionStatus.VORGESCHLAGEN
    )

    # Warnungen (JSON Array)
    warnungen: Mapped[Optional[dict]] = mapped_column(JSON, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    genehmigt_am: Mapped[Optional[datetime]] = mapped_column(DateTime)
    genehmigt_von: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    genehmigt_von_name: Mapped[Optional[str]] = mapped_column(String(200))

    # Ablehnungsgrund
    ablehnungsgrund: Mapped[Optional[str]] = mapped_column(Text)

    # Beziehungen
    forecast: Mapped["Forecast"] = relationship("Forecast", back_populates="suggestions")
    seed: Mapped["Seed"] = relationship("Seed")
    product: Mapped[Optional["Product"]] = relationship("Product")

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
from app.models.product import Product
