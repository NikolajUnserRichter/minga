"""ERP Extension - Units, Products, Invoices, Inventory

Revision ID: 002
Revises: 001
Create Date: 2026-01-24

Erweitert das Schema um vollständige ERP-Funktionalität:
- Units of Measure (Maßeinheiten)
- Products und GrowPlans (getrennt von Seeds)
- Customer Extensions (Payment Terms, Adressen)
- Invoices (Rechnungen mit deutscher MwSt)
- Inventory (Lagerverwaltung mit Rückverfolgbarkeit)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # UNITS OF MEASURE (Maßeinheiten)
    # ============================================================
    op.create_table(
        'units_of_measure',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('code', sa.String(10), nullable=False, unique=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('symbol', sa.String(10)),
        sa.Column('category', sa.String(20), nullable=False),  # WEIGHT, VOLUME, COUNT, CONTAINER
        sa.Column('base_unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('units_of_measure.id', ondelete='SET NULL')),
        sa.Column('conversion_factor', sa.Numeric(15, 6), server_default='1'),
        sa.Column('is_base_unit', sa.Boolean, server_default='false'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )



    # ============================================================
    # PRODUCTS & GROW PLANS
    # ============================================================
    op.create_table(
        'product_groups',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('code', sa.String(20), nullable=False, unique=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('product_groups.id', ondelete='SET NULL')),
        sa.Column('description', sa.Text),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    op.create_table(
        'grow_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('code', sa.String(20), nullable=False, unique=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text),
        # Phasen
        sa.Column('soak_hours', sa.Integer, server_default='0'),
        sa.Column('blackout_days', sa.Integer, server_default='0'),
        sa.Column('germination_days', sa.Integer, nullable=False),
        sa.Column('growth_days', sa.Integer, nullable=False),
        # Erntefenster
        sa.Column('harvest_window_start_days', sa.Integer, nullable=False),
        sa.Column('harvest_window_optimal_days', sa.Integer, nullable=False),
        sa.Column('harvest_window_end_days', sa.Integer, nullable=False),
        # Ertrag
        sa.Column('expected_yield_grams_per_tray', sa.Numeric(10, 2), nullable=False),
        sa.Column('expected_loss_percent', sa.Numeric(5, 2), server_default='5'),
        # Bedingungen
        sa.Column('optimal_temp_celsius', sa.Numeric(4, 1)),
        sa.Column('optimal_humidity_percent', sa.Integer),
        sa.Column('light_hours_per_day', sa.Integer),
        sa.Column('seed_density_grams_per_tray', sa.Numeric(10, 2)),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    op.create_table(
        'price_lists',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('code', sa.String(20), nullable=False, unique=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('currency', sa.String(3), server_default="'EUR'"),
        sa.Column('valid_from', sa.Date),
        sa.Column('valid_until', sa.Date),
        sa.Column('is_default', sa.Boolean, server_default='false'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    op.create_table(
        'products',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('sku', sa.String(50), nullable=False, unique=True),
        sa.Column('name', sa.String(200), nullable=False, index=True),
        sa.Column('description', sa.Text),
        sa.Column('category', sa.String(20), nullable=False),  # MICROGREEN, SEED, PACKAGING, BUNDLE
        sa.Column('product_group_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('product_groups.id', ondelete='SET NULL')),
        # Einheit und Preis
        sa.Column('base_unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('units_of_measure.id')),
        sa.Column('base_price', sa.Numeric(10, 2)),
        sa.Column('tax_rate', sa.String(20), server_default="'REDUZIERT'"),  # STANDARD, REDUZIERT, STEUERFREI
        # Microgreen-spezifisch
        sa.Column('seed_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('seeds.id', ondelete='SET NULL')),
        sa.Column('grow_plan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('grow_plans.id', ondelete='SET NULL')),
        sa.Column('seed_variety', sa.String(100)),
        # Lager
        sa.Column('shelf_life_days', sa.Integer),
        sa.Column('storage_temp_min', sa.Numeric(4, 1)),
        sa.Column('storage_temp_max', sa.Numeric(4, 1)),
        sa.Column('min_stock_quantity', sa.Numeric(10, 2)),
        # Bundle
        sa.Column('is_bundle', sa.Boolean, server_default='false'),
        sa.Column('bundle_components', postgresql.JSONB),
        # Status
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('is_sellable', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    op.create_table(
        'unit_conversions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id', ondelete='CASCADE')),
        sa.Column('from_unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('units_of_measure.id'), nullable=False),
        sa.Column('to_unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('units_of_measure.id'), nullable=False),
        sa.Column('factor', sa.Numeric(15, 6), nullable=False),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.UniqueConstraint('product_id', 'from_unit_id', 'to_unit_id', name='uq_unit_conversion'),
    )

    op.create_table(
        'price_list_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('price_list_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('price_lists.id', ondelete='CASCADE'), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('units_of_measure.id')),
        sa.Column('price', sa.Numeric(10, 4), nullable=False),
        sa.Column('min_quantity', sa.Numeric(10, 2), server_default='1'),
        sa.Column('valid_from', sa.Date),
        sa.Column('valid_until', sa.Date),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.UniqueConstraint('price_list_id', 'product_id', 'unit_id', 'min_quantity', name='uq_price_list_item'),
    )

    # ============================================================
    # CUSTOMER EXTENSIONS
    # ============================================================
    # Neue Spalten für customers
    op.add_column('customers', sa.Column('customer_number', sa.String(20), unique=True))
    op.add_column('customers', sa.Column('ansprechpartner_name', sa.String(200)))
    op.add_column('customers', sa.Column('ansprechpartner_email', sa.String(200)))
    op.add_column('customers', sa.Column('ansprechpartner_telefon', sa.String(50)))
    op.add_column('customers', sa.Column('ust_id', sa.String(20)))
    op.add_column('customers', sa.Column('steuernummer', sa.String(20)))
    op.add_column('customers', sa.Column('payment_terms', sa.String(20), server_default="'NET_14'"))
    op.add_column('customers', sa.Column('credit_limit', sa.Numeric(10, 2)))
    op.add_column('customers', sa.Column('price_list_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('price_lists.id', ondelete='SET NULL')))
    op.add_column('customers', sa.Column('discount_percent', sa.Numeric(5, 2), server_default='0'))
    op.add_column('customers', sa.Column('datev_account', sa.String(10)))
    op.add_column('customers', sa.Column('notizen', sa.Text))

    op.create_index('ix_customers_customer_number', 'customers', ['customer_number'])

    # Customer Addresses
    op.create_table(
        'customer_addresses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('address_type', sa.String(20), nullable=False),  # BILLING, SHIPPING, BOTH
        sa.Column('is_default', sa.Boolean, server_default='false'),
        sa.Column('name', sa.String(200)),
        sa.Column('strasse', sa.String(200), nullable=False),
        sa.Column('hausnummer', sa.String(20)),
        sa.Column('adresszusatz', sa.String(200)),
        sa.Column('plz', sa.String(10), nullable=False),
        sa.Column('ort', sa.String(100), nullable=False),
        sa.Column('land', sa.String(2), server_default="'DE'"),
        sa.Column('lieferhinweise', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # ============================================================
    # INVOICES (Rechnungen)
    # ============================================================
    op.create_table(
        'invoices',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('invoice_number', sa.String(20), nullable=False, unique=True),
        sa.Column('invoice_type', sa.String(20), server_default="'RECHNUNG'"),
        sa.Column('original_invoice_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('invoices.id', ondelete='SET NULL')),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customers.id'), nullable=False),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('orders.id', ondelete='SET NULL')),
        # Datum
        sa.Column('invoice_date', sa.Date, nullable=False),
        sa.Column('delivery_date', sa.Date),
        sa.Column('due_date', sa.Date, nullable=False),
        # Status
        sa.Column('status', sa.String(20), server_default="'ENTWURF'"),
        # Adressen (Snapshot)
        sa.Column('billing_address', postgresql.JSONB),
        sa.Column('shipping_address', postgresql.JSONB),
        # Beträge
        sa.Column('subtotal', sa.Numeric(12, 2), server_default='0'),
        sa.Column('tax_amount', sa.Numeric(12, 2), server_default='0'),
        sa.Column('total', sa.Numeric(12, 2), server_default='0'),
        sa.Column('discount_percent', sa.Numeric(5, 2), server_default='0'),
        sa.Column('discount_amount', sa.Numeric(12, 2), server_default='0'),
        sa.Column('paid_amount', sa.Numeric(12, 2), server_default='0'),
        sa.Column('currency', sa.String(3), server_default="'EUR'"),
        # DATEV
        sa.Column('datev_exported', sa.Boolean, server_default='false'),
        sa.Column('datev_export_date', sa.DateTime),
        sa.Column('buchungskonto', sa.String(10)),
        # Texte
        sa.Column('header_text', sa.Text),
        sa.Column('footer_text', sa.Text),
        sa.Column('internal_notes', sa.Text),
        # Timestamps
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('sent_at', sa.DateTime),
    )

    op.create_index('ix_invoices_invoice_number', 'invoices', ['invoice_number'])
    op.create_index('ix_invoices_customer_id', 'invoices', ['customer_id'])
    op.create_index('ix_invoices_invoice_date', 'invoices', ['invoice_date'])

    op.create_table(
        'invoice_lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False),
        sa.Column('position', sa.Integer, nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id', ondelete='SET NULL')),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('sku', sa.String(50)),
        sa.Column('quantity', sa.Numeric(10, 3), nullable=False),
        sa.Column('unit', sa.String(20), nullable=False),
        sa.Column('unit_price', sa.Numeric(10, 4), nullable=False),
        sa.Column('discount_percent', sa.Numeric(5, 2), server_default='0'),
        sa.Column('tax_rate', sa.String(20), server_default="'REDUZIERT'"),
        sa.Column('line_total', sa.Numeric(12, 2), server_default='0'),
        sa.Column('order_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('order_items.id', ondelete='SET NULL')),
        sa.Column('harvest_batch_ids', postgresql.JSONB),
        sa.Column('buchungskonto', sa.String(10)),
    )

    op.create_table(
        'payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False),
        sa.Column('payment_date', sa.Date, nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('payment_method', sa.String(20), server_default="'UEBERWEISUNG'"),
        sa.Column('reference', sa.String(100)),
        sa.Column('bank_reference', sa.String(100)),
        sa.Column('notes', sa.Text),
        sa.Column('datev_exported', sa.Boolean, server_default='false'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # ============================================================
    # INVENTORY (Lagerverwaltung)
    # ============================================================
    op.create_table(
        'inventory_locations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('code', sa.String(20), nullable=False, unique=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('location_type', sa.String(20), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory_locations.id', ondelete='SET NULL')),
        sa.Column('capacity_trays', sa.Integer),
        sa.Column('capacity_kg', sa.Numeric(10, 2)),
        sa.Column('temperature_min', sa.Numeric(4, 1)),
        sa.Column('temperature_max', sa.Numeric(4, 1)),
        sa.Column('humidity_min', sa.Integer),
        sa.Column('humidity_max', sa.Integer),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    op.create_table(
        'seed_inventory',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('seed_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('seeds.id'), nullable=False),
        sa.Column('batch_number', sa.String(50), nullable=False, index=True),
        sa.Column('supplier_batch', sa.String(50)),
        sa.Column('initial_quantity_kg', sa.Numeric(10, 3), nullable=False),
        sa.Column('current_quantity_kg', sa.Numeric(10, 3), nullable=False),
        sa.Column('germination_rate', sa.Numeric(5, 2)),
        sa.Column('quality_grade', sa.String(10)),
        sa.Column('received_date', sa.Date, nullable=False),
        sa.Column('best_before_date', sa.Date),
        sa.Column('production_date', sa.Date),
        sa.Column('supplier_name', sa.String(200)),
        sa.Column('purchase_price_per_kg', sa.Numeric(10, 2)),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory_locations.id', ondelete='SET NULL')),
        sa.Column('is_organic', sa.Boolean, server_default='false'),
        sa.Column('organic_certificate', sa.String(100)),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('is_blocked', sa.Boolean, server_default='false'),
        sa.Column('block_reason', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    op.create_table(
        'finished_goods_inventory',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id'), nullable=False),
        sa.Column('batch_number', sa.String(50), nullable=False, index=True),
        sa.Column('harvest_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('harvests.id', ondelete='SET NULL')),
        sa.Column('grow_batch_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('grow_batches.id', ondelete='SET NULL')),
        sa.Column('seed_inventory_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('seed_inventory.id', ondelete='SET NULL')),
        sa.Column('initial_quantity_g', sa.Numeric(10, 2), nullable=False),
        sa.Column('current_quantity_g', sa.Numeric(10, 2), nullable=False),
        sa.Column('initial_units', sa.Integer),
        sa.Column('current_units', sa.Integer),
        sa.Column('unit_size_g', sa.Numeric(10, 2)),
        sa.Column('quality_grade', sa.Integer),
        sa.Column('quality_notes', sa.Text),
        sa.Column('harvest_date', sa.Date, nullable=False),
        sa.Column('best_before_date', sa.Date, nullable=False),
        sa.Column('packed_date', sa.Date),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory_locations.id', ondelete='SET NULL')),
        sa.Column('storage_temp_celsius', sa.Numeric(4, 1)),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('is_reserved', sa.Boolean, server_default='false'),
        sa.Column('reserved_order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('orders.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    op.create_table(
        'packaging_inventory',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('sku', sa.String(50), nullable=False, unique=True),
        sa.Column('description', sa.Text),
        sa.Column('current_quantity', sa.Integer, nullable=False, server_default='0'),
        sa.Column('min_quantity', sa.Integer, server_default='0'),
        sa.Column('reorder_quantity', sa.Integer),
        sa.Column('unit', sa.String(20), server_default="'Stück'"),
        sa.Column('supplier_name', sa.String(200)),
        sa.Column('supplier_sku', sa.String(50)),
        sa.Column('purchase_price', sa.Numeric(10, 2)),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory_locations.id', ondelete='SET NULL')),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    op.create_table(
        'inventory_movements',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('movement_type', sa.String(20), nullable=False),
        sa.Column('item_type', sa.String(20), nullable=False),
        sa.Column('seed_inventory_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('seed_inventory.id', ondelete='SET NULL')),
        sa.Column('finished_goods_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('finished_goods_inventory.id', ondelete='SET NULL')),
        sa.Column('packaging_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('packaging_inventory.id', ondelete='SET NULL')),
        sa.Column('quantity', sa.Numeric(12, 3), nullable=False),
        sa.Column('unit', sa.String(20), nullable=False),
        sa.Column('quantity_before', sa.Numeric(12, 3), nullable=False),
        sa.Column('quantity_after', sa.Numeric(12, 3), nullable=False),
        sa.Column('from_location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory_locations.id', ondelete='SET NULL')),
        sa.Column('to_location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory_locations.id', ondelete='SET NULL')),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('orders.id', ondelete='SET NULL')),
        sa.Column('order_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('order_items.id', ondelete='SET NULL')),
        sa.Column('grow_batch_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('grow_batches.id', ondelete='SET NULL')),
        sa.Column('harvest_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('harvests.id', ondelete='SET NULL')),
        sa.Column('created_by', sa.String(100)),
        sa.Column('reason', sa.Text),
        sa.Column('reference_number', sa.String(50)),
        sa.Column('movement_date', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    op.create_index('ix_inventory_movements_date', 'inventory_movements', ['movement_date'])

    op.create_table(
        'inventory_counts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('count_date', sa.Date, nullable=False),
        sa.Column('count_number', sa.String(20), nullable=False, unique=True),
        sa.Column('status', sa.String(20), server_default="'OFFEN'"),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory_locations.id', ondelete='SET NULL')),
        sa.Column('notes', sa.Text),
        sa.Column('counted_by', sa.String(100)),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('completed_at', sa.DateTime),
    )

    op.create_table(
        'inventory_count_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('count_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory_counts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('item_type', sa.String(20), nullable=False),
        sa.Column('seed_inventory_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('seed_inventory.id', ondelete='SET NULL')),
        sa.Column('finished_goods_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('finished_goods_inventory.id', ondelete='SET NULL')),
        sa.Column('packaging_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('packaging_inventory.id', ondelete='SET NULL')),
        sa.Column('system_quantity', sa.Numeric(12, 3), nullable=False),
        sa.Column('counted_quantity', sa.Numeric(12, 3)),
        sa.Column('unit', sa.String(20), nullable=False),
        sa.Column('difference', sa.Numeric(12, 3)),
        sa.Column('notes', sa.Text),
    )


def downgrade() -> None:
    # Inventory
    op.drop_table('inventory_count_items')
    op.drop_table('inventory_counts')
    op.drop_index('ix_inventory_movements_date')
    op.drop_table('inventory_movements')
    op.drop_table('packaging_inventory')
    op.drop_table('finished_goods_inventory')
    op.drop_table('seed_inventory')
    op.drop_table('inventory_locations')

    # Invoices
    op.drop_table('payments')
    op.drop_table('invoice_lines')
    op.drop_index('ix_invoices_invoice_date')
    op.drop_index('ix_invoices_customer_id')
    op.drop_index('ix_invoices_invoice_number')
    op.drop_table('invoices')

    # Customer Extensions
    op.drop_table('customer_addresses')
    op.drop_index('ix_customers_customer_number')
    op.drop_column('customers', 'notizen')
    op.drop_column('customers', 'datev_account')
    op.drop_column('customers', 'discount_percent')
    op.drop_column('customers', 'price_list_id')
    op.drop_column('customers', 'credit_limit')
    op.drop_column('customers', 'payment_terms')
    op.drop_column('customers', 'steuernummer')
    op.drop_column('customers', 'ust_id')
    op.drop_column('customers', 'ansprechpartner_telefon')
    op.drop_column('customers', 'ansprechpartner_email')
    op.drop_column('customers', 'ansprechpartner_name')
    op.drop_column('customers', 'customer_number')

    # Products & GrowPlans
    op.drop_table('price_list_items')
    op.drop_table('products')
    op.drop_table('price_lists')
    op.drop_table('grow_plans')
    op.drop_table('product_groups')

    # Units
    op.drop_table('unit_conversions')
    op.drop_table('units_of_measure')
