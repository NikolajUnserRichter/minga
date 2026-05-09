"""Seed: per-Sorte Saatgut-Dichte (g pro Einheit) — antwortet "Wo wird das definiert?"

Revision ID: 010
Revises: 009
Create Date: 2026-05-09
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'seeds',
        sa.Column('saatgut_pro_einheit_gramm', sa.Numeric(8, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('seeds', 'saatgut_pro_einheit_gramm')
