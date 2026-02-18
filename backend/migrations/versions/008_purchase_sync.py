"""Add purchase sync tables and extend budget_adjustments.

Revision ID: 008
Revises: 007
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1a. Extend budget_adjustments
    op.add_column(
        "budget_adjustments",
        sa.Column("source", sa.String(50), nullable=False, server_default="manual"),
    )
    op.add_column(
        "budget_adjustments",
        sa.Column("hibob_entry_id", sa.String(255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_budget_adjustments_hibob_entry_id",
        "budget_adjustments",
        ["hibob_entry_id"],
    )

    # 1b. Create hibob_purchase_sync_log
    op.create_table(
        "hibob_purchase_sync_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("entries_found", sa.Integer, nullable=False, server_default="0"),
        sa.Column("matched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("auto_adjusted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("pending_review", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "triggered_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 1c. Create hibob_purchase_reviews
    op.create_table(
        "hibob_purchase_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("hibob_employee_id", sa.String(255), nullable=False),
        sa.Column("hibob_entry_id", sa.String(255), nullable=False, unique=True),
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="EUR"),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column(
            "matched_order_id",
            UUID(as_uuid=True),
            sa.ForeignKey("orders.id"),
            nullable=True,
        ),
        sa.Column(
            "adjustment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("budget_adjustments.id"),
            nullable=True,
        ),
        sa.Column(
            "resolved_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "sync_log_id",
            UUID(as_uuid=True),
            sa.ForeignKey("hibob_purchase_sync_log.id"),
            nullable=True,
        ),
        sa.Column("raw_data", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_hibob_purchase_reviews_user_status",
        "hibob_purchase_reviews",
        ["user_id", "status"],
    )

    # 1d. Seed default settings
    op.execute(
        """
        INSERT INTO app_settings (key, value) VALUES
            ('hibob_purchase_table_id', ''),
            ('hibob_purchase_col_date', 'Effective date'),
            ('hibob_purchase_col_description', 'Description'),
            ('hibob_purchase_col_amount', 'Amount'),
            ('hibob_purchase_col_currency', 'Currency')
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_hibob_purchase_reviews_user_status", table_name="hibob_purchase_reviews")
    op.drop_table("hibob_purchase_reviews")
    op.drop_table("hibob_purchase_sync_log")
    op.drop_constraint("uq_budget_adjustments_hibob_entry_id", "budget_adjustments", type_="unique")
    op.drop_column("budget_adjustments", "hibob_entry_id")
    op.drop_column("budget_adjustments", "source")
