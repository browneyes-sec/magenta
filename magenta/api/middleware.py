"""API middleware: auth, rate limiting, request logging."""

from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import time
import jwt


async def validate_auth(request: Request) -> dict:
    """Validate JWT or API key from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    # Stub — real implementation validates Entra ID JWT or API key
    return {"authenticated": True, "tenant": "default"}


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self):
        self._requests: dict[str, list[float]] = {}

    async def check(self, key: str, max_requests: int = 100, window_seconds: int = 60) -> bool:
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
