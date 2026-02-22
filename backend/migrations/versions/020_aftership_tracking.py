"""Add AfterShip tracking columns to orders.

Revision ID: 020
Revises: 019
Create Date: 2026-02-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("aftership_tracking_id", sa.String(64), nullable=True))
    op.add_column("orders", sa.Column("aftership_slug", sa.String(100), nullable=True))
    op.create_index(
        "ix_orders_aftership_tracking_id", "orders", ["aftership_tracking_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_orders_aftership_tracking_id", table_name="orders")
    op.drop_column("orders", "aftership_slug")
    op.drop_column("orders", "aftership_tracking_id")
