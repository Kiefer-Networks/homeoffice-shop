"""Add missing indexes, CHECK constraints, and partial unique index for cart items.

Revision ID: 017
Revises: 016
Create Date: 2026-02-20
"""
from typing import Sequence, Union

from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Performance indexes ──────────────────────────────────────────────────
    # orders: budget queries filter by (user_id, status) frequently
    op.create_index("idx_orders_user_id_status", "orders", ["user_id", "status"])
    # budget_adjustments: summed per user for budget calculations
    op.create_index("idx_budget_adjustments_user_id", "budget_adjustments", ["user_id"])
    # cart_items: queried per user on every cart load
    op.create_index("idx_cart_items_user_id", "cart_items", ["user_id"])
    # products: filtered by category on shop pages
    op.create_index("idx_products_category_id", "products", ["category_id"])

    # ── Partial unique index for NULL variant_asin ───────────────────────────
    # The existing unique constraint (user_id, product_id, variant_asin) does
    # not prevent duplicates when variant_asin IS NULL because NULL != NULL.
    op.execute(
        "CREATE UNIQUE INDEX uq_cart_user_product_no_variant "
        "ON cart_items (user_id, product_id) WHERE variant_asin IS NULL"
    )

    # ── CHECK constraints ────────────────────────────────────────────────────
    op.create_check_constraint(
        "ck_products_price_non_negative", "products", "price_cents >= 0"
    )
    op.create_check_constraint(
        "ck_products_max_qty_positive", "products", "max_quantity_per_user >= 1"
    )
    op.create_check_constraint(
        "ck_order_items_qty_positive", "order_items", "quantity >= 1"
    )
    op.create_check_constraint(
        "ck_cart_items_qty_positive", "cart_items", "quantity >= 1"
    )


def downgrade() -> None:
    op.drop_constraint("ck_cart_items_qty_positive", "cart_items", type_="check")
    op.drop_constraint("ck_order_items_qty_positive", "order_items", type_="check")
    op.drop_constraint("ck_products_max_qty_positive", "products", type_="check")
    op.drop_constraint("ck_products_price_non_negative", "products", type_="check")

    op.execute("DROP INDEX IF EXISTS uq_cart_user_product_no_variant")

    op.drop_index("idx_products_category_id", table_name="products")
    op.drop_index("idx_cart_items_user_id", table_name="cart_items")
    op.drop_index("idx_budget_adjustments_user_id", table_name="budget_adjustments")
    op.drop_index("idx_orders_user_id_status", table_name="orders")
