# WebSocket / Real-Time Events

## Overview

Magenta exposes a WebSocket endpoint for real-time mission progress, agent activity, and approval requests. This enables live-updating dashboards, CLI streaming, and notification integration.

## Endpoint

```
WebSocket: wss://magenta.example.com/ws/{client_id}
```

| Parameter | Description |
|---|---|
| `client_id` | Unique client identifier (e.g., `dashboard-1`, `cli-session-john`) |

## Authentication

The WebSocket handshake authenticates via the query parameter `token`:

```
wss://magenta.example.com/ws/dashboard-1?token=eyJhbGciOi...
```

## Event Types

```json
{
  "event": "mission_update",
  "mission_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "executing",
  "timestamp": "2026-06-13T14:30:00Z",
  "data": {
    "tasks_completed": 3,
    "tasks_total": 7,
    "current_agent": "triage_agent"
  }
}
```

| Event | Description | Payload |
|---|---|---|
| `mission_update` | Mission status changed | `status`, `tasks_completed`, `tasks_total` |
| `agent_action` | Agent performed an action | `agent_id`, `action`, `target`, `status` |
| `approval_request` | Human approval needed | `correlation_id`, `agent_id`, `risk_score`, `action` |
| `approval_response` | Human responded to request | `correlation_id`, `approved`, `reason` |
| `log_line` | Agent log line | `agent_id`, `level`, `message` |
| `heartbeat` | Server alive | Nothing |
| `error` | Error during mission | `code`, `message`, `mission_id` |

## Implementation

```python
from fastapi import WebSocket, WebSocketDisconnect

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)

    async def broadcast(self, event: dict):
        for client_id, ws in self.active_connections.items():
            try:
                await ws.send_json(event)
            except Exception:
                self.disconnect(client_id)

manager = ConnectionManager()
```

## Production Considerations

| Concern | Solution |
|---|---|
| Scaling | Redis Pub/Sub — all API servers subscribe to same channel |
| Session persistence | Redis-backed session store |
| Reconnection | Client sends last seen `event_id`, server replays missed events |
| Heartbeat | Server sends `heartbeat` every 30s, client responds with `pong` |
| Authentication | Validate token on connect, reject if invalid |
| Rate limiting | Max 10 messages/sec per client |
