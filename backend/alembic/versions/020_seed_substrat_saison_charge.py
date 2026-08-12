"""Substrattyp + Winterzyklus (Sorte), Erntefenster-Abweichung (Saatgut-Charge)

- seeds.substrat: Substrattyp für die Aussaat-Arbeitsanweisung
- seeds.winter_extra_tage: zusätzliche Wachstumstage wenn SEASON_MODE=WINTER
- seed_batches.zusatz_tage: chargen-spezifische Erntefenster-Verschiebung
  (z.B. +1 Tag bei langsam keimender Charge)

Hinweis: Bestehende Tenant-DBs werden über tenancy._auto_migrate migriert;
diese Revision hält das Alembic-Schema konsistent.

Revision ID: 020
Revises: 019
Create Date: 2026-08-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '020'
down_revision: Union[str, None] = '019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('seeds', sa.Column('substrat', sa.String(100), nullable=True))
    op.add_column('seeds', sa.Column('winter_extra_tage', sa.Integer(), server_default='0', nullable=False))
    op.add_column('seed_batches', sa.Column('zusatz_tage', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('seed_batches', 'zusatz_tage')
    op.drop_column('seeds', 'winter_extra_tage')
    op.drop_column('seeds', 'substrat')
