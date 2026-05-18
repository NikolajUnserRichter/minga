"""App-Settings — Key/Value-Konfiguration zur Laufzeit (SMTP, künftig mehr)

Revision ID: 016
Revises: 015
Create Date: 2026-05-18

Generic key/value store für Settings, die zur Laufzeit aus dem Admin-Center
gesetzt werden können. is_secret=True bedeutet: Wert wird beim GET maskiert,
nur PATCH/SET ist möglich.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '016'
down_revision: Union[str, None] = '015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(80), primary_key=True),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('is_secret', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('app_settings')
