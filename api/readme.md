# Magenta REST API

The Magenta API provides programmatic access to the ASOAR framework over HTTP. It is built on **FastAPI** with auto-generated OpenAPI documentation.

## Base URL

| Environment | URL |
|---|---|
| Development | `http://localhost:8000` |
| Production | `https://magenta.{domain}` |

All endpoints are prefixed with `/api/v1/`.

## Interactive Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Quick Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/agents` | List all registered agents |
| `GET` | `/api/v1/agents/{agent_id}` | Get agent details |
| `GET` | `/api/v1/agents/roles/{role}` | Get agents by role |
| `POST` | `/api/v1/agents/register` | Register a new agent |
| `GET` | `/api/v1/missions` | List missions |
| `GET` | `/api/v1/missions/{mission_id}` | Get mission details |
| `POST` | `/api/v1/missions/` | Create a mission |
| `POST` | `/api/v1/missions/{mission_id}/start` | Start mission execution |
| `POST` | `/api/v1/missions/{mission_id}/stop` | Stop mission execution |
| `GET` | `/api/v1/missions/{mission_id}/logs` | Get mission logs |
| `GET` | `/api/v1/playbooks` | List playbooks |
| `GET` | `/api/v1/playbooks/{name}` | Get playbook details |
| `POST` | `/api/v1/playbooks/validate` | Validate a playbook |
| `POST` | `/api/v1/playbooks/` | Register a playbook |
| `GET` | `/api/v1/search` | Cross-registry search |
| `GET` | `/api/v1/search/activity` | Search activity events |
| `GET` | `/api/v1/health` | Full system health |
| `GET` | `/api/v1/health/agents` | Agent health |
| `GET` | `/api/v1/health/models` | Model health |
| `POST` | `/webhooks/{source}` | Receive SIEM webhook alerts |

## API Server

```python
# From magenta/api/server.py
def create_app() -> FastAPI:
    app = FastAPI(title="Magenta ASOAR API", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
    app.include_router(agents.router, prefix="/api/v1/agents")
    app.include_router(missions.router, prefix="/api/v1/missions")
    app.include_router(playbooks.router, prefix="/api/v1/playbooks")
    app.include_router(health.router, prefix="/api/v1/health")
    app.include_router(search.router, prefix="/api/v1/search")
    return app
```

## Standard Headers

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <jwt>` or `ApiKey <key>` |
| `Content-Type` | Yes | `application/json` |
| `X-Request-Id` | No | Idempotency / correlation header |
| `X-Source-System` | No | Override source system for webhooks |

## Error Responses

All errors return JSON:

```json
{
  "detail": "Human-readable error message"
}
```

Common status codes:

| Code | Meaning |
|---|---|
| 200 | Success |
| 400 | Bad request (validation error) |
| 401 | Missing or invalid authentication |
| 403 | Insufficient permissions |
| 404 | Resource not found |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
