"""Add expected_delivery and purchase_url to orders, create order_invoices table.

Revision ID: 006
Revises: 005
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Order enhancements
    op.add_column("orders", sa.Column("expected_delivery", sa.VARCHAR(255), nullable=True))
    op.add_column("orders", sa.Column("purchase_url", sa.Text, nullable=True))

    # Order invoices table
    op.create_table(
        "order_invoices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "order_id",
            UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.VARCHAR(255), nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column(
            "uploaded_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_order_invoices_order_id", "order_invoices", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_order_invoices_order_id", table_name="order_invoices")
    op.drop_table("order_invoices")
    op.drop_column("orders", "purchase_url")
    op.drop_column("orders", "expected_delivery")
