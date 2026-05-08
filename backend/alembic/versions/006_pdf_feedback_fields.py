"""Add fields requested in PDF feedback (GTIN, certification, BIO, multi-email, cooling, etc)

Revision ID: 006
Revises: 005
Create Date: 2026-05-08

Additive columns to support PDF feedback features:
- products: gtin (EAN-13/14), old_article_number, certification
- seed_batches: bio_zertifiziert, kontrollstelle, lieferschein_nr, in_production_at
- customers: email_purchasing, email_sales, email_billing
- grow_plans: cooling_days, cooling_shelf_life_days, process_type

No existing data is altered. All new columns are nullable or have a server default.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- products ----------
    op.add_column('products', sa.Column('gtin', sa.String(14), nullable=True))
    op.create_index(
        'ix_products_gtin',
        'products',
        ['gtin'],
        unique=True,
        postgresql_where=sa.text('gtin IS NOT NULL'),
    )
    op.add_column('products', sa.Column('old_article_number', sa.String(50), nullable=True))
    op.create_index('ix_products_old_article_number', 'products', ['old_article_number'])
    op.add_column('products', sa.Column('certification', sa.String(30), nullable=True))

    # ---------- seed_batches ----------
    op.add_column(
        'seed_batches',
        sa.Column('bio_zertifiziert', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )
    op.add_column('seed_batches', sa.Column('kontrollstelle', sa.String(100), nullable=True))
    op.add_column('seed_batches', sa.Column('lieferschein_nr', sa.String(50), nullable=True))
    op.add_column('seed_batches', sa.Column('in_production_at', sa.Date(), nullable=True))

    # ---------- customers ----------
    op.add_column('customers', sa.Column('email_purchasing', sa.String(200), nullable=True))
    op.add_column('customers', sa.Column('email_sales', sa.String(200), nullable=True))
    op.add_column('customers', sa.Column('email_billing', sa.String(200), nullable=True))

    # ---------- grow_plans ----------
    op.add_column('grow_plans', sa.Column('cooling_days', sa.Integer(), nullable=True))
    op.add_column('grow_plans', sa.Column('cooling_shelf_life_days', sa.Integer(), nullable=True))
    op.add_column(
        'grow_plans',
        sa.Column('process_type', sa.String(20), server_default='STANDARD', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('grow_plans', 'process_type')
    op.drop_column('grow_plans', 'cooling_shelf_life_days')
    op.drop_column('grow_plans', 'cooling_days')
    op.drop_column('customers', 'email_billing')
    op.drop_column('customers', 'email_sales')
    op.drop_column('customers', 'email_purchasing')
    op.drop_column('seed_batches', 'in_production_at')
    op.drop_column('seed_batches', 'lieferschein_nr')
    op.drop_column('seed_batches', 'kontrollstelle')
    op.drop_column('seed_batches', 'bio_zertifiziert')
    op.drop_column('products', 'certification')
    op.drop_index('ix_products_old_article_number', table_name='products')
    op.drop_column('products', 'old_article_number')
    op.drop_index('ix_products_gtin', table_name='products')
    op.drop_column('products', 'gtin')
