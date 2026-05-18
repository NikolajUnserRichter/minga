"""Tester feedback round 1: location description + supplier product_group/BIO + new article types

Revision ID: 012
Revises: 011
Create Date: 2026-05-11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '012'
down_revision: Union[str, None] = '011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- inventory_locations: description ----
    op.add_column('inventory_locations', sa.Column('description', sa.Text(), nullable=True))

    # ---- suppliers: product_group + BIO ----
    # product_group: SAATGUT | SUBSTRAT | VERPACKUNG | ARBEITSMATERIAL | SONSTIGES
    op.add_column('suppliers', sa.Column('product_group', sa.String(30), nullable=True))
    op.add_column('suppliers', sa.Column('is_organic', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('suppliers', sa.Column('bio_certificate_url', sa.String(500), nullable=True))
    op.add_column('suppliers', sa.Column('bio_certificate_valid_until', sa.Date(), nullable=True))
    op.add_column('suppliers', sa.Column('bio_kontrollstelle', sa.String(100), nullable=True))

    # ---- subscriptions: Produkt + Variante (legacy seed_id bleibt) ----
    op.add_column('subscriptions', sa.Column('product_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('subscriptions', sa.Column('product_variant_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    # seed_id nullable machen — Subscriptions können jetzt auch Produkt-basiert sein
    try:
        op.alter_column('subscriptions', 'seed_id', nullable=True)
    except Exception:
        pass

    # ---- packaging_inventory: article_type (für Verpackung / Substrat / Pfandkiste) ----
    op.add_column(
        'packaging_inventory',
        sa.Column('article_type', sa.String(20), server_default='VERPACKUNG', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('packaging_inventory', 'article_type')
    op.drop_column('subscriptions', 'product_variant_id')
    op.drop_column('subscriptions', 'product_id')
    op.drop_column('suppliers', 'bio_kontrollstelle')
    op.drop_column('suppliers', 'bio_certificate_valid_until')
    op.drop_column('suppliers', 'bio_certificate_url')
    op.drop_column('suppliers', 'is_organic')
    op.drop_column('suppliers', 'product_group')
    op.drop_column('inventory_locations', 'description')
