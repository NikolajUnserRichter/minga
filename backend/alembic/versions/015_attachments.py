"""Attachments — Datei-Anhänge (BIO-Zertifikate, Datenblätter, Test-Reports)

Revision ID: 015
Revises: 014
Create Date: 2026-05-18

Polymorphe Attachment-Tabelle für Anhänge an Lieferant/Produkt/Erntecharge.
Die eigentlichen Dateien liegen im Filesystem (Railway-Volume bzw. IONOS-VPS-Volume)
unter STORAGE_ROOT/attachments/{entity_type}/{entity_id}/{storage_key}.
Spätere S3-Migration ohne Schema-Änderung möglich (StorageService-Abstraktion).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '015'
down_revision: Union[str, None] = '014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'attachments',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('entity_type', sa.String(20), nullable=False),  # supplier|product|harvest
        sa.Column('entity_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('storage_key', sa.String(500), nullable=False),  # relative path / S3 key
        sa.Column('certificate_type', sa.String(40), nullable=True),  # BIO|ANALYSE|DATENBLATT|...
        sa.Column('bio_kontrollstelle', sa.String(100), nullable=True),
        sa.Column('valid_until', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('uploaded_by', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index('ix_attachments_entity', 'attachments', ['entity_type', 'entity_id'])
    op.create_index('ix_attachments_valid_until', 'attachments', ['valid_until'])


def downgrade() -> None:
    op.drop_index('ix_attachments_valid_until', table_name='attachments')
    op.drop_index('ix_attachments_entity', table_name='attachments')
    op.drop_table('attachments')
