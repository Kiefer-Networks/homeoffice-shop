def ilike_escape(q: str) -> str:
    """Escape special LIKE/ILIKE characters and wrap in wildcards."""
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
