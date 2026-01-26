"""ERP Order & Forecast Enhancements

Revision ID: 003
Revises: 002
Create Date: 2026-01-25

Erweitert das Schema um ERP-Standard Funktionalität:
- Order Header-Line Architecture (Bestellkopf/Positionen)
- OrderAuditLog für Änderungsnachverfolgung
- ForecastManualAdjustment für manuelle Forecast-Anpassungen
- Erweiterte Order-Felder (Bestellnummer, Adressen, Beträge)
- Erweiterte Forecast-Felder (effektive Menge, Datenquellen)
- Erweiterte ProductionSuggestion-Felder
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # ORDER HEADER ENHANCEMENTS
    # ============================================================

    # Neue Spalten für orders (Header)
    op.add_column('orders', sa.Column('order_number', sa.String(20), unique=True, index=True))
    op.add_column('orders', sa.Column('customer_reference', sa.String(100)))
    op.add_column('orders', sa.Column('billing_address', postgresql.JSONB))
    op.add_column('orders', sa.Column('delivery_address', postgresql.JSONB))
    op.add_column('orders', sa.Column('order_date', sa.DateTime, server_default=sa.text('NOW()')))
    op.add_column('orders', sa.Column('requested_delivery_date', sa.Date))
    op.add_column('orders', sa.Column('confirmed_delivery_date', sa.Date))
    op.add_column('orders', sa.Column('total_net', sa.Numeric(12, 2), server_default='0'))
    op.add_column('orders', sa.Column('total_vat', sa.Numeric(12, 2), server_default='0'))
    op.add_column('orders', sa.Column('total_gross', sa.Numeric(12, 2), server_default='0'))
    op.add_column('orders', sa.Column('currency', sa.String(3), server_default=sa.text("'EUR'")))
    op.add_column('orders', sa.Column('created_by', postgresql.UUID(as_uuid=True)))
    op.add_column('orders', sa.Column('updated_by', postgresql.UUID(as_uuid=True)))


    # Rename customer_id -> kunde_id for consistency (alias in model)
    # Note: The model uses both kunde_id (legacy) and customer_id (new)

    # ============================================================
    # ORDER LINES (Bestellpositionen) - Restructure
    # ============================================================

    # Neue Spalten für order_items -> order_lines
    op.add_column('order_items', sa.Column('position', sa.Integer, server_default='1'))
    op.add_column('order_items', sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id', ondelete='SET NULL')))
    op.add_column('order_items', sa.Column('beschreibung', sa.Text))
    op.add_column('order_items', sa.Column('quantity', sa.Numeric(10, 3)))
    op.add_column('order_items', sa.Column('unit', sa.String(20)))
    op.add_column('order_items', sa.Column('unit_price', sa.Numeric(12, 4)))
    op.add_column('order_items', sa.Column('discount_percent', sa.Numeric(5, 2), server_default='0'))
    op.add_column('order_items', sa.Column('line_net', sa.Numeric(12, 2), server_default='0'))
    op.add_column('order_items', sa.Column('tax_rate', sa.String(20), server_default="'REDUZIERT'"))
    op.add_column('order_items', sa.Column('line_vat', sa.Numeric(12, 2), server_default='0'))
    op.add_column('order_items', sa.Column('line_gross', sa.Numeric(12, 2), server_default='0'))
    op.add_column('order_items', sa.Column('requested_delivery_date', sa.Date))

    # ============================================================
    # ORDER AUDIT LOG
    # ============================================================
    op.create_table(
        'order_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True)),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('old_values', postgresql.JSONB),
        sa.Column('new_values', postgresql.JSONB),
        sa.Column('reason', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    op.create_index('ix_order_audit_logs_order_id', 'order_audit_logs', ['order_id'])
    op.create_index('ix_order_audit_logs_created_at', 'order_audit_logs', ['created_at'])

    # ============================================================
    # FORECAST ENHANCEMENTS
    # ============================================================

    # Neue Spalten für forecasts
    op.add_column('forecasts', sa.Column('effektive_menge', sa.Numeric(10, 2)))
    op.add_column('forecasts', sa.Column('hat_manuelle_anpassung', sa.Boolean, server_default='false'))
    op.add_column('forecasts', sa.Column('basiert_auf_historisch', sa.Boolean, server_default='false'))
    op.add_column('forecasts', sa.Column('basiert_auf_abonnements', sa.Boolean, server_default='false'))
    op.add_column('forecasts', sa.Column('basiert_auf_saisonalitaet', sa.Boolean, server_default='false'))

    # ============================================================
    # FORECAST MANUAL ADJUSTMENTS
    # ============================================================
    op.create_table(
        'forecast_manual_adjustments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('forecast_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('forecasts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('adjustment_type', sa.String(30), nullable=False),  # ABSOLUTE, PERCENTAGE_INCREASE, etc.
        sa.Column('adjustment_value', sa.Numeric(10, 2), nullable=False),
        sa.Column('reason', sa.Text, nullable=False),  # Pflichtfeld
        sa.Column('valid_from', sa.Date),
        sa.Column('valid_until', sa.Date),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('reverted_at', sa.DateTime),
        sa.Column('reverted_by', postgresql.UUID(as_uuid=True)),
        sa.Column('revert_reason', sa.Text),
    )

    op.create_index('ix_forecast_manual_adjustments_forecast_id', 'forecast_manual_adjustments', ['forecast_id'])
    op.create_index('ix_forecast_manual_adjustments_active', 'forecast_manual_adjustments', ['is_active'])

    # ============================================================
    # FORECAST ACCURACY ENHANCEMENTS
    # ============================================================

    # Neue Spalten für forecast_accuracy
    op.add_column('forecast_accuracy', sa.Column('automatic_menge', sa.Numeric(10, 2)))
    op.add_column('forecast_accuracy', sa.Column('effektive_menge', sa.Numeric(10, 2)))
    op.add_column('forecast_accuracy', sa.Column('abweichung_von_automatisch', sa.Numeric(10, 2)))
    op.add_column('forecast_accuracy', sa.Column('abweichung_von_effektiv', sa.Numeric(10, 2)))
    op.add_column('forecast_accuracy', sa.Column('hatte_manuelle_anpassung', sa.Boolean, server_default='false'))

    # ============================================================
    # PRODUCTION SUGGESTION ENHANCEMENTS
    # ============================================================

    # Neue Spalten für production_suggestions
    op.add_column('production_suggestions', sa.Column('benoetigte_menge_gramm', sa.Numeric(10, 2)))
    op.add_column('production_suggestions', sa.Column('erwartete_menge_gramm', sa.Numeric(10, 2)))

    op.add_column('production_suggestions', sa.Column('abgelehnt_am', sa.DateTime))
    op.add_column('production_suggestions', sa.Column('abgelehnt_von', postgresql.UUID(as_uuid=True)))
    op.add_column('production_suggestions', sa.Column('ablehnungsgrund', sa.Text))

    # ============================================================
    # DATA MIGRATION: Set effektive_menge = prognostizierte_menge
    # ============================================================
    op.execute("""
        UPDATE forecasts
        SET effektive_menge = prognostizierte_menge
        WHERE effektive_menge IS NULL
    """)

    # ============================================================
    # DATA MIGRATION: Copy legacy order fields to new structure
    # ============================================================
    op.execute("""
        UPDATE order_items
        SET quantity = menge,
            unit = einheit,
            unit_price = preis_pro_einheit
        WHERE quantity IS NULL
    """)

    # Migrate liefer_datum to requested_delivery_date
    op.execute("""
        UPDATE orders
        SET requested_delivery_date = liefer_datum
        WHERE requested_delivery_date IS NULL AND liefer_datum IS NOT NULL
    """)


def downgrade() -> None:
    # Production Suggestions
    op.drop_column('production_suggestions', 'ablehnungsgrund')
    op.drop_column('production_suggestions', 'abgelehnt_von')
    op.drop_column('production_suggestions', 'abgelehnt_am')
    op.drop_column('production_suggestions', 'genehmigt_von')
    op.drop_column('production_suggestions', 'genehmigt_am')
    op.drop_column('production_suggestions', 'erwartete_menge_gramm')
    op.drop_column('production_suggestions', 'benoetigte_menge_gramm')

    # Forecast Accuracy
    op.drop_column('forecast_accuracy', 'hatte_manuelle_anpassung')
    op.drop_column('forecast_accuracy', 'abweichung_von_effektiv')
    op.drop_column('forecast_accuracy', 'abweichung_von_automatisch')
    op.drop_column('forecast_accuracy', 'effektive_menge')
    op.drop_column('forecast_accuracy', 'automatic_menge')

    # Forecast Manual Adjustments
    op.drop_index('ix_forecast_manual_adjustments_active')
    op.drop_index('ix_forecast_manual_adjustments_forecast_id')
    op.drop_table('forecast_manual_adjustments')

    # Forecast Enhancements
    op.drop_column('forecasts', 'basiert_auf_saisonalitaet')
    op.drop_column('forecasts', 'basiert_auf_abonnements')
    op.drop_column('forecasts', 'basiert_auf_historisch')
    op.drop_column('forecasts', 'hat_manuelle_anpassung')
    op.drop_column('forecasts', 'effektive_menge')

    # Order Audit Log
    op.drop_index('ix_order_audit_logs_created_at')
    op.drop_index('ix_order_audit_logs_order_id')
    op.drop_table('order_audit_logs')

    # Order Lines
    op.drop_column('order_items', 'requested_delivery_date')
    op.drop_column('order_items', 'line_gross')
    op.drop_column('order_items', 'line_vat')
    op.drop_column('order_items', 'tax_rate')
    op.drop_column('order_items', 'line_net')
    op.drop_column('order_items', 'discount_percent')
    op.drop_column('order_items', 'unit_price')
    op.drop_column('order_items', 'unit')
    op.drop_column('order_items', 'quantity')
    op.drop_column('order_items', 'beschreibung')
    op.drop_column('order_items', 'product_id')
    op.drop_column('order_items', 'position')

    # Order Header
    op.drop_column('orders', 'updated_at')
    op.drop_column('orders', 'updated_by')
    op.drop_column('orders', 'created_by')
    op.drop_column('orders', 'currency')
    op.drop_column('orders', 'total_gross')
    op.drop_column('orders', 'total_vat')
    op.drop_column('orders', 'total_net')
    op.drop_column('orders', 'confirmed_delivery_date')
    op.drop_column('orders', 'requested_delivery_date')
    op.drop_column('orders', 'order_date')
    op.drop_column('orders', 'delivery_address')
    op.drop_column('orders', 'billing_address')
    op.drop_column('orders', 'customer_reference')
    op.drop_index('ix_orders_order_number', 'orders')
    op.drop_column('orders', 'order_number')
