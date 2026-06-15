"""Security headers middleware for FastAPI."""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from magenta.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security hardening headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        headers = settings.security_headers.headers
        for name, value in headers.items():
            response.headers[name] = value
        return response
