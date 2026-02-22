"""Add GIN index on to_tsvector expression for direct full-text search queries.

This supplements the existing idx_products_search GIN index on the stored
search_vector column by adding an expression-based index that covers direct
to_tsvector('english', name || ' ' || coalesce(description, '')) queries,
useful for lightweight autocomplete and ad-hoc full-text searches that don't
rely on the trigger-maintained search_vector column.

Revision ID: 024
Revises: 023
Create Date: 2026-02-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX idx_products_name_desc_fts
        ON products
        USING GIN (to_tsvector('english', name || ' ' || coalesce(description, '')))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_products_name_desc_fts")
