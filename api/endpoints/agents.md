# Agents API

## `GET /api/v1/agents`

List all registered agents.

```json
[
  {
    "agent_id": "triage-01",
    "role": "triage_agent",
    "status": "ready",
    "model": "ollama/qwen2.5:7b"
  }
]
```

## `GET /api/v1/agents/{agent_id}`

Get agent details.

```json
{
  "agent_id": "triage-01",
  "role": "triage_agent",
  "status": "ready",
  "config": {
    "agent_id": "triage-01",
    "role": "triage_agent",
    "model_provider": "ollama",
    "model_name": "qwen2.5:7b",
    "tools": ["sentinel_query", "registry_write"],
    "risk_tolerance": 0.6,
    "escalation_threshold": 0.8
  }
}
```

## `GET /api/v1/agents/roles/{role}`

Get agents by role (e.g., `triage_agent`, `contain_agent`, `swarm_manager`).

```json
[
  {
    "agent_id": "triage-01",
    "status": "ready",
    "load": 3
  }
]
```

## `POST /api/v1/agents/register`

Register a new agent.

```json
{
  "agent_id": "custom-01",
  "role": "investigate_agent",
  "model_provider": "ollama",
  "model_name": "qwen2.5:32b",
  "tools": ["sentinel_query", "registry_write", "threat_intel"],
  "risk_tolerance": 0.5,
  "escalation_threshold": 0.7,
  "max_concurrent_tasks": 3
}
```

Response:

```json
{
  "status": "registered",
  "agent_id": "custom-01"
}
```

## Error Codes

| Code | Meaning |
|---|---|
| 404 | Agent not found |
| 409 | Agent ID already registered |
| 422 | Validation error (invalid role, missing fields) |
