# Playbooks API

## `GET /api/v1/playbooks`

List registered playbooks.

| Query Param | Type | Default | Description |
|---|---|---|---|
| `tag` | string | — | Filter by tag |

```json
[
  {
    "name": "ransomware-response",
    "version": "2.1.0",
    "tags": ["ransomware", "critical"],
    "stages": 5,
    "updated_at": "2026-06-01T12:00:00+00:00"
  }
]
```

## `GET /api/v1/playbooks/{name}`

Get playbook details.

| Query Param | Type | Default | Description |
|---|---|---|---|
| `version` | string | latest | Semantic version |

Returns full playbook object including `trigger`, `orchestration`, `stages`, and `governance` sections.

## `POST /api/v1/playbooks/validate`

Validate a playbook configuration without registering it.

```json
{
  "name": "phishing-response",
  "stages": [
    {"name": "triage", "assignee": "triage_agent", "timeout": 120},
    {"name": "contain", "assignee": "contain_agent", "timeout": 60}
  ]
}
```

```json
{
  "valid": true,
  "errors": []
}
```

## `POST /api/v1/playbooks/`

Register a new playbook.

```json
{
  "name": "phishing-response",
  "description": "Standard phishing incident response",
  "version": "1.0.0",
  "trigger": {
    "type": "webhook",
    "source": "sentinel",
    "conditions": {"severity": {"gte": 3}}
  },
  "stages": [...],
  "tags": ["phishing", "standard"]
}
```

Response:

```json
{
  "status": "registered",
  "name": "phishing-response",
  "version": "1.0.0"
}
```

## Error Codes

| Code | Meaning |
|---|---|
| 400 | Invalid playbook schema |
| 404 | Playbook not found |
| 409 | Playbook version already registered |
