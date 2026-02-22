"""Add missing indexes on foreign key columns for faster joins and lookups.

Covers: order_items, refresh_tokens, order_invoices, order_tracking_updates,
user_budget_overrides, and hibob_purchase_reviews.

Revision ID: 025
Revises: 024
Create Date: 2026-02-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("idx_order_items_order_id", "order_items", ["order_id"], if_not_exists=True)
    op.create_index("idx_order_items_product_id", "order_items", ["product_id"], if_not_exists=True)
    op.create_index("idx_refresh_tokens_user_id", "refresh_tokens", ["user_id"], if_not_exists=True)
    op.create_index("idx_refresh_tokens_token_family", "refresh_tokens", ["token_family"], if_not_exists=True)
    op.create_index("idx_order_invoices_order_id", "order_invoices", ["order_id"], if_not_exists=True)
    op.create_index("idx_order_tracking_order_id", "order_tracking_updates", ["order_id"], if_not_exists=True)
    op.create_index("idx_user_budget_overrides_user_id", "user_budget_overrides", ["user_id"], if_not_exists=True)
    op.create_index("idx_hibob_purchase_review_user_id", "hibob_purchase_reviews", ["user_id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("idx_hibob_purchase_review_user_id", table_name="hibob_purchase_reviews")
    op.drop_index("idx_user_budget_overrides_user_id", table_name="user_budget_overrides")
    op.drop_index("idx_order_tracking_order_id", table_name="order_tracking_updates")
    op.drop_index("idx_order_invoices_order_id", table_name="order_invoices")
    op.drop_index("idx_refresh_tokens_token_family", table_name="refresh_tokens")
    op.drop_index("idx_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_index("idx_order_items_product_id", table_name="order_items")
    op.drop_index("idx_order_items_order_id", table_name="order_items")
