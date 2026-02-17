"""Initial schema with all tables, indexes, and audit partitions

Revision ID: 001
Revises:
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Users ---
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("hibob_id", sa.String(255), unique=True, nullable=True),
        sa.Column("department", sa.String(255), nullable=True),
        sa.Column("manager_email", sa.String(255), nullable=True),
        sa.Column("manager_name", sa.String(255), nullable=True),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("total_budget_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cached_spent_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cached_adjustment_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("budget_cache_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("probation_override", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("provider_id", sa.String(255), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="employee"),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column("last_hibob_sync", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_users_hibob_id", "users", ["hibob_id"], postgresql_where=sa.text("hibob_id IS NOT NULL"))
    op.create_index("idx_users_active", "users", ["is_active"])

    # --- Refresh Tokens ---
    op.create_table(
        "refresh_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("jti", sa.String(255), unique=True, nullable=False),
        sa.Column("token_family", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_refresh_jti", "refresh_tokens", ["jti"])
    op.create_index("idx_refresh_family", "refresh_tokens", ["token_family"])
    op.create_index("idx_refresh_user", "refresh_tokens", ["user_id"])
    op.create_index("idx_refresh_expires", "refresh_tokens", ["expires_at"])

    # --- Categories ---
    op.create_table(
        "categories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("icon", sa.String(100), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- Products ---
    op.create_table(
        "products",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("category_id", UUID(as_uuid=True), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("brand", sa.String(255), nullable=True),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column("image_url", sa.Text, nullable=True),
        sa.Column("image_gallery", JSONB, nullable=True),
        sa.Column("specifications", JSONB, nullable=True),
        sa.Column("price_cents", sa.Integer, nullable=False),
        sa.Column("price_min_cents", sa.Integer, nullable=True),
        sa.Column("price_max_cents", sa.Integer, nullable=True),
        sa.Column("icecat_gtin", sa.String(14), nullable=True),
        sa.Column("external_url", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("max_quantity_per_user", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Full-text search vector (generated column)
    op.execute("""
        ALTER TABLE products ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(brand, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(model, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(description, '')), 'C')
        ) STORED
    """)

    op.create_index("idx_products_category", "products", ["category_id"], postgresql_where=sa.text("is_active = TRUE"))
    op.create_index("idx_products_gtin", "products", ["icecat_gtin"], postgresql_where=sa.text("icecat_gtin IS NOT NULL"))
    op.execute("CREATE INDEX idx_products_search ON products USING GIN(search_vector)")
    op.execute("CREATE INDEX idx_products_brand_trgm ON products USING GIN(brand gin_trgm_ops)")
    op.execute("CREATE INDEX idx_products_name_trgm ON products USING GIN(name gin_trgm_ops)")
    op.create_index("idx_products_price", "products", ["price_cents"], postgresql_where=sa.text("is_active = TRUE"))

    # --- Cart Items ---
    op.create_table(
        "cart_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("price_at_add_cents", sa.Integer, nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),
    )
    op.create_index("idx_cart_user", "cart_items", ["user_id"])

    # --- Orders ---
    op.create_table(
        "orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("total_cents", sa.Integer, nullable=False),
        sa.Column("delivery_note", sa.Text, nullable=True),
        sa.Column("admin_note", sa.Text, nullable=True),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_orders_user", "orders", ["user_id"])
    op.create_index("idx_orders_status", "orders", ["status"])

    # --- Order Items ---
    op.create_table(
        "order_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("price_cents", sa.Integer, nullable=False),
        sa.Column("external_url", sa.Text, nullable=False),
        sa.Column("vendor_ordered", sa.Boolean, nullable=False, server_default="false"),
    )
    op.create_index("idx_order_items_order", "order_items", ["order_id"])

    # --- Budget Adjustments ---
    op.create_table(
        "budget_adjustments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_budget_adj_user", "budget_adjustments", ["user_id"])

    # --- Admin Notification Preferences ---
    op.create_table(
        "admin_notification_prefs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), unique=True, nullable=False),
        sa.Column("slack_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("slack_events", JSONB, nullable=False, server_default=sa.text("'[\"order.created\",\"order.cancelled\",\"hibob.sync\"]'::jsonb")),
        sa.Column("email_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("email_events", JSONB, nullable=False, server_default=sa.text("'[\"order.created\"]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_notif_prefs_user", "admin_notification_prefs", ["user_id"])

    # --- App Settings ---
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- HiBob Sync Log ---
    op.create_table(
        "hibob_sync_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("employees_synced", sa.Integer, nullable=False, server_default="0"),
        sa.Column("employees_created", sa.Integer, nullable=False, server_default="0"),
        sa.Column("employees_updated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("employees_deactivated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Audit Log (partitioned by month) ---
    op.execute("""
        CREATE TABLE audit_log (
            id UUID DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            action VARCHAR(255) NOT NULL,
            resource_type VARCHAR(100) NOT NULL,
            resource_id UUID,
            details JSONB,
            ip_address INET,
            correlation_id VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
    """)

    # Create partitions for current month + next 2 months
    op.execute("""
        CREATE TABLE audit_log_2026_02 PARTITION OF audit_log
            FOR VALUES FROM ('2026-02-01') TO ('2026-03-01')
    """)
    op.execute("""
        CREATE TABLE audit_log_2026_03 PARTITION OF audit_log
            FOR VALUES FROM ('2026-03-01') TO ('2026-04-01')
    """)
    op.execute("""
        CREATE TABLE audit_log_2026_04 PARTITION OF audit_log
            FOR VALUES FROM ('2026-04-01') TO ('2026-05-01')
    """)

    op.execute("CREATE INDEX idx_audit_user ON audit_log(user_id, created_at DESC)")
    op.execute("CREATE INDEX idx_audit_action ON audit_log(action)")
    op.execute("CREATE INDEX idx_audit_resource ON audit_log(resource_type, resource_id)")

    # --- Seed default app_settings ---
    op.execute("""
        INSERT INTO app_settings (key, value) VALUES
            ('budget_initial_cents', '75000'),
            ('budget_yearly_increment_cents', '25000'),
            ('probation_months', '6'),
            ('price_refresh_cooldown_minutes', '60'),
            ('price_refresh_rate_limit_per_minute', '10'),
            ('company_name', 'Home Office Shop'),
            ('cart_stale_days', '30')
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_log CASCADE")
    op.drop_table("hibob_sync_log")
    op.drop_table("app_settings")
    op.drop_table("admin_notification_prefs")
    op.drop_table("budget_adjustments")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("cart_items")
    op.drop_table("products")
    op.drop_table("categories")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
