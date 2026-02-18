"""Tests for Amazon/ScraperAPI integration: fake client + image service."""
import uuid
from pathlib import Path

import pytest

from src.integrations.amazon.client import (
    AmazonClientProtocol,
    FakeAmazonClient,
    _extract_asin,
    _parse_price_cents,
)
from src.integrations.amazon.models import AmazonProduct, AmazonSearchResult
from src.services.image_service import (
    ImagePaths,
    _generate_placeholder_svg,
    _get_extension,
    download_and_store_product_images,
)


class TestExtractAsin:
    def test_dp_url(self):
        assert _extract_asin("https://www.amazon.de/dp/B08N5WRWNW") == "B08N5WRWNW"

    def test_gp_product_url(self):
        assert _extract_asin("https://www.amazon.de/gp/product/B08N5WRWNW") == "B08N5WRWNW"

    def test_complex_url(self):
        assert _extract_asin("https://www.amazon.de/Some-Product/dp/B08N5WRWNW/ref=sr_1_1") == "B08N5WRWNW"

    def test_no_asin(self):
        assert _extract_asin("https://www.amazon.de/search?q=monitor") is None


class TestParsePriceCents:
    def test_us_format(self):
        assert _parse_price_cents("$29.99") == 2999

    def test_european_format(self):
        assert _parse_price_cents("29,99") == 2999

    def test_european_thousands(self):
        assert _parse_price_cents("1.234,56") == 123456

    def test_empty_string(self):
        assert _parse_price_cents("") == 0

    def test_none(self):
        assert _parse_price_cents(None) == 0

    def test_currency_symbol(self):
        assert _parse_price_cents("EUR 49,99") == 4999


class TestFakeAmazonClient:
    @pytest.mark.asyncio
    async def test_implements_protocol(self):
        client = FakeAmazonClient()
        assert isinstance(client, AmazonClientProtocol)

    @pytest.mark.asyncio
    async def test_search_by_name(self):
        product = AmazonProduct(name="Test Monitor", price_cents=35000)
        client = FakeAmazonClient(products={"B08N5WRWNW": product})
        results = await client.search("monitor")
        assert len(results) == 1
        assert results[0].asin == "B08N5WRWNW"
        assert results[0].name == "Test Monitor"

    @pytest.mark.asyncio
    async def test_search_by_asin(self):
        product = AmazonProduct(name="Test Monitor", price_cents=35000)
        client = FakeAmazonClient(products={"B08N5WRWNW": product})
        results = await client.search("B08N5WRWNW")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_no_match(self):
        client = FakeAmazonClient()
        results = await client.search("nonexistent")
        assert results == []

    @pytest.mark.asyncio
    async def test_get_product(self):
        product = AmazonProduct(
            name="Test Monitor",
            brand="TestBrand",
            price_cents=35000,
        )
        client = FakeAmazonClient(products={"B08N5WRWNW": product})
        result = await client.get_product("B08N5WRWNW")
        assert result is not None
        assert result.name == "Test Monitor"
        assert result.price_cents == 35000

    @pytest.mark.asyncio
    async def test_get_product_unknown(self):
        client = FakeAmazonClient()
        result = await client.get_product("UNKNOWN")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_price(self):
        product = AmazonProduct(name="Monitor", price_cents=45000)
        client = FakeAmazonClient(products={"B08N5WRWNW": product})
        price = await client.get_current_price("B08N5WRWNW")
        assert price == 45000

    @pytest.mark.asyncio
    async def test_get_current_price_zero_returns_none(self):
        product = AmazonProduct(name="Monitor", price_cents=0)
        client = FakeAmazonClient(products={"B08N5WRWNW": product})
        price = await client.get_current_price("B08N5WRWNW")
        assert price is None

    @pytest.mark.asyncio
    async def test_get_current_price_unknown_asin(self):
        client = FakeAmazonClient()
        price = await client.get_current_price("unknown")
        assert price is None


class TestPlaceholderSvg:
    def test_generates_valid_svg(self):
        svg_bytes = _generate_placeholder_svg("Test Product")
        svg = svg_bytes.decode("utf-8")
        assert "<svg" in svg
        assert "TP" in svg
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
        assert svg1 != svg2


class TestGetExtension:
    def test_jpeg_content_type(self):
        assert _get_extension("", "image/jpeg") == ".jpg"

    def test_png_content_type(self):
        assert _get_extension("", "image/png") == ".png"

    def test_webp_content_type(self):
        assert _get_extension("", "image/webp") == ".webp"

    def test_svg_content_type_rejected(self):
        assert _get_extension("", "image/svg+xml") == ".jpg"  # SVG not allowed

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

        svg_path = tmp_path / "products" / str(product_id) / "placeholder.svg"
        assert svg_path.exists()
        content = svg_path.read_text()
        assert "TP" in content

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
        assert result.gallery == []

    @pytest.mark.asyncio
    async def test_creates_product_directory(self, tmp_path):
        product_id = uuid.uuid4()
        await download_and_store_product_images(
            product_id, None, [], tmp_path, "Dir Test",
        )
        assert (tmp_path / "products" / str(product_id)).is_dir()
