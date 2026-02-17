import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # Propagate request_id to logging context via a filter
        log_filter = _RequestIdFilter(request_id)
        root_logger = logging.getLogger()
        root_logger.addFilter(log_filter)
        try:
            response = await call_next(request)
        finally:
            root_logger.removeFilter(log_filter)

        response.headers["X-Request-ID"] = request_id
        return response


class _RequestIdFilter(logging.Filter):
    def __init__(self, request_id: str):
        super().__init__()
        self.request_id = request_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = self.request_id
        return True
