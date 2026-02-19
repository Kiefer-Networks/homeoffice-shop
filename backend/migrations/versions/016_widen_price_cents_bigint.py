"""Widen order_items.price_cents and cart_items.price_at_add_cents to BigInteger.

Revision ID: 016
Revises: 015
Create Date: 2026-02-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "order_items",
        "price_cents",
        type_=sa.BigInteger(),
        existing_type=sa.Integer(),
    )
    op.alter_column(
        "cart_items",
        "price_at_add_cents",
        type_=sa.BigInteger(),
        existing_type=sa.Integer(),
    )


def downgrade() -> None:
    op.alter_column(
        "cart_items",
        "price_at_add_cents",
        type_=sa.Integer(),
        existing_type=sa.BigInteger(),
    )
    op.alter_column(
        "order_items",
        "price_cents",
        type_=sa.Integer(),
        existing_type=sa.BigInteger(),
    )
