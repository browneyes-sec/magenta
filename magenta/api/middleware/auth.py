"""Entra ID JWT authentication middleware."""

from typing import Optional
import json
import logging

import jwt
import httpx
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from magenta.config import settings

logger = logging.getLogger(__name__)

JWKS_CACHE: dict[str, list[dict]] = {}
JWKS_URL = (
    f"https://login.microsoftonline.com/"
    f"{settings.entra_jwt.tenant_id}/discovery/v2.0/keys"
)


async def _fetch_jwks() -> list[dict]:
    if JWKS_CACHE.get("keys"):
        return JWKS_CACHE["keys"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(JWKS_URL)
        resp.raise_for_status()
        data = resp.json()
        JWKS_CACHE["keys"] = data.get("keys", [])
    return JWKS_CACHE["keys"]


def _get_public_key(kid: str, keys: list[dict]) -> Optional[str]:
    for key in keys:
        if key.get("kid") == kid:
            from cryptography.hazmat.primitives import serialization
            from jwt.algorithms import RSAAlgorithm
            return RSAAlgorithm.from_jwk(json.dumps(key))
    return None


class EntraJWTAuthMiddleware(BaseHTTPMiddleware):
    """Validates Bearer tokens against Entra ID JWKS endpoint.

    Skips validation for docs, health, and root endpoints.
    """

    async def dispatch(self, request: Request, call_next):
        if _should_skip(request):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header.removeprefix("Bearer ").strip()
        try:
            unverified_header = jwt.get_unverified_header(token)
            keys = await _fetch_jwks()
            public_key = _get_public_key(unverified_header.get("kid", ""), keys)
            if not public_key:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Unable to find signing key"},
                    headers={"WWW-Authenticate": "Bearer error='invalid_token'"},
                )

            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256", "RS384", "RS512"],
                audience=settings.entra_jwt.audience,
                issuer=settings.entra_jwt.issuer,
                options={"verify_exp": True},
            )
            request.state.user = payload.get("preferred_username", payload.get("sub", "unknown"))
            request.state.token_roles = payload.get("roles", [])

        except jwt.ExpiredSignatureError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token has expired"},
                headers={"WWW-Authenticate": "Bearer error='invalid_token' error_description='token_expired'"},
            )
        except jwt.InvalidTokenError as exc:
            return JSONResponse(
                status_code=401,
                content={"detail": f"Invalid token: {exc}"},
                headers={"WWW-Authenticate": "Bearer error='invalid_token'"},
            )
        except Exception as exc:
            logger.warning("JWT validation error: %s", exc)
            return JSONResponse(
                status_code=401,
                content={"detail": "Token validation failed"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)


def _should_skip(request: Request) -> bool:
    path = request.url.path
    skip_prefixes = ("/docs", "/redoc", "/openapi.json", "/api/v1/health")
    return any(path.startswith(p) for p in skip_prefixes)
