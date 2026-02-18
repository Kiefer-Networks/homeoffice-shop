"""Add product variants JSONB, variant fields on cart_items and order_items.

Revision ID: 005
Revises: 004
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Product variants JSONB column
    op.add_column("products", sa.Column("variants", JSONB, nullable=True))

    # CartItem variant fields
    op.add_column("cart_items", sa.Column("variant_asin", sa.VARCHAR(20), nullable=True))
    op.add_column("cart_items", sa.Column("variant_value", sa.VARCHAR(100), nullable=True))

    # Replace unique constraint: (user_id, product_id) -> (user_id, product_id, variant_asin)
    op.drop_constraint("uq_cart_user_product", "cart_items", type_="unique")
    op.create_unique_constraint(
        "uq_cart_user_product_variant",
        "cart_items",
        ["user_id", "product_id", "variant_asin"],
    )

    # OrderItem variant fields
    op.add_column("order_items", sa.Column("variant_asin", sa.VARCHAR(20), nullable=True))
    op.add_column("order_items", sa.Column("variant_value", sa.VARCHAR(100), nullable=True))


def downgrade() -> None:
    op.drop_column("order_items", "variant_value")
    op.drop_column("order_items", "variant_asin")

    op.drop_constraint("uq_cart_user_product_variant", "cart_items", type_="unique")
    op.create_unique_constraint(
        "uq_cart_user_product", "cart_items", ["user_id", "product_id"]
    )

    op.drop_column("cart_items", "variant_value")
    op.drop_column("cart_items", "variant_asin")

    op.drop_column("products", "variants")
