"""Remove Slack notification columns from admin_notification_prefs.

Revision ID: 018
Revises: 017
Create Date: 2026-02-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("admin_notification_prefs", "slack_enabled")
    op.drop_column("admin_notification_prefs", "slack_events")


def downgrade() -> None:
    op.add_column(
        "admin_notification_prefs",
        sa.Column(
            "slack_events", JSONB, nullable=False,
            server_default=sa.text("'[\"order.created\",\"order.cancelled\"]'::jsonb"),
        ),
    )
    op.add_column(
        "admin_notification_prefs",
        sa.Column(
            "slack_enabled", sa.Boolean, nullable=False,
            server_default="true",
        ),
    )
