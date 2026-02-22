"""Add idempotency_key column to orders table.

Supports idempotent order creation via X-Idempotency-Key header.

Revision ID: 027
Revises: 026
Create Date: 2026-02-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("idempotency_key", sa.String(255), nullable=True))
    op.create_unique_constraint(
        "uq_orders_user_idempotency", "orders", ["user_id", "idempotency_key"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_orders_user_idempotency", "orders", type_="unique")
    op.drop_column("orders", "idempotency_key")
