"""Small deployment guardrails for the research API.

The API key is a shared deployment token, not per-user identity. Public hosting
should also use HTTPS and an edge proxy with its own authentication and limits.
"""

from __future__ import annotations

import json
import secrets
import time
from collections import defaultdict, deque
from typing import Any


class APIAccessMiddleware:
    """Optionally require a server-configured key and limit API traffic."""

    def __init__(
        self,
        app: Any,
        *,
        api_key: str | None,
        auth_required: bool,
        max_body_bytes: int = 25 * 1024 * 1024,
        rate_limit_per_minute: int = 120,
        window_seconds: int = 60,
    ) -> None:
        self.app = app
        self.api_key = api_key
        self.auth_required = auth_required
        self.max_body_bytes = max_body_bytes
        self.rate_limit_per_minute = rate_limit_per_minute
        self.window_seconds = window_seconds
        self.requests: dict[str, deque[float]] = defaultdict(deque)

    async def _respond(self, send, status_code: int, detail: str, headers=None) -> None:
        body = json.dumps({"detail": detail}).encode("utf-8")
        response_headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
        ]
        for name, value in (headers or {}).items():
            response_headers.append((name.lower().encode("ascii"), value.encode("ascii")))
        await send({"type": "http.response.start", "status": status_code, "headers": response_headers})
        await send({"type": "http.response.body", "body": body})

    def _rate_limited(self, client: str, now: float) -> bool:
        cutoff = now - self.window_seconds
        calls = self.requests[client]
        while calls and calls[0] <= cutoff:
            calls.popleft()
        if len(calls) >= self.rate_limit_per_minute:
            return True
        calls.append(now)
        return False

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/"):
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        method = scope["method"].upper()
        public_health = path == "/api/health" and method == "GET"
        preflight = method == "OPTIONS"
        if public_health or preflight:
            await self.app(scope, receive, send)
            return

        client_info = scope.get("client")
        client = str(client_info[0]) if client_info else "unknown"
        if self._rate_limited(client, time.monotonic()):
            await self._respond(send, 429, "Too many API requests. Wait briefly and retry.", {"retry-after": "60"})
            return

        if self.auth_required and not self.api_key:
            await self._respond(send, 503, "API authentication is required but no server key is configured.")
            return
        if self.api_key:
            headers = {key.lower(): value for key, value in scope.get("headers", [])}
            supplied = headers.get(b"x-api-key", b"")
            if not secrets.compare_digest(supplied, self.api_key.encode("utf-8")):
                await self._respond(send, 401, "A valid API key is required.")
                return

        if method not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.max_body_bytes:
                    await self._respond(send, 413, "Request body exceeds the configured API size limit.")
                    return
            except ValueError:
                await self._respond(send, 400, "Invalid Content-Length header.")
                return

        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > self.max_body_bytes:
                await self._respond(send, 413, "Request body exceeds the configured API size limit.")
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        body = b"".join(chunks)
        replayed = False

        async def replay_body():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay_body, send)
