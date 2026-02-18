"""Add budget_rules and user_budget_overrides tables.

Revision ID: 007
Revises: 006
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "budget_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("effective_from", sa.Date, nullable=False, unique=True),
        sa.Column("initial_cents", sa.Integer, nullable=False),
        sa.Column("yearly_increment_cents", sa.Integer, nullable=False),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "user_budget_overrides",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_until", sa.Date, nullable=True),
        sa.Column("initial_cents", sa.Integer, nullable=False),
        sa.Column("yearly_increment_cents", sa.Integer, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_user_budget_overrides_user_id",
        "user_budget_overrides",
        ["user_id"],
    )

    # Seed initial budget rule from current defaults
    op.execute(
        """
        INSERT INTO budget_rules (id, effective_from, initial_cents, yearly_increment_cents, created_by, created_at)
        SELECT gen_random_uuid(), '2020-01-01', 75000, 25000, u.id, now()
        FROM users u WHERE u.role = 'admin' LIMIT 1
        """
    )


def downgrade() -> None:
    op.drop_index("ix_user_budget_overrides_user_id", table_name="user_budget_overrides")
    op.drop_table("user_budget_overrides")
    op.drop_table("budget_rules")
