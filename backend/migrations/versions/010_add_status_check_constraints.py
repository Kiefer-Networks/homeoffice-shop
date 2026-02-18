"""Add CHECK constraints for order status and user role columns.

Revision ID: 010
Revises: 009
Create Date: 2026-02-18
"""
from typing import Sequence, Union

from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_orders_status",
        "orders",
        "status IN ('pending', 'ordered', 'delivered', 'rejected', 'cancelled')",
    )
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('employee', 'admin', 'manager')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_constraint("ck_orders_status", "orders", type_="check")
