"""Product variants - packaging size variants per product (instead of separate Products)

Revision ID: 008
Revises: 007
Create Date: 2026-05-09

Each product can have multiple variants representing different packaging
sizes/mixes (e.g. "12er Kiste", "6er Karton", "Tray", "1kg lose").
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'product_variants',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('parent_product_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('packaging_unit_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('items_per_pack', sa.Integer(), server_default='1', nullable=False),
        sa.Column('sku_suffix', sa.String(20), nullable=True),
        sa.Column('name_suffix', sa.String(100), nullable=True),
        sa.Column('gtin', sa.String(14), nullable=True),
        sa.Column('price_override', sa.Numeric(10, 2), nullable=True),
        sa.Column('weight_grams', sa.Numeric(10, 3), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['parent_product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['packaging_unit_id'], ['units_of_measure.id'], ondelete='RESTRICT'),
    )
    op.create_index('ix_product_variants_parent', 'product_variants', ['parent_product_id'])
    op.create_index(
        'ix_product_variants_gtin',
        'product_variants',
        ['gtin'],
        unique=True,
        postgresql_where=sa.text('gtin IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('ix_product_variants_gtin', table_name='product_variants')
    op.drop_index('ix_product_variants_parent', table_name='product_variants')
    op.drop_table('product_variants')
