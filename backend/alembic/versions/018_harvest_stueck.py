"""Ernte in Stück: einheit + Stück-Felder an harvests

Minga erntet ganze Schalen (nicht geschnitten/gewogen). Ernten können daher
wahlweise in Gramm ("G", bisheriges Verhalten) oder Stück ("STK") erfasst
werden. Bei STK-Ernten wird menge_gramm als 0 gespeichert — die Spalte bleibt
NOT NULL (SQLite-Tenant-DBs erlauben kein nachträgliches Lockern) und 0
verfälscht keine Gramm-Aggregationen.

Hinweis: Bestehende Tenant-DBs werden zusätzlich über tenancy._auto_migrate
beim Boot migriert; diese Revision hält das Alembic-Schema konsistent.

Revision ID: 018
Revises: 017
Create Date: 2026-08-11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '018'
down_revision: Union[str, None] = '017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('harvests', sa.Column('einheit', sa.String(10), server_default='G', nullable=False))
    op.add_column('harvests', sa.Column('menge_stueck', sa.Integer(), nullable=True))
    op.add_column('harvests', sa.Column('verlust_stueck', sa.Integer(), nullable=True))
    op.add_column('harvests', sa.Column('stueck_pro_kiste', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('harvests', 'stueck_pro_kiste')
    op.drop_column('harvests', 'verlust_stueck')
    op.drop_column('harvests', 'menge_stueck')
    op.drop_column('harvests', 'einheit')
