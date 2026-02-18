"""Add product archiving, brands table, and order cancellation fields.

Revision ID: 004
Revises: 003
Create Date: 2026-02-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Brands table ---
    op.create_table(
        "brands",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column("logo_url", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- Products: archived_at + brand_id ---
    op.add_column("products", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("products", sa.Column("brand_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_products_brand_id", "products", "brands", ["brand_id"], ["id"])

    # --- Orders: cancellation fields ---
    op.add_column("orders", sa.Column("cancellation_reason", sa.Text, nullable=True))
    op.add_column("orders", sa.Column("cancelled_by", UUID(as_uuid=True), nullable=True))
    op.add_column("orders", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_orders_cancelled_by", "orders", "users", ["cancelled_by"], ["id"])

    # --- Data migration: create Brand rows from existing distinct product.brand values ---
    op.execute("""
        INSERT INTO brands (id, name, slug, created_at)
        SELECT gen_random_uuid(), brand, LOWER(REPLACE(REPLACE(brand, ' ', '-'), '.', '')), NOW()
        FROM (SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL AND brand != '') AS sub
        ON CONFLICT (name) DO NOTHING
    """)

    # Set brand_id on products that have a matching brand text
    op.execute("""
        UPDATE products p
        SET brand_id = b.id
        FROM brands b
        WHERE p.brand = b.name AND p.brand IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_constraint("fk_orders_cancelled_by", "orders", type_="foreignkey")
    op.drop_column("orders", "cancelled_at")
    op.drop_column("orders", "cancelled_by")
    op.drop_column("orders", "cancellation_reason")

    op.drop_constraint("fk_products_brand_id", "products", type_="foreignkey")
    op.drop_column("products", "brand_id")
    op.drop_column("products", "archived_at")

    op.drop_table("brands")
