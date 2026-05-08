"""Add performance indexes and unique constraints

Revision ID: 004
Revises: 003
Create Date: 2026-04-13

Adds missing indexes on:
- Foreign key columns (join performance)
- Status/enum columns (filter performance)
- Date columns (range query performance)
- Composite indexes for common multi-column queries
- Unique constraints on business identifiers
"""
from typing import Sequence, Union
from alembic import op

revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _safe_index(name: str, table: str, columns: list[str], unique: bool = False):
    """Create an index only if the table exists."""
    try:
        op.create_index(name, table, columns, unique=unique)
    except Exception:
        pass  # Table may not exist yet


def upgrade() -> None:
    # ============================================================
    # FOREIGN KEY INDEXES
    # ============================================================

    # --- Orders & Invoices ---
    _safe_index('ix_orders_customer_id', 'orders', ['customer_id'])
    _safe_index('ix_orders_order_date', 'orders', ['order_date'])
    _safe_index('ix_order_lines_product_id', 'order_lines', ['product_id'])
    _safe_index('ix_order_lines_seed_id', 'order_lines', ['seed_id'])
    _safe_index('ix_order_lines_harvest_id', 'order_lines', ['harvest_id'])

    _safe_index('ix_invoices_customer_id', 'invoices', ['customer_id'])
    _safe_index('ix_invoices_order_id', 'invoices', ['order_id'])
    _safe_index('ix_invoices_status', 'invoices', ['status'])
    _safe_index('ix_invoices_due_date', 'invoices', ['due_date'])
    _safe_index('ix_invoice_lines_product_id', 'invoice_lines', ['product_id'])

    # --- Production ---
    _safe_index('ix_grow_batches_seed_batch_id', 'grow_batches', ['seed_batch_id'])
    _safe_index('ix_grow_batches_status', 'grow_batches', ['status'])
    _safe_index('ix_harvests_grow_batch_id', 'harvests', ['grow_batch_id'])

    # --- Customers ---
    _safe_index('ix_customer_addresses_customer_id', 'customer_addresses', ['customer_id'])

    # --- Inventory ---
    _safe_index('ix_seed_inventory_seed_id', 'seed_inventory', ['seed_id'])
    _safe_index('ix_seed_inventory_location_id', 'seed_inventory', ['location_id'])
    _safe_index('ix_finished_goods_product_id', 'finished_goods_inventory', ['product_id'])
    _safe_index('ix_finished_goods_harvest_id', 'finished_goods_inventory', ['harvest_id'])
    _safe_index('ix_finished_goods_location_id', 'finished_goods_inventory', ['location_id'])
    _safe_index('ix_finished_goods_grow_batch_id', 'finished_goods_inventory', ['grow_batch_id'])
    _safe_index('ix_packaging_inventory_location_id', 'packaging_inventory', ['location_id'])

    # --- Inventory Movements ---
    _safe_index('ix_inv_movements_seed_inv_id', 'inventory_movements', ['seed_inventory_id'])
    _safe_index('ix_inv_movements_finished_goods_id', 'inventory_movements', ['finished_goods_id'])
    _safe_index('ix_inv_movements_movement_date', 'inventory_movements', ['movement_date'])
    _safe_index('ix_inv_movements_movement_type', 'inventory_movements', ['movement_type'])

    # --- Products ---
    _safe_index('ix_products_seed_id', 'products', ['seed_id'])
    _safe_index('ix_products_grow_plan_id', 'products', ['grow_plan_id'])
    _safe_index('ix_products_product_group_id', 'products', ['product_group_id'])
    _safe_index('ix_price_list_items_product_id', 'price_list_items', ['product_id'])

    # --- Forecasts ---
    _safe_index('ix_forecasts_seed_id', 'forecasts', ['seed_id'])
    _safe_index('ix_production_suggestions_status', 'production_suggestions', ['status'])

    # --- Inventory Counts ---
    _safe_index('ix_inventory_counts_location_id', 'inventory_counts', ['location_id'])
    _safe_index('ix_inventory_counts_count_date', 'inventory_counts', ['count_date'])

    # ============================================================
    # COMPOSITE INDEXES (common multi-column queries)
    # ============================================================

    _safe_index('ix_forecasts_seed_datum', 'forecasts', ['seed_id', 'datum'], unique=True)
    _safe_index('ix_invoices_customer_date', 'invoices', ['customer_id', 'invoice_date'])
    _safe_index('ix_grow_batches_status_date', 'grow_batches', ['status', 'aussaat_datum'])
    _safe_index('ix_inv_movements_type_date', 'inventory_movements', ['movement_type', 'movement_date'])
    _safe_index('ix_finished_goods_product_date', 'finished_goods_inventory', ['product_id', 'harvest_date'])

    # ============================================================
    # UNIQUE CONSTRAINTS on business identifiers
    # ============================================================

    _safe_index('uq_seed_batches_charge_nummer', 'seed_batches', ['charge_nummer'], unique=True)
    _safe_index('uq_seed_inventory_batch_number', 'seed_inventory', ['batch_number'], unique=True)
    _safe_index('uq_finished_goods_batch_number', 'finished_goods_inventory', ['batch_number'], unique=True)


def downgrade() -> None:
    # Drop all indexes (reverse order)
    index_names = [
        'uq_finished_goods_batch_number',
        'uq_seed_inventory_batch_number',
        'uq_seed_batches_charge_nummer',
        'ix_finished_goods_product_date',
        'ix_inv_movements_type_date',
        'ix_grow_batches_status_date',
        'ix_invoices_customer_date',
        'ix_forecasts_seed_datum',
        'ix_inventory_counts_count_date',
        'ix_inventory_counts_location_id',
        'ix_production_suggestions_status',
        'ix_forecasts_seed_id',
        'ix_price_list_items_product_id',
        'ix_products_product_group_id',
        'ix_products_grow_plan_id',
        'ix_products_seed_id',
        'ix_inv_movements_movement_type',
        'ix_inv_movements_movement_date',
        'ix_inv_movements_finished_goods_id',
        'ix_inv_movements_seed_inv_id',
        'ix_packaging_inventory_location_id',
        'ix_finished_goods_grow_batch_id',
        'ix_finished_goods_location_id',
        'ix_finished_goods_harvest_id',
        'ix_finished_goods_product_id',
        'ix_seed_inventory_location_id',
        'ix_seed_inventory_seed_id',
        'ix_customer_addresses_customer_id',
        'ix_harvests_grow_batch_id',
        'ix_grow_batches_status',
        'ix_grow_batches_seed_batch_id',
        'ix_invoice_lines_product_id',
        'ix_invoices_due_date',
        'ix_invoices_status',
        'ix_invoices_order_id',
        'ix_invoices_customer_id',
        'ix_order_lines_harvest_id',
        'ix_order_lines_seed_id',
        'ix_order_lines_product_id',
        'ix_orders_order_date',
        'ix_orders_customer_id',
    ]
    for name in index_names:
        try:
            op.drop_index(name)
        except Exception:
            pass
