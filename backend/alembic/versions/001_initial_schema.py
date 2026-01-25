"""Initial Schema - Minga-Greens ERP

Revision ID: 001
Revises:
Create Date: 2026-01-23

Erstellt alle Basistabellen für das ERP-System.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Seeds (Saatgut-Sorten)
    op.create_table(
        'seeds',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(100), nullable=False, index=True),
        sa.Column('sorte', sa.String(100)),
        sa.Column('lieferant', sa.String(200)),
        sa.Column('keimdauer_tage', sa.Integer, nullable=False),
        sa.Column('wachstumsdauer_tage', sa.Integer, nullable=False),
        sa.Column('erntefenster_min_tage', sa.Integer, nullable=False),
        sa.Column('erntefenster_optimal_tage', sa.Integer, nullable=False),
        sa.Column('erntefenster_max_tage', sa.Integer, nullable=False),
        sa.Column('ertrag_gramm_pro_tray', sa.Numeric(10, 2), nullable=False),
        sa.Column('verlustquote_prozent', sa.Numeric(5, 2), server_default='0'),
        sa.Column('aktiv', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Seed Batches (Saatgut-Chargen)
    op.create_table(
        'seed_batches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('seed_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('seeds.id'), nullable=False),
        sa.Column('charge_nummer', sa.String(50), nullable=False, index=True),
        sa.Column('menge_gramm', sa.Numeric(10, 2), nullable=False),
        sa.Column('verbleibend_gramm', sa.Numeric(10, 2), nullable=False),
        sa.Column('mhd', sa.Date),
        sa.Column('lieferdatum', sa.Date),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Grow Batches (Wachstumschargen)
    op.create_table(
        'grow_batches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('seed_batch_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('seed_batches.id'), nullable=False),
        sa.Column('tray_anzahl', sa.Integer, nullable=False),
        sa.Column('aussaat_datum', sa.Date, nullable=False, index=True),
        sa.Column('erwartete_ernte_min', sa.Date, nullable=False),
        sa.Column('erwartete_ernte_optimal', sa.Date, nullable=False),
        sa.Column('erwartete_ernte_max', sa.Date, nullable=False),
        sa.Column('status', sa.String(20), server_default='KEIMUNG'),
        sa.Column('regal_position', sa.String(50)),
        sa.Column('notizen', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Harvests (Ernten)
    op.create_table(
        'harvests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('grow_batch_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('grow_batches.id'), nullable=False),
        sa.Column('ernte_datum', sa.Date, nullable=False, index=True),
        sa.Column('menge_gramm', sa.Numeric(10, 2), nullable=False),
        sa.Column('verlust_gramm', sa.Numeric(10, 2), server_default='0'),
        sa.Column('qualitaet_note', sa.Integer),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Customers (Kunden)
    op.create_table(
        'customers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(200), nullable=False, index=True),
        sa.Column('typ', sa.String(20), nullable=False),
        sa.Column('email', sa.String(200)),
        sa.Column('telefon', sa.String(50)),
        sa.Column('adresse', sa.Text),
        sa.Column('liefertage', postgresql.ARRAY(sa.Integer)),
        sa.Column('aktiv', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Orders (Bestellungen)
    op.create_table(
        'orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('kunde_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customers.id'), nullable=False),
        sa.Column('bestell_datum', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('liefer_datum', sa.Date, nullable=False, index=True),
        sa.Column('status', sa.String(20), server_default='OFFEN'),
        sa.Column('notizen', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Order Items (Bestellpositionen)
    op.create_table(
        'order_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('orders.id'), nullable=False),
        sa.Column('seed_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('seeds.id'), nullable=False),
        sa.Column('menge', sa.Numeric(10, 2), nullable=False),
        sa.Column('einheit', sa.String(20), nullable=False),
        sa.Column('preis_pro_einheit', sa.Numeric(10, 2)),
        sa.Column('harvest_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('harvests.id')),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Subscriptions (Abonnements)
    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('kunde_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customers.id'), nullable=False),
        sa.Column('seed_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('seeds.id'), nullable=False),
        sa.Column('menge', sa.Numeric(10, 2), nullable=False),
        sa.Column('einheit', sa.String(20), nullable=False),
        sa.Column('intervall', sa.String(20), nullable=False),
        sa.Column('liefertage', postgresql.ARRAY(sa.Integer)),
        sa.Column('gueltig_von', sa.Date, nullable=False),
        sa.Column('gueltig_bis', sa.Date),
        sa.Column('aktiv', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Forecasts
    op.create_table(
        'forecasts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('seed_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('seeds.id'), nullable=False),
        sa.Column('kunde_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customers.id')),
        sa.Column('datum', sa.Date, nullable=False, index=True),
        sa.Column('horizont_tage', sa.Integer, nullable=False),
        sa.Column('prognostizierte_menge', sa.Numeric(10, 2), nullable=False),
        sa.Column('konfidenz_untergrenze', sa.Numeric(10, 2)),
        sa.Column('konfidenz_obergrenze', sa.Numeric(10, 2)),
        sa.Column('modell_typ', sa.String(20), nullable=False),
        sa.Column('override_menge', sa.Numeric(10, 2)),
        sa.Column('override_grund', sa.Text),
        sa.Column('override_user_id', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Forecast Accuracy
    op.create_table(
        'forecast_accuracy',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('forecast_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('forecasts.id'), nullable=False, unique=True),
        sa.Column('ist_menge', sa.Numeric(10, 2), nullable=False),
        sa.Column('abweichung_absolut', sa.Numeric(10, 2)),
        sa.Column('abweichung_prozent', sa.Numeric(5, 2)),
        sa.Column('mape', sa.Numeric(5, 2)),
        sa.Column('ausgewertet_am', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Production Suggestions
    op.create_table(
        'production_suggestions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('forecast_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('forecasts.id'), nullable=False),
        sa.Column('seed_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('seeds.id'), nullable=False),
        sa.Column('empfohlene_trays', sa.Integer, nullable=False),
        sa.Column('aussaat_datum', sa.Date, nullable=False, index=True),
        sa.Column('erwartete_ernte_datum', sa.Date, nullable=False),
        sa.Column('status', sa.String(20), server_default='VORGESCHLAGEN'),
        sa.Column('warnungen', postgresql.JSONB, server_default='[]'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('genehmigt_am', sa.DateTime),
        sa.Column('genehmigt_von', postgresql.UUID(as_uuid=True)),
    )

    # Capacities
    op.create_table(
        'capacities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('ressource_typ', sa.String(20), nullable=False),
        sa.Column('name', sa.String(100)),
        sa.Column('max_kapazitaet', sa.Integer, nullable=False),
        sa.Column('aktuell_belegt', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )


def downgrade() -> None:
    op.drop_table('capacities')
    op.drop_table('production_suggestions')
    op.drop_table('forecast_accuracy')
    op.drop_table('forecasts')
    op.drop_table('subscriptions')
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_table('customers')
    op.drop_table('harvests')
    op.drop_table('grow_batches')
    op.drop_table('seed_batches')
    op.drop_table('seeds')
