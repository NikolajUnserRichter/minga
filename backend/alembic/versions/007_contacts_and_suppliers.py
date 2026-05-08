"""Contacts (multiple Ansprechpartner) and Suppliers (mit Default + Backup je Saatgut)

Revision ID: 007
Revises: 006
Create Date: 2026-05-08

New entities:
- contacts: many contacts per customer (Ansprechpartner mit Rolle)
- suppliers: master data for seed suppliers
- seeds: supplier_id (default) + backup_supplier_id (FK to suppliers)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- suppliers ----------
    op.create_table(
        'suppliers',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('email', sa.String(200), nullable=True),
        sa.Column('telefon', sa.String(50), nullable=True),
        sa.Column('adresse', sa.Text(), nullable=True),
        sa.Column('ust_id', sa.String(20), nullable=True),
        sa.Column('notizen', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_suppliers_name', 'suppliers', ['name'])

    # ---------- contacts ----------
    op.create_table(
        'contacts',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('customer_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('email', sa.String(200), nullable=True),
        sa.Column('telefon', sa.String(50), nullable=True),
        # role: ALLGEMEIN | EINKAUF | VERTRIEB | BUCHHALTUNG | TECHNIK
        sa.Column('role', sa.String(30), server_default='ALLGEMEIN', nullable=False),
        sa.Column('is_primary', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('notizen', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_contacts_customer_id', 'contacts', ['customer_id'])

    # ---------- seeds: default + backup supplier ----------
    op.add_column('seeds', sa.Column('supplier_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('seeds', sa.Column('backup_supplier_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_seeds_supplier', 'seeds', 'suppliers', ['supplier_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_seeds_backup_supplier', 'seeds', 'suppliers', ['backup_supplier_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_seeds_supplier_id', 'seeds', ['supplier_id'])


def downgrade() -> None:
    op.drop_index('ix_seeds_supplier_id', table_name='seeds')
    op.drop_constraint('fk_seeds_backup_supplier', 'seeds', type_='foreignkey')
    op.drop_constraint('fk_seeds_supplier', 'seeds', type_='foreignkey')
    op.drop_column('seeds', 'backup_supplier_id')
    op.drop_column('seeds', 'supplier_id')
    op.drop_index('ix_contacts_customer_id', table_name='contacts')
    op.drop_table('contacts')
    op.drop_index('ix_suppliers_name', table_name='suppliers')
    op.drop_table('suppliers')
