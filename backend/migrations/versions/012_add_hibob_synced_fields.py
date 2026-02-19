"""Add HiBob sync tracking to orders and order_items.

Revision ID: 012
Revises: 011
Create Date: 2026-02-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("hibob_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column(
            "hibob_synced_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "order_items",
        sa.Column("hibob_synced", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("order_items", "hibob_synced")
    op.drop_column("orders", "hibob_synced_by")
    op.drop_column("orders", "hibob_synced_at")
