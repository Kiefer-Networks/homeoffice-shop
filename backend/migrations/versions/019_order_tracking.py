"""Add tracking fields to orders and order_tracking_updates table.

Revision ID: 019
Revises: 018
Create Date: 2026-02-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("tracking_number", sa.String(255), nullable=True))
    op.add_column("orders", sa.Column("tracking_url", sa.Text, nullable=True))

    op.create_table(
        "order_tracking_updates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("comment", sa.Text, nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_order_tracking_updates_order_id", "order_tracking_updates", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_order_tracking_updates_order_id", table_name="order_tracking_updates")
    op.drop_table("order_tracking_updates")
    op.drop_column("orders", "tracking_url")
    op.drop_column("orders", "tracking_number")
