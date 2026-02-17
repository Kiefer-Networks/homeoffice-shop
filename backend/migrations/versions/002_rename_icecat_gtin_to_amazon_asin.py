"""Rename icecat_gtin to amazon_asin.

Revision ID: 002
Revises: 001
Create Date: 2026-02-17
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("products", "icecat_gtin", new_column_name="amazon_asin")
    op.alter_column("products", "amazon_asin", type_=sa.String(20), existing_type=sa.String(14))


def downgrade() -> None:
    op.alter_column("products", "amazon_asin", type_=sa.String(14), existing_type=sa.String(20))
    op.alter_column("products", "amazon_asin", new_column_name="icecat_gtin")
