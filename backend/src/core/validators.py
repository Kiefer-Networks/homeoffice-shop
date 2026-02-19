from urllib.parse import urlparse


def validate_http_url(v: str | None) -> str | None:
    """Validate that a URL uses http or https scheme."""
    if v is not None:
        parsed = urlparse(v)
        if parsed.scheme not in ("https", "http") or not parsed.netloc:
            raise ValueError("URL must be a valid http:// or https:// URL")
    return v
