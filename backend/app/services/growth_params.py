"""Auflösung der Wachstumsparameter einer Aussaat.

Drei Ebenen, in dieser Reihenfolge:

1. **Charge** (`SeedBatch`) — chargenbedingte Abweichungen, einmal in den
   Stammdaten der Charge gepflegt statt bei jedem Aussaatzyklus.
2. **Saison** (`Seed.winter_*` bei SEASON_MODE=WINTER) — ein vollständiger
   eigener Satz, weil die Verzögerung in der Keimung ODER im Growroom
   entstehen kann. Nur wenn kein Winter-Satz gepflegt ist, greift die
   Legacy-Pauschale `winter_extra_tage`.
3. **Sorte** (`Seed`) — der Standardsatz.

Zusätzlich verschiebt `SeedBatch.zusatz_tage` das Erntefenster (Legacy;
wirkt weiterhin, damit bestehende Chargen sich nicht ändern).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session


@dataclass
class GrowthParams:
    keimdauer_tage: int
    wachstumsdauer_tage: int
    erntefenster_min_tage: int
    erntefenster_optimal_tage: int
    erntefenster_max_tage: int
    quelle: str  # SORTE | WINTER | CHARGE — für die Anzeige im Tagesplan


FIELDS = (
    "keimdauer_tage",
    "wachstumsdauer_tage",
    "erntefenster_min_tage",
    "erntefenster_optimal_tage",
    "erntefenster_max_tage",
)


def is_winter(db: Session) -> bool:
    from app.services.settings_service import get_setting

    return (get_setting(db, "SEASON_MODE") or "SOMMER").upper() == "WINTER"


def resolve_growth_params(db: Session, seed, seed_batch=None) -> GrowthParams:
    """Ermittelt den gültigen Parametersatz für eine Aussaat."""
    values = {f: getattr(seed, f) for f in FIELDS}
    quelle = "SORTE"

    if is_winter(db):
        winter = {f: getattr(seed, f"winter_{f}", None) for f in FIELDS}
        if any(v is not None for v in winter.values()):
            # Gepflegter Winter-Satz: einzelne Lücken fallen auf die Sorte zurück
            values.update({f: v for f, v in winter.items() if v is not None})
            quelle = "WINTER"
        elif seed.winter_extra_tage:
            # Legacy-Pauschale: wirkt nur aufs Erntefenster, wie bisher
            for f in ("erntefenster_min_tage", "erntefenster_optimal_tage", "erntefenster_max_tage"):
                values[f] += seed.winter_extra_tage
            quelle = "WINTER"

    if seed_batch is not None:
        batch_values = {f: getattr(seed_batch, f, None) for f in FIELDS}
        if any(v is not None for v in batch_values.values()):
            values.update({f: v for f, v in batch_values.items() if v is not None})
            quelle = "CHARGE"

        zusatz = seed_batch.zusatz_tage or 0
        if zusatz:
            for f in ("erntefenster_min_tage", "erntefenster_optimal_tage", "erntefenster_max_tage"):
                values[f] += zusatz
            quelle = "CHARGE"

    return GrowthParams(**values, quelle=quelle)
