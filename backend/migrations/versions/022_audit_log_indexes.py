"""Add individual indexes on audit_log for common query patterns.

Revision ID: 022
Revises: 021
Create Date: 2026-02-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_audit_log_user_id",
        "audit_log",
        ["user_id"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_audit_log_action",
        "audit_log",
        ["action"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_audit_log_created_at",
        "audit_log",
        [sa.text("created_at DESC")],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("idx_audit_log_created_at", table_name="audit_log")
    op.drop_index("idx_audit_log_action", table_name="audit_log")
    op.drop_index("idx_audit_log_user_id", table_name="audit_log")
