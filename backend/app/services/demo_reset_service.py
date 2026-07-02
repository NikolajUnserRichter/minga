"""
Demo-Reset: setzt die Demo-Tenant-DB nächtlich auf einen sauberen Golden-Seed
zurück. So bleibt die offen beschreibbare Demo dauerhaft präsentabel.

Ablauf:
  * ``snapshot_demo_seed`` friert den aktuellen Stand als Golden-Kopie ein
    (``<slug>.seed.db``) — einmal beim Einrichten aufrufen.
  * ``reset_demo_from_seed`` tauscht die Live-DB gegen die Golden-Kopie
    (Engine vorher schließen; WAL/SHM verwerfen). Läuft im Scheduler.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DEMO_SLUG = "demo"


def _seed_path(db_path: Path) -> Path:
    return db_path.with_name(f"{db_path.stem}.seed.db")


def _remove_sidecars(db_path: Path) -> None:
    for suffix in ("-wal", "-shm"):
        side = db_path.with_name(db_path.name + suffix)
        if side.exists():
            try:
                side.unlink()
            except OSError as e:
                logger.warning(f"[demo-reset] konnte {side} nicht löschen: {e}")


def snapshot_demo_seed(slug: str = DEFAULT_DEMO_SLUG) -> dict:
    """Aktuellen DB-Stand als Golden-Seed sichern (überschreibt vorhandenen Seed)."""
    from app.tenancy import registry

    db_path = registry.path_for(slug)
    if not db_path.is_file():
        raise FileNotFoundError(f"Tenant-DB '{slug}' existiert nicht: {db_path}")

    # WAL in die Haupt-DB falten, damit die Kopie vollständig ist.
    try:
        with registry.get_engine(slug).begin() as conn:
            conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception as e:  # noqa: BLE001 — Checkpoint ist best-effort
        logger.warning(f"[demo-reset] wal_checkpoint fehlgeschlagen: {e}")

    registry.dispose_tenant(slug)
    seed = _seed_path(db_path)
    shutil.copy2(db_path, seed)
    logger.info(f"[demo-reset] Golden-Seed erstellt: {seed} ({seed.stat().st_size} bytes)")
    return {"status": "snapshotted", "seed": str(seed), "size_bytes": seed.stat().st_size}


def reset_demo_from_seed(slug: str = DEFAULT_DEMO_SLUG) -> dict:
    """Live-DB durch den Golden-Seed ersetzen. Ohne Seed: no-op (skip)."""
    from app.tenancy import registry

    db_path = registry.path_for(slug)
    seed = _seed_path(db_path)
    if not seed.is_file():
        logger.info(f"[demo-reset] kein Golden-Seed für '{slug}' — übersprungen")
        return {"status": "skipped", "reason": "no seed"}

    registry.dispose_tenant(slug)
    _remove_sidecars(db_path)
    shutil.copy2(seed, db_path)
    logger.info(f"[demo-reset] '{slug}' auf Golden-Seed zurückgesetzt")
    return {"status": "reset", "slug": slug}
