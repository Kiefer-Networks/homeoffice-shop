"""Add updated_at auto-update trigger and widen budget columns to BigInteger.

Revision ID: 011
Revises: 010
Create Date: 2026-02-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables that have an updated_at column
_UPDATED_AT_TABLES = [
    "users",
    "products",
    "orders",
    "admin_notification_prefs",
    "app_settings",
]


def upgrade() -> None:
    # 1. Create a reusable trigger function for auto-updating updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    # 2. Attach trigger to all tables with updated_at
    for table in _UPDATED_AT_TABLES:
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION set_updated_at()
        """)

    # 3. Widen budget columns from INTEGER to BIGINT to prevent overflow
    op.alter_column("users", "total_budget_cents", type_=sa.BigInteger())
    op.alter_column("users", "cached_spent_cents", type_=sa.BigInteger())
    op.alter_column("users", "cached_adjustment_cents", type_=sa.BigInteger())
    op.alter_column("budget_adjustments", "amount_cents", type_=sa.BigInteger())
    op.alter_column("budget_rules", "initial_cents", type_=sa.BigInteger())
    op.alter_column("budget_rules", "yearly_increment_cents", type_=sa.BigInteger())
    op.alter_column("user_budget_overrides", "initial_cents", type_=sa.BigInteger())
    op.alter_column("user_budget_overrides", "yearly_increment_cents", type_=sa.BigInteger())


def downgrade() -> None:
    # Revert columns to INTEGER
    op.alter_column("user_budget_overrides", "yearly_increment_cents", type_=sa.Integer())
    op.alter_column("user_budget_overrides", "initial_cents", type_=sa.Integer())
    op.alter_column("budget_rules", "yearly_increment_cents", type_=sa.Integer())
    op.alter_column("budget_rules", "initial_cents", type_=sa.Integer())
    op.alter_column("budget_adjustments", "amount_cents", type_=sa.Integer())
    op.alter_column("users", "cached_adjustment_cents", type_=sa.Integer())
    op.alter_column("users", "cached_spent_cents", type_=sa.Integer())
    op.alter_column("users", "total_budget_cents", type_=sa.Integer())

    for table in reversed(_UPDATED_AT_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")

    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
