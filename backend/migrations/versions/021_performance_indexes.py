"""Add performance indexes for cart lookups and audit filtering.

Revision ID: 021
Revises: 020
Create Date: 2026-02-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_cart_items_user_product_variant",
        "cart_items",
        ["user_id", "product_id", "variant_asin"],
    )
    op.create_index(
        "idx_audit_log_filter",
        "audit_log",
        ["user_id", "action", "resource_type", "created_at"],
    )
    op.create_index(
        "idx_orders_hibob_synced",
        "orders",
        ["hibob_synced_at"],
        postgresql_where="hibob_synced_at IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("idx_orders_hibob_synced", table_name="orders")
    op.drop_index("idx_audit_log_filter", table_name="audit_log")
    op.drop_index("idx_cart_items_user_product_variant", table_name="cart_items")
