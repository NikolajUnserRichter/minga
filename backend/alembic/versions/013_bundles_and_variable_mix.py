"""Bundle-Komponenten (Mischkisten) + variable Mix-Produkte (Gastrotray)

Revision ID: 013
Revises: 012
Create Date: 2026-05-11

Zwei Bundle-Modi:
- FIXED: products.is_bundle=True + Komponenten in bundle_components Tabelle
  (z.B. Genussmix = 1× Sonnenblume + 1× Rucola + 1× Erbse)
- VARIABLE: products.is_variable_bundle=True + min/max-Slots (1-8); Sorten
  werden je Bestell-Position gewählt und in order_lines.variable_bundle_selections
  gespeichert (z.B. Gastrotray mit 8 vom Kunden gewählten Sorten)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '013'
down_revision: Union[str, None] = '012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- bundle_components: FIXED-Bundle Definition ----
    op.create_table(
        'bundle_components',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('parent_product_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('child_product_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quantity', sa.Numeric(10, 2), server_default='1', nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['parent_product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['child_product_id'], ['products.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('parent_product_id', 'child_product_id', name='uq_bundle_component'),
    )
    op.create_index('ix_bundle_components_parent', 'bundle_components', ['parent_product_id'])

    # ---- products: VARIABLE-Bundle Flags ----
    op.add_column('products', sa.Column('is_variable_bundle', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('products', sa.Column('variable_bundle_min_slots', sa.Integer(), nullable=True))
    op.add_column('products', sa.Column('variable_bundle_max_slots', sa.Integer(), nullable=True))

    # ---- order_lines: per-Bestellung gewählte Sorten für Variable Bundles ----
    # Format: [{"product_id": "uuid", "quantity": 1}, ...]
    op.add_column('order_lines', sa.Column('variable_bundle_selections', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('order_lines', 'variable_bundle_selections')
    op.drop_column('products', 'variable_bundle_max_slots')
    op.drop_column('products', 'variable_bundle_min_slots')
    op.drop_column('products', 'is_variable_bundle')
    op.drop_index('ix_bundle_components_parent', table_name='bundle_components')
    op.drop_table('bundle_components')
