"""Demo-Reset: Golden-Seed-Snapshot + Restore (Datei-Swap)."""
from pathlib import Path

import pytest

from app.services import demo_reset_service as drs


class _FakeRegistry:
    """Minimaler Registry-Stub: kennt nur den Pfad + zählt dispose-Aufrufe."""
    def __init__(self, db_path: Path):
        self._db_path = db_path
        self.disposed = 0

    def path_for(self, slug):
        return self._db_path

    def dispose_tenant(self, slug):
        self.disposed += 1

    def get_engine(self, slug):  # nur für snapshot (Checkpoint) — hier ungenutzt
        raise RuntimeError("kein Engine im Test")


@pytest.fixture
def demo_db(tmp_path, monkeypatch):
    db = tmp_path / "demo.db"
    db.write_text("LIVE-DATA")
    fake = _FakeRegistry(db)
    # registry wird in den Funktionen lazy importiert → dort patchen
    monkeypatch.setattr("app.tenancy.registry", fake, raising=False)
    return db, fake


def test_reset_without_seed_is_skipped(demo_db):
    db, fake = demo_db
    result = drs.reset_demo_from_seed("demo")
    assert result["status"] == "skipped"
    assert db.read_text() == "LIVE-DATA"  # unverändert


def test_reset_restores_seed_and_clears_sidecars(demo_db):
    db, fake = demo_db
    # Golden-Seed + WAL/SHM-Sidecars anlegen
    drs._seed_path(db).write_text("GOLDEN-SEED")
    db.with_name("demo.db-wal").write_text("x")
    db.with_name("demo.db-shm").write_text("x")

    result = drs.reset_demo_from_seed("demo")
    assert result["status"] == "reset"
    assert db.read_text() == "GOLDEN-SEED"          # Live-DB = Seed
    assert fake.disposed == 1                        # Engine wurde geschlossen
    assert not db.with_name("demo.db-wal").exists()  # Sidecars verworfen
    assert not db.with_name("demo.db-shm").exists()
