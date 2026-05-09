"""Refine PDF feedback per follow-up: drop multi-email Customer cols,
move cooling/process from GrowPlan to Seed, replace supplier_id/backup
with m2m seed_suppliers.

Revision ID: 009
Revises: 008
Create Date: 2026-05-09

User clarification:
- Kunde: keep only Haupt-E-Mail + Contact-Liste (mit Abteilung)
- Sorte: kann mehrere Lieferanten haben (nicht nur 2 mit Priorität)
- Sorte: Kühlung-Schritt + Prozessvariante gehören zur Sorte, nicht zum GrowPlan
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- customers: drop department-emails ----------
    # The user wants per-Ansprechpartner emails (already supported by Contact)
    # rather than departmental columns on Customer.
    op.drop_column('customers', 'email_purchasing')
    op.drop_column('customers', 'email_sales')
    op.drop_column('customers', 'email_billing')

    # ---------- seeds: cooling phase + process variant ----------
    op.add_column('seeds', sa.Column('cooling_days', sa.Integer(), nullable=True))
    op.add_column('seeds', sa.Column('cooling_shelf_life_days', sa.Integer(), nullable=True))
    op.add_column(
        'seeds',
        sa.Column('process_type', sa.String(30), server_default='STANDARD', nullable=False),
    )

    # ---------- seeds: drop old default+backup supplier columns ----------
    # Replaced by seed_suppliers m2m.
    op.drop_index('ix_seeds_supplier_id', table_name='seeds')
    op.drop_constraint('fk_seeds_backup_supplier', 'seeds', type_='foreignkey')
    op.drop_constraint('fk_seeds_supplier', 'seeds', type_='foreignkey')
    op.drop_column('seeds', 'backup_supplier_id')
    op.drop_column('seeds', 'supplier_id')

    # ---------- seed_suppliers (m2m) ----------
    op.create_table(
        'seed_suppliers',
        sa.Column('seed_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('supplier_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('notizen', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('seed_id', 'supplier_id'),
        sa.ForeignKeyConstraint(['seed_id'], ['seeds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_seed_suppliers_supplier_id', 'seed_suppliers', ['supplier_id'])

    # ---------- grow_plans: drop cooling/process (moved to seeds) ----------
    op.drop_column('grow_plans', 'cooling_days')
    op.drop_column('grow_plans', 'cooling_shelf_life_days')
    op.drop_column('grow_plans', 'process_type')


def downgrade() -> None:
    op.add_column(
        'grow_plans',
        sa.Column('process_type', sa.String(20), server_default='STANDARD', nullable=False),
    )
    op.add_column('grow_plans', sa.Column('cooling_shelf_life_days', sa.Integer(), nullable=True))
    op.add_column('grow_plans', sa.Column('cooling_days', sa.Integer(), nullable=True))
    op.drop_index('ix_seed_suppliers_supplier_id', table_name='seed_suppliers')
    op.drop_table('seed_suppliers')
    op.add_column('seeds', sa.Column('supplier_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('seeds', sa.Column('backup_supplier_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_seeds_supplier', 'seeds', 'suppliers', ['supplier_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_seeds_backup_supplier', 'seeds', 'suppliers', ['backup_supplier_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_seeds_supplier_id', 'seeds', ['supplier_id'])
    op.drop_column('seeds', 'process_type')
    op.drop_column('seeds', 'cooling_shelf_life_days')
    op.drop_column('seeds', 'cooling_days')
    op.add_column('customers', sa.Column('email_billing', sa.String(200), nullable=True))
    op.add_column('customers', sa.Column('email_sales', sa.String(200), nullable=True))
    op.add_column('customers', sa.Column('email_purchasing', sa.String(200), nullable=True))
