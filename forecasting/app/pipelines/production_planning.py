"""
Production Planning Pipeline
Übersetzt Absatzprognosen in Produktionsvorschläge
"""
import math
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.pipelines.sales_forecast import SalesForecastPipeline

settings = get_settings()


class ProductionPlanningPipeline:
    """
    Pipeline für Produktionsplanung.

    Übersetzt Absatzprognosen in:
    - Benötigte Trays
    - Aussaat-Termine
    - Kapazitätswarnungen
    """

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or settings.database_url
        self.engine = create_engine(self.database_url)
        self.Session = sessionmaker(bind=self.engine)
        self.sales_pipeline = SalesForecastPipeline(self.database_url)

    def load_seed_parameters(self, seed_id: UUID) -> dict:
        """
        Lädt Wachstumsparameter für ein Saatgut.
        """
        query = text("""
            SELECT
                id,
                name,
                keimdauer_tage,
                wachstumsdauer_tage,
                erntefenster_min_tage,
                erntefenster_optimal_tage,
                erntefenster_max_tage,
                ertrag_gramm_pro_tray,
                verlustquote_prozent
            FROM seeds
            WHERE id = :seed_id AND aktiv = true
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query, {"seed_id": str(seed_id)}).fetchone()

        if not result:
            raise ValueError(f"Seed {seed_id} not found or inactive")

        return {
            "id": result.id,
            "name": result.name,
            "keimdauer_tage": result.keimdauer_tage,
            "wachstumsdauer_tage": result.wachstumsdauer_tage,
            "erntefenster_min_tage": result.erntefenster_min_tage,
            "erntefenster_optimal_tage": result.erntefenster_optimal_tage,
            "erntefenster_max_tage": result.erntefenster_max_tage,
            "ertrag_gramm_pro_tray": float(result.ertrag_gramm_pro_tray),
            "verlustquote_prozent": float(result.verlustquote_prozent)
        }

    def load_current_capacity(self) -> dict:
        """
        Lädt aktuelle Kapazitätsauslastung.
        """
        query = text("""
            SELECT
                ressource_typ,
                max_kapazitaet,
                aktuell_belegt
            FROM capacities
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query)
            capacities = {
                row.ressource_typ: {
                    "max": row.max_kapazitaet,
                    "current": row.aktuell_belegt,
                    "available": row.max_kapazitaet - row.aktuell_belegt
                }
                for row in result
            }

        return capacities

    def load_planned_production(self, from_date: date, to_date: date) -> list[dict]:
        """
        Lädt bereits geplante Produktion für Kapazitätsberechnung.
        """
        query = text("""
            SELECT
                ps.aussaat_datum,
                ps.empfohlene_trays,
                s.name as seed_name
            FROM production_suggestions ps
            JOIN seeds s ON s.id = ps.seed_id
            WHERE ps.aussaat_datum BETWEEN :from_date AND :to_date
                AND ps.status IN ('VORGESCHLAGEN', 'GENEHMIGT')
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query, {
                "from_date": from_date,
                "to_date": to_date
            })
            return [
                {
                    "date": str(row.aussaat_datum),
                    "trays": row.empfohlene_trays,
                    "seed_name": row.seed_name
                }
                for row in result
            ]

    def calculate_required_trays(
        self,
        required_quantity_gramm: float,
        seed_params: dict
    ) -> int:
        """
        Berechnet benötigte Trays für eine Menge.

        Berücksichtigt:
        - Ertrag pro Tray
        - Verlustquote
        """
        ertrag_pro_tray = seed_params["ertrag_gramm_pro_tray"]
        verlust_faktor = 1 - (seed_params["verlustquote_prozent"] / 100)
        effektiver_ertrag = ertrag_pro_tray * verlust_faktor

        if effektiver_ertrag <= 0:
            return 0

        return math.ceil(required_quantity_gramm / effektiver_ertrag)

    def calculate_sow_date(
        self,
        harvest_date: date,
        seed_params: dict
    ) -> date:
        """
        Berechnet Aussaat-Datum für gewünschtes Erntedatum.
        """
        total_days = (
            seed_params["keimdauer_tage"] +
            seed_params["wachstumsdauer_tage"]
        )
        return harvest_date - timedelta(days=total_days)

    def check_capacity_warnings(
        self,
        sow_date: date,
        required_trays: int,
        capacities: dict,
        planned: list[dict]
    ) -> list[dict]:
        """
        Prüft auf Kapazitätswarnungen.
        """
        warnings = []

        # Bereits geplante Trays für diesen Tag
        already_planned = sum(
            p["trays"] for p in planned
            if p["date"] == sow_date.isoformat()
        )

        regal_capacity = capacities.get("REGAL", {"max": 100, "current": 0, "available": 100})
        total_after = regal_capacity["current"] + already_planned + required_trays

        if total_after > regal_capacity["max"]:
            warnings.append({
                "type": "KAPAZITAET",
                "message": f"Regalkapazität überschritten: {total_after}/{regal_capacity['max']}",
                "severity": "high"
            })
        elif total_after > regal_capacity["max"] * 0.9:
            warnings.append({
                "type": "KAPAZITAET",
                "message": f"Regalkapazität fast erreicht: {total_after}/{regal_capacity['max']}",
                "severity": "medium"
            })

        # Aussaat in Vergangenheit
        if sow_date < date.today():
            warnings.append({
                "type": "UNTERDECKUNG",
                "message": f"Aussaat-Datum liegt in der Vergangenheit ({sow_date})",
                "severity": "high"
            })

        return warnings

    def create_production_plan(
        self,
        seed_id: UUID,
        horizon_days: int = 14
    ) -> list[dict]:
        """
        Erstellt vollständigen Produktionsplan.

        Returns:
            [
                {
                    "harvest_date": "2026-02-05",
                    "sow_date": "2026-01-25",
                    "seed_id": "...",
                    "seed_name": "Sonnenblume",
                    "forecast_quantity": 3500.0,
                    "required_trays": 12,
                    "warnings": [...],
                    "confidence": {
                        "lower": 2800,
                        "upper": 4200
                    }
                },
                ...
            ]
        """
        # Parameter laden
        seed_params = self.load_seed_parameters(seed_id)
        capacities = self.load_current_capacity()

        # Forecast abrufen
        forecast = self.sales_pipeline.run_forecast(seed_id, horizon_days)

        # Geplante Produktion für Kapazitätsprüfung
        today = date.today()
        planned = self.load_planned_production(
            today,
            today + timedelta(days=horizon_days)
        )

        production_plan = []

        for fc in forecast:
            harvest_date = date.fromisoformat(fc["date"])
            sow_date = self.calculate_sow_date(harvest_date, seed_params)

            required_quantity = fc["total_quantity"]
            required_trays = self.calculate_required_trays(required_quantity, seed_params)

            warnings = self.check_capacity_warnings(
                sow_date, required_trays, capacities, planned
            )

            production_plan.append({
                "harvest_date": fc["date"],
                "sow_date": sow_date.isoformat(),
                "seed_id": str(seed_id),
                "seed_name": seed_params["name"],
                "forecast_quantity": required_quantity,
                "required_trays": required_trays,
                "warnings": warnings,
                "confidence": {
                    "lower": fc["lower_bound"],
                    "upper": fc["upper_bound"]
                }
            })

            # Für Kapazitätsprüfung merken
            planned.append({
                "date": sow_date.isoformat(),
                "trays": required_trays,
                "seed_name": seed_params["name"]
            })

        return production_plan


def create_production_plan_for_product(
    seed_id: UUID,
    horizon_days: int = 14
) -> list[dict]:
    """
    Convenience-Funktion für Produktionsplanung.
    """
    pipeline = ProductionPlanningPipeline()
    return pipeline.create_production_plan(seed_id, horizon_days)
