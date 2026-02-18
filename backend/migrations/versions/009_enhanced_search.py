"""Enhanced search: trigger-maintained search_vector with category names and JSONB values.

Revision ID: 009
Revises: 008
Create Date: 2026-02-18
"""
from typing import Sequence, Union

from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop existing GIN index and generated column
    op.execute("DROP INDEX IF EXISTS idx_products_search")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS search_vector")

    # 2. Recreate as plain tsvector column
    op.execute("ALTER TABLE products ADD COLUMN search_vector tsvector")

    # 3. Create trigger function that builds the search vector
    op.execute("""
        CREATE OR REPLACE FUNCTION products_search_vector_update()
        RETURNS trigger AS $$
        DECLARE
            cat_name TEXT;
            info_text TEXT;
        BEGIN
            -- Get category name
            SELECT name INTO cat_name FROM categories WHERE id = NEW.category_id;

            -- Aggregate all product_information JSONB values into one string
            SELECT string_agg(value, ' ')
            INTO info_text
            FROM jsonb_each_text(COALESCE(NEW.product_information, '{}'::jsonb));

            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.name, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.brand, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(cat_name, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.model, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.color, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.material, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.description, '')), 'C') ||
                setweight(to_tsvector('english', coalesce(info_text, '')), 'D');

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 4. Attach trigger to products table
    op.execute("""
        CREATE TRIGGER trg_products_search_vector
        BEFORE INSERT OR UPDATE ON products
        FOR EACH ROW
        EXECUTE FUNCTION products_search_vector_update();
    """)

    # 5. Category rename trigger: when category name changes, touch products to re-fire search trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION categories_name_update()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.name IS DISTINCT FROM NEW.name THEN
                UPDATE products SET updated_at = now() WHERE category_id = NEW.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_categories_name_update
        AFTER UPDATE ON categories
        FOR EACH ROW
        EXECUTE FUNCTION categories_name_update();
    """)

    # 6. Backfill: touch all products to populate search_vector
    op.execute("UPDATE products SET updated_at = now()")

    # 7. Recreate GIN index
    op.execute("CREATE INDEX idx_products_search ON products USING GIN(search_vector)")


def downgrade() -> None:
    # Drop triggers and functions
    op.execute("DROP TRIGGER IF EXISTS trg_products_search_vector ON products")
    op.execute("DROP FUNCTION IF EXISTS products_search_vector_update()")
    op.execute("DROP TRIGGER IF EXISTS trg_categories_name_update ON categories")
    op.execute("DROP FUNCTION IF EXISTS categories_name_update()")

    # Drop the plain column and index
    op.execute("DROP INDEX IF EXISTS idx_products_search")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS search_vector")

    # Restore original GENERATED ALWAYS column
    op.execute("""
        ALTER TABLE products ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(brand, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(model, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(description, '')), 'C')
        ) STORED
    """)

    op.execute("CREATE INDEX idx_products_search ON products USING GIN(search_vector)")
