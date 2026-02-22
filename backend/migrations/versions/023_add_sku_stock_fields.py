"""Add SKU and stock tracking fields to products, add return statuses to orders.

Revision ID: 023
Revises: 022
Create Date: 2026-02-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Product stock/SKU fields
    op.add_column("products", sa.Column("sku", sa.String(50), nullable=True))
    op.add_column("products", sa.Column("stock_quantity", sa.Integer(), nullable=True))
    op.add_column(
        "products",
        sa.Column("stock_warning_level", sa.Integer(), nullable=False, server_default="5"),
    )

    # Update order status check constraint to include return_requested and returned
    op.drop_constraint("ck_orders_status", "orders", type_="check")
    op.create_check_constraint(
        "ck_orders_status",
        "orders",
        "status IN ('pending', 'ordered', 'delivered', 'rejected', 'cancelled', 'return_requested', 'returned')",
    )


def downgrade() -> None:
    # Restore original order status constraint
    op.drop_constraint("ck_orders_status", "orders", type_="check")
    op.create_check_constraint(
        "ck_orders_status",
        "orders",
        "status IN ('pending', 'ordered', 'delivered', 'rejected', 'cancelled')",
    )

    # Remove product stock/SKU fields
    op.drop_column("products", "stock_warning_level")
    op.drop_column("products", "stock_quantity")
    op.drop_column("products", "sku")
