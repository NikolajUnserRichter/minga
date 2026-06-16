"""Backfill Kundennummern für Bestandskunden ohne customer_number

Revision ID: 017
Revises: 016
Create Date: 2026-06-16

Kunden, die vor Einführung des customer_number-Felds (Migration 002 /
Auto-Vergabe in sales.create_customer) angelegt wurden, haben
customer_number = NULL und tauchen daher ohne Nummer auf Belegen auf.

Diese Migration vergibt allen Kunden ohne Nummer fortlaufende KD-NNNNN-
Nummern nach demselben Schema wie die Laufzeit-Auto-Vergabe und knüpft an
die aktuell höchste vorhandene KD-Nummer an (keine Kollisionen).
Sortierung deterministisch nach created_at, name, id.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '017'
down_revision: Union[str, None] = '016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Höchste bestehende KD-Nummer ermitteln (Python-seitig robust geparst)
    existing = bind.execute(
        sa.text("SELECT customer_number FROM customers WHERE customer_number LIKE 'KD-%'")
    ).fetchall()
    max_num = 10000
    for (cn,) in existing:
        try:
            n = int(str(cn).split("-")[-1])
        except (ValueError, AttributeError, IndexError):
            continue
        if n > max_num:
            max_num = n

    # 2) Kunden ohne Nummer deterministisch sortiert holen
    missing = bind.execute(
        sa.text(
            "SELECT id FROM customers "
            "WHERE customer_number IS NULL OR customer_number = '' "
            "ORDER BY created_at, name, id"
        )
    ).fetchall()

    # 3) Fortlaufend vergeben
    next_num = max_num + 1
    for (cid,) in missing:
        bind.execute(
            sa.text("UPDATE customers SET customer_number = :cn WHERE id = :id"),
            {"cn": f"KD-{next_num:05d}", "id": cid},
        )
        next_num += 1


def downgrade() -> None:
    # Backfill ist nicht eindeutig rückführbar (vergebene vs. manuell gesetzte
    # Nummern lassen sich nachträglich nicht unterscheiden) -> bewusst No-op.
    pass
