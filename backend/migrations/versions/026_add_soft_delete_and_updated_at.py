"""Add deleted_at to categories/brands and updated_at to several tables.

Adds soft-delete support (deleted_at) to categories and brands tables.
Adds updated_at column to categories, brands, budget_adjustments,
budget_rules, and user_budget_overrides tables.

Revision ID: 026
Revises: 025
Create Date: 2026-02-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UPDATED_AT_TABLES = [
    "categories",
    "brands",
    "budget_adjustments",
    "budget_rules",
    "user_budget_overrides",
]


def upgrade() -> None:
    # Add deleted_at (soft-delete) to categories and brands
    op.add_column(
        "categories",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "brands",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add updated_at to tables that lack it
    for table in _UPDATED_AT_TABLES:
        op.add_column(
            table,
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    # Drop updated_at columns
    for table in reversed(_UPDATED_AT_TABLES):
        op.drop_column(table, "updated_at")

    # Drop deleted_at columns
    op.drop_column("brands", "deleted_at")
    op.drop_column("categories", "deleted_at")
