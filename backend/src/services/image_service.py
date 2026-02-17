import hashlib
import logging
from pathlib import Path
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


class ImagePaths:
    def __init__(self, main_image: str | None, gallery: list[str]):
        self.main_image = main_image
        self.gallery = gallery


def _generate_placeholder_svg(product_name: str) -> bytes:
    """Generate SVG placeholder with product name initials."""
    words = product_name.split()[:2]
    initials = "".join(w[0].upper() for w in words if w) or "?"
    color_hash = hashlib.md5(product_name.encode()).hexdigest()[:6]
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
  <rect width="400" height="400" fill="#{color_hash}"/>
  <text x="200" y="220" text-anchor="middle" font-family="Arial,sans-serif"
        font-size="120" font-weight="bold" fill="white">{initials}</text>
</svg>"""
    return svg.encode("utf-8")


async def download_and_store_product_images(
    product_id: UUID,
    main_image_url: str | None,
    gallery_urls: list[str],
    upload_dir: Path,
    product_name: str = "Product",
) -> ImagePaths:
    product_dir = upload_dir / "products" / str(product_id)
    product_dir.mkdir(parents=True, exist_ok=True)

    main_image_path = None
    gallery_paths = []

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        if main_image_url:
            try:
                resp = await client.get(main_image_url)
                resp.raise_for_status()
                ext = _get_extension(main_image_url, resp.headers.get("content-type", ""))
                filename = f"main{ext}"
                filepath = product_dir / filename
                filepath.write_bytes(resp.content)
                main_image_path = f"/uploads/products/{product_id}/{filename}"
                logger.info("Downloaded main image for product %s", product_id)
            except Exception:
                logger.warning("Failed to download main image for product %s", product_id)

        if not main_image_path:
            svg_data = _generate_placeholder_svg(product_name)
            filepath = product_dir / "placeholder.svg"
            filepath.write_bytes(svg_data)
            main_image_path = f"/uploads/products/{product_id}/placeholder.svg"

        for i, url in enumerate(gallery_urls):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                ext = _get_extension(url, resp.headers.get("content-type", ""))
                filename = f"gallery_{i}{ext}"
                filepath = product_dir / filename
                filepath.write_bytes(resp.content)
                gallery_paths.append(f"/uploads/products/{product_id}/{filename}")
            except Exception:
                logger.warning(
                    "Failed to download gallery image %d for product %s", i, product_id
                )

    return ImagePaths(main_image=main_image_path, gallery=gallery_paths)


def _get_extension(url: str, content_type: str) -> str:
    ct_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/svg+xml": ".svg",
    }
    for ct, ext in ct_map.items():
        if ct in content_type:
            return ext

    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"):
        if ext in url.lower():
            return ext

    return ".jpg"
