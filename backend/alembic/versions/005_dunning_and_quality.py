"""Add dunning level to invoices and quality fields to harvests

Revision ID: 005
Revises: 004
Create Date: 2026-04-14
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Dunning level on invoices ---
    op.add_column("invoices", sa.Column("reminder_level", sa.Integer(), server_default="0", nullable=False))
    op.add_column("invoices", sa.Column("last_reminder_sent_at", sa.DateTime(), nullable=True))
    op.add_column("invoices", sa.Column("next_reminder_date", sa.Date(), nullable=True))

    op.create_index("ix_invoices_reminder_level", "invoices", ["reminder_level"])
    op.create_index("ix_invoices_next_reminder_date", "invoices", ["next_reminder_date"])

    # --- Quality control fields on harvests ---
    op.add_column("harvests", sa.Column("quality_approved", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("harvests", sa.Column("quality_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("harvests", "quality_notes")
    op.drop_column("harvests", "quality_approved")

    op.drop_index("ix_invoices_next_reminder_date", table_name="invoices")
    op.drop_index("ix_invoices_reminder_level", table_name="invoices")

    op.drop_column("invoices", "next_reminder_date")
    op.drop_column("invoices", "last_reminder_sent_at")
    op.drop_column("invoices", "reminder_level")
