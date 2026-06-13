# Missions API

## `GET /api/v1/missions`

List missions, optionally filtered by status.

| Query Param | Type | Default | Description |
|---|---|---|---|
| `status` | string | — | Filter: `created`, `executing`, `completed`, `failed`, etc. |
| `limit` | int | 50 | Max results |

```json
[
  {
    "mission_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "executing",
    "alert_id": "sentinel-incident-8932",
    "severity": 4,
    "tasks": 7,
    "team_size": 3,
    "created_at": "2026-06-13T14:00:00+00:00"
  }
]
```

## `GET /api/v1/missions/{mission_id}`

Get full mission details.

```json
{
  "mission_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "alert_id": "sentinel-incident-8932",
  "source_system": "sentinel",
  "severity": 4,
  "risk_score": 65,
  "description": "Suspicious login from unusual location",
  "team": [...],
  "tasks": [...],
  "created_at": "2026-06-13T14:00:00+00:00",
  "completed_at": "2026-06-13T14:12:30+00:00"
}
```

## `POST /api/v1/missions/`

Create a new mission.

| Query Param | Type | Default | Description |
|---|---|---|---|
| `alert_id` | string | — | Source alert identifier |
| `source` | string | `sentinel` | Source system (`sentinel`, `splunk`, `generic`) |
| `description` | string | — | Human-readable description |

Response: Full mission object (`201 Created`).

## `POST /api/v1/missions/{mission_id}/start`

Start mission execution. The orchestration engine assigns agents and begins task processing.

## `POST /api/v1/missions/{mission_id}/stop`

Stop a running mission. In-flight tasks are cancelled, compensating actions are triggered.

## `GET /api/v1/missions/{mission_id}/logs`

Get mission execution logs.

| Query Param | Type | Default | Description |
|---|---|---|---|
| `tail` | int | 100 | Number of recent log lines |

```json
{
  "mission_id": "550e8400-e29b-41d4-a716-446655440000",
  "logs": [
    {"timestamp": "...", "level": "INFO", "message": "Mission created"},
    {"timestamp": "...", "level": "INFO", "message": "Triage agent assigned"}
  ]
}
```

## Error Codes

| Code | Meaning |
|---|---|
| 400 | Invalid status transition, mission not startable |
| 404 | Mission not found |
| 409 | Mission already running |
