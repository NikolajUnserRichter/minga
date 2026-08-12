"""Dienstplan: staff_shifts-Tabelle

Leichtgewichtiger Dienstplan — Mitarbeiter als Freitext-Name, Schicht =
Name + Tag + Zeitfenster (HH:MM) + Aufgabe.

Hinweis: Neue Tabellen erreichen bestehende Tenant-DBs über
Base.metadata.create_all beim Boot (tenancy.init_all_existing_tenants);
diese Revision hält das Alembic-Schema konsistent.

Revision ID: 021
Revises: 020
Create Date: 2026-08-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '021'
down_revision: Union[str, None] = '020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'staff_shifts',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('employee_name', sa.String(200), nullable=False, index=True),
        sa.Column('datum', sa.Date(), nullable=False, index=True),
        sa.Column('start_time', sa.String(5), nullable=True),
        sa.Column('end_time', sa.String(5), nullable=True),
        sa.Column('aufgabe', sa.String(200), nullable=True),
        sa.Column('notizen', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('staff_shifts')
