# Rate Limiting

## Overview

Magenta implements rate limiting via middleware (`magenta/api/middleware.py`) to protect the API from abuse and ensure fair resource allocation.

Current implementation is **in-memory** (single-process). For production, replace with **Redis-based** distributed rate limiting.

## Default Limits

| Endpoint Group | Requests per Minute | Burst |
|---|---|---|
| `GET /api/v1/health/*` | 60 | 10 |
| `GET /api/v1/agents/*` | 60 | 10 |
| `GET /api/v1/missions/*` | 30 | 5 |
| `POST /api/v1/missions/*` | 10 | 3 |
| `POST /api/v1/agents/register` | 5 | 2 |
| `POST /webhooks/*` | 30 | 10 |
| `GET /api/v1/search/*` | 20 | 5 |

## Current Implementation

```python
# From magenta/api/middleware.py
class RateLimiter:
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
```

## Production (Redis) Implementation Guide

```python
import aioredis

class RedisRateLimiter:
    def __init__(self, redis_client, prefix="ratelimit"):
        self._redis = redis_client
        self._prefix = prefix

    async def check(self, key: str, max_requests: int = 100, window_seconds: int = 60) -> bool:
        redis_key = f"{self._prefix}:{key}"
        current = await self._redis.incr(redis_key)
        if current == 1:
            await self._redis.expire(redis_key, window_seconds)
        return current <= max_requests
```

## Response Headers

Rate-limited requests return:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 45
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1623456789
```

```json
{
  "detail": "Rate limit exceeded. Retry after 45 seconds."
}
```

## Per-Client Rate Limiting

Rate limit key is derived from:

```python
def get_rate_limit_key(request: Request) -> str:
    # Use API key or JWT sub, fall back to IP
    auth = request.headers.get("Authorization", "")
    if auth.startswith("ApiKey "):
        return f"apikey:{auth[7:]}"
    if auth.startswith("Bearer "):
        # Decode JWT to extract sub
        token = auth[7:]
        payload = jwt.decode(token, options={"verify_signature": False})
        return f"user:{payload.get('sub', 'unknown')}"
    return f"ip:{request.client.host}"
```

## Configuration

```yaml
rate_limiting:
  backend: redis
  default_limits:
    missions:
      read: "30/minute"
      write: "10/minute"
    agents:
      read: "60/minute"
      write: "5/minute"
    webhooks: "30/minute"
    search: "20/minute"
    health: "60/minute"
```
