import time
from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings

settings = get_settings()

_memory_store: dict[str, tuple[int, float]] = {}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method == "OPTIONS" or not settings.rate_limit_enabled:
            return await call_next(request)

        if request.url.path in settings.rate_limit_exempt_paths_list:
            return await call_next(request)

        identifier = request.client.host if request.client else "unknown"
        bucket_key = f"ratelimit:{identifier}:{request.url.path}"
        limit = settings.rate_limit_requests
        window = settings.rate_limit_window_seconds

        count = await _increase_counter(bucket_key, window)
        if count > limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(window)},
            )

        response = await call_next(request)
        response.headers["x-rate-limit-limit"] = str(limit)
        response.headers["x-rate-limit-remaining"] = str(max(limit - count, 0))
        response.headers["x-rate-limit-window"] = str(window)
        return response


async def _increase_counter(key: str, window_seconds: int) -> int:
    # Redis removed; using in-memory fallback only
    now = time.time()
    count, expires_at = _memory_store.get(key, (0, now + window_seconds))
    if now > expires_at:
        count = 0
        expires_at = now + window_seconds
    count += 1
    _memory_store[key] = (count, expires_at)
    return count
