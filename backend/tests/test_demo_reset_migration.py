"""Demo-Reset migriert ein älteres Golden-Seed-Schema direkt nach dem Restore."""
import sqlite3

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.services.demo_reset_service import reset_demo_from_seed, snapshot_demo_seed
from app import tenancy


def test_reset_migrates_restored_seed_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(tenancy, "TENANTS_DIR", tmp_path)
    tenancy.registry.dispose_all()

    try:
        db_path = tenancy.provision_tenant("demo", seed_defaults=False)
        seed_path = snapshot_demo_seed("demo")["seed"]

        with sqlite3.connect(seed_path) as connection:
            connection.execute("ALTER TABLE customers DROP COLUMN pfand_abrechnung")
            connection.commit()
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        with sqlite3.connect(seed_path) as connection:
            seed_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(customers)")
            }
        assert "pfand_abrechnung" not in seed_columns

        result = reset_demo_from_seed("demo")

        engine = tenancy.registry.get_engine("demo")
        columns = {column["name"] for column in inspect(engine).get_columns("customers")}
        assert "pfand_abrechnung" in columns
        assert result == {"status": "reset", "slug": "demo", "migriert": True}

        with Session(engine) as session:
            assert session.scalars(select(Customer)).all() == []
    finally:
        tenancy.registry.dispose_all()
        db_path.unlink(missing_ok=True)
