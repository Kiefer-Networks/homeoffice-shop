import json
import logging
import sys
from datetime import datetime, timezone


_SENSITIVE_KEYS = {"password", "secret", "token", "api_key", "authorization"}
_DEFAULT_LOG_RECORD_KEYS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


def _sanitize_value(data: dict) -> dict:
    """Replace values for keys containing sensitive terms with '********'."""
    sanitized = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(s in key_lower for s in _SENSITIVE_KEYS):
            sanitized[key] = "********"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_value(value)
        else:
            sanitized[key] = value
    return sanitized


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Read request_id from contextvars (async-safe)
        from src.api.middleware.request_id import request_id_var
        request_id = request_id_var.get("")
        if request_id:
            log_entry["request_id"] = request_id
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Sanitize any extra fields that may contain sensitive data
        extra = {
            k: v for k, v in record.__dict__.items()
            if k not in _DEFAULT_LOG_RECORD_KEYS and k not in ("message", "asctime")
        }
        if extra:
            extra = _sanitize_value(extra)
            log_entry["extra"] = extra
        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    """Configure structured JSON logging for the application."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
