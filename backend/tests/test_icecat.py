"""Tests for Icecat integration: fake client + image downloader."""
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.integrations.icecat.client import FakeIcecatClient, IcecatClientProtocol
from src.integrations.icecat.image_downloader import (
    ImagePaths,
    _generate_placeholder_svg,
    _get_extension,
    download_and_store_product_images,
)
from src.integrations.icecat.models import IcecatProduct


class TestFakeIcecatClient:
    @pytest.mark.asyncio
    async def test_implements_protocol(self):
        client = FakeIcecatClient()
        assert isinstance(client, IcecatClientProtocol)

    @pytest.mark.asyncio
    async def test_returns_product_by_gtin(self):
        product = IcecatProduct(
            title="Test Monitor",
            brand="TestBrand",
            price_cents=35000,
        )
        client = FakeIcecatClient(products={"1234567890123": product})
        result = await client.lookup_by_gtin("1234567890123")
        assert result is not None
        assert result.title == "Test Monitor"
        assert result.price_cents == 35000

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_gtin(self):
        client = FakeIcecatClient()
        result = await client.lookup_by_gtin("9999999999999")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_price(self):
        product = IcecatProduct(title="Monitor", price_cents=45000)
        client = FakeIcecatClient(products={"123": product})
        price = await client.get_current_price("123")
        assert price == 45000

    @pytest.mark.asyncio
    async def test_get_current_price_zero_returns_none(self):
        product = IcecatProduct(title="Monitor", price_cents=0)
        client = FakeIcecatClient(products={"123": product})
        price = await client.get_current_price("123")
        assert price is None

    @pytest.mark.asyncio
    async def test_get_current_price_unknown_gtin(self):
        client = FakeIcecatClient()
        price = await client.get_current_price("unknown")
        assert price is None


class TestPlaceholderSvg:
    def test_generates_valid_svg(self):
        svg_bytes = _generate_placeholder_svg("Test Product")
        svg = svg_bytes.decode("utf-8")
        assert "<svg" in svg
        assert "TP" in svg  # initials of Test Product
        assert "400" in svg

    def test_single_word(self):
        svg = _generate_placeholder_svg("Monitor").decode("utf-8")
        assert "M" in svg

    def test_empty_name_uses_question_mark(self):
        svg = _generate_placeholder_svg("").decode("utf-8")
        assert "?" in svg

    def test_deterministic_color(self):
        svg1 = _generate_placeholder_svg("Same Name").decode("utf-8")
        svg2 = _generate_placeholder_svg("Same Name").decode("utf-8")
        assert svg1 == svg2

    def test_different_names_different_colors(self):
        svg1 = _generate_placeholder_svg("Product A").decode("utf-8")
        svg2 = _generate_placeholder_svg("Product B").decode("utf-8")
        # Different products should (likely) have different colors
        # Extract the fill color
        assert svg1 != svg2


class TestGetExtension:
    def test_jpeg_content_type(self):
        assert _get_extension("", "image/jpeg") == ".jpg"

    def test_png_content_type(self):
        assert _get_extension("", "image/png") == ".png"

    def test_webp_content_type(self):
        assert _get_extension("", "image/webp") == ".webp"

    def test_svg_content_type(self):
        assert _get_extension("", "image/svg+xml") == ".svg"

    def test_fallback_to_url_extension(self):
        assert _get_extension("https://example.com/image.png", "") == ".png"

    def test_default_jpg(self):
        assert _get_extension("https://example.com/image", "") == ".jpg"


class TestDownloadAndStoreProductImages:
    @pytest.mark.asyncio
    async def test_creates_placeholder_when_no_url(self, tmp_path):
        product_id = uuid.uuid4()
        result = await download_and_store_product_images(
            product_id, None, [], tmp_path, "Test Product",
        )
        assert result.main_image is not None
        assert "placeholder.svg" in result.main_image
        assert result.gallery == []

        # Verify file exists on disk
        svg_path = tmp_path / "products" / str(product_id) / "placeholder.svg"
        assert svg_path.exists()
        content = svg_path.read_text()
        assert "TP" in content  # initials

    @pytest.mark.asyncio
    async def test_creates_placeholder_on_download_failure(self, tmp_path):
        product_id = uuid.uuid4()
        result = await download_and_store_product_images(
            product_id,
            "https://nonexistent.example.com/image.jpg",
            [],
            tmp_path,
            "Failed Download",
        )
        assert result.main_image is not None
        assert "placeholder.svg" in result.main_image

    @pytest.mark.asyncio
    async def test_gallery_failures_skipped(self, tmp_path):
        product_id = uuid.uuid4()
        result = await download_and_store_product_images(
            product_id,
            None,
            ["https://nonexistent.example.com/g1.jpg", "https://nonexistent.example.com/g2.jpg"],
            tmp_path,
            "Product",
        )
        assert result.gallery == []  # both failed, none stored

    @pytest.mark.asyncio
    async def test_creates_product_directory(self, tmp_path):
        product_id = uuid.uuid4()
        await download_and_store_product_images(
            product_id, None, [], tmp_path, "Dir Test",
        )
        assert (tmp_path / "products" / str(product_id)).is_dir()
