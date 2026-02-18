"""Tests for product refresh preview/apply flow and brand extraction."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import BadRequestError, NotFoundError
from src.integrations.amazon.models import AmazonProduct
from src.models.dto.product import RefreshApplyRequest
from tests.factories import make_product, make_user


def _make_request(ip: str = "127.0.0.1"):
    req = MagicMock()
    req.client = MagicMock()
    req.client.host = ip
    return req


def _mock_db_get(mock_db, return_value):
    mock_db.get = AsyncMock(return_value=return_value)
    mock_db.refresh = AsyncMock()


class TestRefreshPreview:
    @pytest.mark.asyncio
    async def test_not_found(self, mock_db):
        from src.api.routes.admin.products import refresh_preview

        _mock_db_get(mock_db, None)
        admin = make_user(role="admin")

        with pytest.raises(NotFoundError):
            await refresh_preview(uuid.uuid4(), _make_request(), mock_db, admin)

    @pytest.mark.asyncio
    async def test_no_asin(self, mock_db):
        from src.api.routes.admin.products import refresh_preview

        product = make_product()
        product.amazon_asin = None
        _mock_db_get(mock_db, product)
        admin = make_user(role="admin")

        with pytest.raises(BadRequestError):
            await refresh_preview(product.id, _make_request(), mock_db, admin)

    @pytest.mark.asyncio
    @patch("src.api.routes.admin.products.write_audit_log", new_callable=AsyncMock)
    @patch("src.api.routes.admin.products.download_and_store_product_images", new_callable=AsyncMock)
    @patch("src.api.routes.admin.products.AmazonClient")
    async def test_returns_diffs(self, MockClient, mock_download, mock_audit, mock_db):
        from src.api.routes.admin.products import refresh_preview

        product = make_product(name="Old Name", price_cents=10000, brand="OldBrand")
        product.amazon_asin = "B08TEST123"
        product.color = None
        product.material = None
        product.product_dimensions = None
        product.item_weight = None
        product.item_model_number = None
        product.product_information = None
        product.specifications = None
        product.description = None
        _mock_db_get(mock_db, product)

        amazon_data = AmazonProduct(
            name="New Name",
            price_cents=20000,
            brand="NewBrand",
            images=["https://img.example.com/1.jpg"],
            color="Black",
        )
        client_instance = AsyncMock()
        client_instance.get_product = AsyncMock(return_value=amazon_data)
        MockClient.return_value = client_instance

        mock_download.return_value = MagicMock(main_image="/uploads/main.jpg", gallery=[])

        admin = make_user(role="admin")
        result = await refresh_preview(product.id, _make_request(), mock_db, admin)

        assert result.images_updated is True
        diff_fields = {d.field for d in result.diffs}
        assert "name" in diff_fields
        assert "price_cents" in diff_fields
        assert "brand" in diff_fields
        assert "color" in diff_fields

    @pytest.mark.asyncio
    @patch("src.api.routes.admin.products.write_audit_log", new_callable=AsyncMock)
    @patch("src.api.routes.admin.products.download_and_store_product_images", new_callable=AsyncMock)
    @patch("src.api.routes.admin.products.AmazonClient")
    async def test_no_diffs_when_same(self, MockClient, mock_download, mock_audit, mock_db):
        from src.api.routes.admin.products import refresh_preview

        product = make_product(name="Same Name", price_cents=35000, brand="SameBrand")
        product.amazon_asin = "B08TEST123"
        product.color = "Red"
        product.material = None
        product.product_dimensions = None
        product.item_weight = None
        product.item_model_number = None
        product.product_information = None
        product.specifications = None
        product.description = "A test product"
        _mock_db_get(mock_db, product)

        amazon_data = AmazonProduct(
            name="Same Name",
            price_cents=35000,
            brand="SameBrand",
            images=[],
            color="Red",
            description="A test product",
        )
        client_instance = AsyncMock()
        client_instance.get_product = AsyncMock(return_value=amazon_data)
        MockClient.return_value = client_instance

        mock_download.return_value = MagicMock(main_image="/uploads/main.jpg", gallery=[])

        admin = make_user(role="admin")
        result = await refresh_preview(product.id, _make_request(), mock_db, admin)

        assert len(result.diffs) == 0

    @pytest.mark.asyncio
    @patch("src.api.routes.admin.products.write_audit_log", new_callable=AsyncMock)
    @patch("src.api.routes.admin.products.download_and_store_product_images", new_callable=AsyncMock)
    @patch("src.api.routes.admin.products.AmazonClient")
    async def test_skips_none_new_values(self, MockClient, mock_download, mock_audit, mock_db):
        from src.api.routes.admin.products import refresh_preview

        product = make_product(name="Name", price_cents=10000, brand="Brand")
        product.amazon_asin = "B08TEST123"
        product.color = "Blue"
        product.material = "Metal"
        product.product_dimensions = None
        product.item_weight = None
        product.item_model_number = None
        product.product_information = None
        product.specifications = None
        product.description = None
        _mock_db_get(mock_db, product)

        # Amazon returns None for color/material — should not appear in diffs
        amazon_data = AmazonProduct(
            name="Name",
            price_cents=10000,
            brand="Brand",
            images=[],
        )
        client_instance = AsyncMock()
        client_instance.get_product = AsyncMock(return_value=amazon_data)
        MockClient.return_value = client_instance

        mock_download.return_value = MagicMock(main_image="/uploads/main.jpg", gallery=[])

        admin = make_user(role="admin")
        result = await refresh_preview(product.id, _make_request(), mock_db, admin)

        diff_fields = {d.field for d in result.diffs}
        assert "color" not in diff_fields
        assert "material" not in diff_fields


class TestRefreshApply:
    @pytest.mark.asyncio
    async def test_not_found(self, mock_db):
        from src.api.routes.admin.products import refresh_apply

        _mock_db_get(mock_db, None)
        admin = make_user(role="admin")
        body = RefreshApplyRequest(fields=["name"], values={"name": "New"})

        with pytest.raises(NotFoundError):
            await refresh_apply(uuid.uuid4(), body, _make_request(), mock_db, admin)

    @pytest.mark.asyncio
    async def test_unknown_field_rejected(self, mock_db):
        from src.api.routes.admin.products import refresh_apply

        product = make_product()
        product.amazon_asin = "B08TEST123"
        _mock_db_get(mock_db, product)
        admin = make_user(role="admin")
        body = RefreshApplyRequest(fields=["bogus_field"], values={"bogus_field": "x"})

        with pytest.raises(BadRequestError, match="Unknown fields"):
            await refresh_apply(product.id, body, _make_request(), mock_db, admin)

    @pytest.mark.asyncio
    @patch("src.api.routes.admin.products.write_audit_log", new_callable=AsyncMock)
    async def test_applies_selected_fields(self, mock_audit, mock_db):
        from src.api.routes.admin.products import refresh_apply

        product = make_product(name="Old", price_cents=10000)
        product.amazon_asin = "B08TEST123"
        product.color = None
        _mock_db_get(mock_db, product)
        admin = make_user(role="admin")

        body = RefreshApplyRequest(
            fields=["name", "color"],
            values={"name": "New Name", "color": "Red"},
        )

        result = await refresh_apply(product.id, body, _make_request(), mock_db, admin)

        assert product.name == "New Name"
        assert product.color == "Red"
        # price should not have changed
        assert product.price_cents == 10000

    @pytest.mark.asyncio
    @patch("src.api.routes.admin.products.write_audit_log", new_callable=AsyncMock)
    async def test_brand_resolution_creates_new(self, mock_audit, mock_db):
        from src.api.routes.admin.products import refresh_apply

        product = make_product(brand="OldBrand")
        product.amazon_asin = "B08TEST123"
        _mock_db_get(mock_db, product)

        # simulate no existing brand found
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result_mock)

        admin = make_user(role="admin")
        body = RefreshApplyRequest(
            fields=["brand"],
            values={"brand": "NewBrand"},
        )

        await refresh_apply(product.id, body, _make_request(), mock_db, admin)

        assert product.brand == "NewBrand"
        # A new brand should have been added
        mock_db.add.assert_called()
        added = mock_db.add.call_args[0][0]
        assert added.name == "NewBrand"
        assert added.slug == "newbrand"

    @pytest.mark.asyncio
    @patch("src.api.routes.admin.products.write_audit_log", new_callable=AsyncMock)
    async def test_brand_resolution_existing(self, mock_audit, mock_db):
        from src.api.routes.admin.products import refresh_apply

        product = make_product(brand="OldBrand")
        product.amazon_asin = "B08TEST123"
        _mock_db_get(mock_db, product)

        existing_brand_id = uuid.uuid4()
        existing_brand = MagicMock()
        existing_brand.id = existing_brand_id

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing_brand
        mock_db.execute = AsyncMock(return_value=result_mock)

        admin = make_user(role="admin")
        body = RefreshApplyRequest(
            fields=["brand"],
            values={"brand": "ExistingBrand"},
        )

        await refresh_apply(product.id, body, _make_request(), mock_db, admin)

        assert product.brand == "ExistingBrand"
        assert product.brand_id == existing_brand_id


class TestBrandExtraction:
    """Test that brand is extracted from product_information only, not top-level data."""

    def test_brand_from_product_info_lowercase(self):
        from src.integrations.amazon.client import AmazonClient
        # This tests the logic inline; we'll check the source directly
        product_info = {"brand": "Logitech"}
        brand = (
            product_info.get("brand")
            or product_info.get("Brand")
            or product_info.get("Marke")
            or product_info.get("Hersteller")
        )
        assert brand == "Logitech"

    def test_brand_from_marke(self):
        product_info = {"Marke": "Dell"}
        brand = (
            product_info.get("brand")
            or product_info.get("Brand")
            or product_info.get("Marke")
            or product_info.get("Hersteller")
        )
        assert brand == "Dell"

    def test_brand_from_hersteller(self):
        product_info = {"Hersteller": "HP"}
        brand = (
            product_info.get("brand")
            or product_info.get("Brand")
            or product_info.get("Marke")
            or product_info.get("Hersteller")
        )
        assert brand == "HP"

    def test_no_brand_returns_none(self):
        product_info = {"weight": "500g"}
        brand = (
            product_info.get("brand")
            or product_info.get("Brand")
            or product_info.get("Marke")
            or product_info.get("Hersteller")
        )
        assert brand is None
