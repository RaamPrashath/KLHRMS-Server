"""
ASGI middleware that reads or generates a correlation ID (X-Request-ID) for
every HTTP request, stores it in a contextvar for all downstream logging,
and echoes it back in the response headers.
"""

from __future__ import annotations

from uuid import uuid4

from app.shared.logging_config import set_request_id


class RequestContextMiddleware:
    """ASGI middleware — injects X-Request-ID context and response header."""

    def __init__(self, app):  # type: ignore[no-untyped-def]
        self.app = app

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract raw headers as a dict (bytes -> bytes)
        headers: dict[bytes, bytes] = dict(scope.get("headers", []))

        raw = headers.get(b"x-request-id")
        if raw:
            request_id = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        else:
            request_id = str(uuid4())

        set_request_id(request_id)

        async def send_wrapper(message):  # type: ignore[no-untyped-def]
            if message["type"] == "http.response.start":
                resp_headers: list[tuple[bytes, bytes]] = list(
                    message.get("headers", [])
                )
                resp_headers.append(
                    (b"x-request-id", request_id.encode("utf-8"))
                )
                message["headers"] = resp_headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
