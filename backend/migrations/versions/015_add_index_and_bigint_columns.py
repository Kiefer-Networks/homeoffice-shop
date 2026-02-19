"""Add index on order_items.product_id and widen remaining cents columns to BigInteger.

Revision ID: 015
Revises: 014
Create Date: 2026-02-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add index on product_id for product deletion/archival checks
    op.create_index("idx_order_items_product_id", "order_items", ["product_id"])

    # Widen remaining cents columns to BIGINT for consistency with migration 011
    op.alter_column(
        "budget_adjustments",
        "amount_cents",
        type_=sa.BigInteger(),
        existing_type=sa.Integer(),
    )
    op.alter_column(
        "orders",
        "total_cents",
        type_=sa.BigInteger(),
        existing_type=sa.Integer(),
    )


def downgrade() -> None:
    op.alter_column(
        "orders",
        "total_cents",
        type_=sa.Integer(),
        existing_type=sa.BigInteger(),
    )
    op.alter_column(
        "budget_adjustments",
        "amount_cents",
        type_=sa.Integer(),
        existing_type=sa.BigInteger(),
    )

    op.drop_index("idx_order_items_product_id", table_name="order_items")
