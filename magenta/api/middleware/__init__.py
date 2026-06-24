"""API middleware: auth, rate limiting, request logging."""

import time

import jwt
from fastapi import HTTPException, Request


async def validate_auth(request: Request) -> dict:
    """Validate JWT or API key from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    # Stub — real implementation validates Entra ID JWT or API key
    return {"authenticated": True, "tenant": "default"}


async def get_tenant_id(request: Request) -> str:
    """Extract tenant_id from JWT/auth context for multi-tenant isolation (ADR-018).

    Returns tenant_id from JWT `tid` claim (Entra ID standard) or defaults to "default" for dev mode.
    """
    # First check if JWT middleware already decoded the token
    if hasattr(request.state, "token_payload"):
        payload = request.state.token_payload
        tid = payload.get("tid")
        if tid:
            return tid

    # Fallback: decode JWT without verification (for dev mode or when middleware disabled)
    auth_header = request.headers.get("Authorization", "")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
        try:
            # Decode without verification for tenant extraction
            payload = jwt.decode(token, options={"verify_signature": False})
            tid = payload.get("tid")
            if tid:
                return tid
        except Exception:
            pass

    return "default"


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self):
        self._requests: dict[str, list[float]] = {}

    async def check(
        self, key: str, max_requests: int = 100, window_seconds: int = 60
    ) -> bool:
        now = time.time()
        if key not in self._requests:
            self._requests[key] = []

        self._requests[key] = [
            t for t in self._requests[key] if now - t < window_seconds
        ]

        if len(self._requests[key]) >= max_requests:
            return False

        self._requests[key].append(now)
        return True


rate_limiter = RateLimiter()
