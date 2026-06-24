"""API middleware: auth, rate limiting, request logging."""

import os
import time
from uuid import uuid4

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


async def validate_auth(request: Request) -> dict:
    """Validate JWT or API key from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    # Stub — real implementation validates Entra ID JWT or API key
    return {"authenticated": True, "tenant": "default"}


async def get_tenant_id(request: Request) -> str:
    """Extract tenant_id from JWT/auth context for multi-tenant isolation (ADR-018).

    Returns tenant_id from JWT ``tid`` claim (Entra ID standard) or
    defaults to "default" for dev mode.
    """
    # First check if JWT middleware already decoded the token
    if hasattr(request.state, "token_payload"):
        payload = request.state.token_payload
        tid = payload.get("tid")
        if tid:
            return tid

    return "default"


class RateLimiter:
    """In-memory sliding window rate limiter with optional Redis persistence."""

    def __init__(self):
        self._requests: dict[str, list[float]] = {}

    async def check(self, key: str, max_requests: int = 100, window_seconds: int = 60) -> bool:
        now = time.time()
        if key not in self._requests:
            self._requests[key] = []

        self._requests[key] = [t for t in self._requests[key] if now - t < window_seconds]

        if len(self._requests[key]) >= max_requests:
            return False

        self._requests[key].append(now)
        return True


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that enforces per-IP rate limits.

    Defaults: 100 requests per 60s window. Configurable via
    MAGENTA_RATE_LIMIT_MAX and MAGENTA_RATE_LIMIT_WINDOW env vars.
    """

    def __init__(self, app, max_requests: int = 0, window_seconds: int = 0):
        super().__init__(app)
        self.max_requests = max_requests or int(os.getenv("MAGENTA_RATE_LIMIT_MAX", "100"))
        self.window_seconds = window_seconds or int(os.getenv("MAGENTA_RATE_LIMIT_WINDOW", "60"))
        self._excluded_paths = {"/", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in self._excluded_paths or path.startswith("/metrics"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"rate:{client_ip}:{path.rsplit('/', 1)[0]}"

        allowed = await rate_limiter.check(
            key, max_requests=self.max_requests, window_seconds=self.window_seconds
        )
        if not allowed:
            return Response(
                content='{"detail":"Rate limit exceeded. Try again later."}',
                status_code=429,
                media_type="application/json",
            )

        return await call_next(request)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Attaches a unique correlation_id to every request/response.

    The correlation_id is stored in request.state.correlation_id for downstream
    use and returned in the X-Correlation-ID response header.
    """

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", f"req-{uuid4().hex[:12]}")
        request.state.correlation_id = correlation_id

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
