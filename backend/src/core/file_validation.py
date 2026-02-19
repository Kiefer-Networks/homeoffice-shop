MAGIC_BYTES = {
    'application/pdf': [b'%PDF'],
    'image/jpeg': [b'\xff\xd8\xff'],
    'image/png': [b'\x89PNG'],
    'image/gif': [b'GIF87a', b'GIF89a'],
    'image/webp': [b'RIFF'],  # RIFF....WEBP
}

ALLOWED_INVOICE_TYPES = {'application/pdf', 'image/jpeg', 'image/png'}
MAX_INVOICE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_file_magic(content: bytes, claimed_content_type: str) -> bool:
    """Validate file content matches claimed Content-Type via magic bytes."""
    signatures = MAGIC_BYTES.get(claimed_content_type, [])
    if not signatures:
        return False
    return any(content.startswith(sig) for sig in signatures)
