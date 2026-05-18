"""Belegkette: Auftragsbestätigung, Lieferschein, Verpackungsliste

Revision ID: 014
Revises: 013
Create Date: 2026-05-18

Drei neue Tabellen für die DSGVO/HGB-konforme Belegkette pro Bestellung:
- order_confirmations: Auftragsbestätigung (AB) mit Nummernkreis AB-YYYYMMDD-NNNN
- delivery_notes: Lieferschein (LS) mit Nummernkreis LS-YYYYMMDD-NNNN
- packing_lists: Verpackungsliste 1:1 zu Lieferschein (PL-YYYYMMDD-NNNN)
- packing_list_items: Einzelpositionen mit Pfand-Container + Batch-Tracking

Status-Übergänge zu finalen Status (VERSENDET / GELIEFERT) machen das
Dokument immutable.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '014'
down_revision: Union[str, None] = '013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    confirmation_status = sa.Enum('ENTWURF', 'VERSENDET', name='confirmationstatus')
    delivery_note_status = sa.Enum('ENTWURF', 'AUSGESTELLT', 'GELIEFERT', name='deliverynotestatus')

    op.create_table(
        'order_confirmations',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('order_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('confirmation_number', sa.String(30), unique=True, nullable=False),
        sa.Column('status', confirmation_status, server_default='ENTWURF', nullable=False),
        sa.Column('issued_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('sent_to_email', sa.String(200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_order_confirmations_order', 'order_confirmations', ['order_id'])

    op.create_table(
        'delivery_notes',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('order_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('delivery_note_number', sa.String(30), unique=True, nullable=False),
        sa.Column('status', delivery_note_status, server_default='ENTWURF', nullable=False),
        sa.Column('issued_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('signed_by', sa.String(200), nullable=True),
        sa.Column('actual_delivery_date', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_delivery_notes_order', 'delivery_notes', ['order_id'])

    op.create_table(
        'packing_lists',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('delivery_note_id', sa.dialects.postgresql.UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column('packing_list_number', sa.String(30), unique=True, nullable=False),
        sa.Column('total_weight_g', sa.Numeric(12, 2), nullable=True),
        sa.Column('total_packages', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['delivery_note_id'], ['delivery_notes.id'], ondelete='CASCADE'),
    )

    op.create_table(
        'packing_list_items',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('packing_list_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('order_line_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('product_name', sa.String(255), nullable=False),
        sa.Column('quantity', sa.Numeric(12, 3), nullable=False),
        sa.Column('unit', sa.String(20), nullable=False),
        sa.Column('batch_number', sa.String(50), nullable=True),
        sa.Column('harvest_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_returnable_container', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('container_type', sa.String(30), nullable=True),
        sa.Column('container_count', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['packing_list_id'], ['packing_lists.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['order_line_id'], ['order_lines.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['harvest_id'], ['harvests.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_packing_list_items_pl', 'packing_list_items', ['packing_list_id'])


def downgrade() -> None:
    op.drop_index('ix_packing_list_items_pl', table_name='packing_list_items')
    op.drop_table('packing_list_items')
    op.drop_table('packing_lists')
    op.drop_index('ix_delivery_notes_order', table_name='delivery_notes')
    op.drop_table('delivery_notes')
    op.drop_index('ix_order_confirmations_order', table_name='order_confirmations')
    op.drop_table('order_confirmations')
    sa.Enum(name='deliverynotestatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='confirmationstatus').drop(op.get_bind(), checkfirst=True)
