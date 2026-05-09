"""Order line links to ProductVariant (Verpackungsgröße statt Unit-String)

Revision ID: 011
Revises: 010
Create Date: 2026-05-09
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '011'
down_revision: Union[str, None] = '010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'order_lines',
        sa.Column('product_variant_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_order_lines_variant',
        'order_lines',
        'product_variants',
        ['product_variant_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_order_lines_variant_id', 'order_lines', ['product_variant_id'])


def downgrade() -> None:
    op.drop_index('ix_order_lines_variant_id', table_name='order_lines')
    op.drop_constraint('fk_order_lines_variant', 'order_lines', type_='foreignkey')
    op.drop_column('order_lines', 'product_variant_id')
