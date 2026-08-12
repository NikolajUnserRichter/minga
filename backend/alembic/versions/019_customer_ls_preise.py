"""Preise auf Lieferschein: per-Kunde-Flag show_prices_on_delivery_note

Einzelne Kunden wünschen Preise auf dem Lieferschein (z.B. zur direkten
Weiterberechnung). Default False → Lieferscheine bleiben für alle anderen
Kunden preisfrei.

Hinweis: Bestehende Tenant-DBs werden zusätzlich über tenancy._auto_migrate
beim Boot migriert; diese Revision hält das Alembic-Schema konsistent.

Revision ID: 019
Revises: 018
Create Date: 2026-08-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '019'
down_revision: Union[str, None] = '018'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('customers', sa.Column(
        'show_prices_on_delivery_note', sa.Boolean(),
        server_default=sa.text('0'), nullable=False,
    ))


def downgrade() -> None:
    op.drop_column('customers', 'show_prices_on_delivery_note')
