"""Add product information fields.

Revision ID: 003
Revises: 002
Create Date: 2026-02-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("color", sa.VARCHAR(100), nullable=True))
    op.add_column("products", sa.Column("material", sa.VARCHAR(255), nullable=True))
    op.add_column("products", sa.Column("product_dimensions", sa.VARCHAR(255), nullable=True))
    op.add_column("products", sa.Column("item_weight", sa.VARCHAR(100), nullable=True))
    op.add_column("products", sa.Column("item_model_number", sa.VARCHAR(100), nullable=True))
    op.add_column("products", sa.Column("product_information", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("products", "product_information")
    op.drop_column("products", "item_model_number")
    op.drop_column("products", "item_weight")
    op.drop_column("products", "product_dimensions")
    op.drop_column("products", "material")
    op.drop_column("products", "color")
