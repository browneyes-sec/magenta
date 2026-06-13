# Webhooks API

## Overview

Webhooks are the primary mechanism for SIEM-to-Magenta alert ingestion. Each webhook source transforms the SIEM-specific payload into a Magenta mission.

## `POST /webhooks/{source}`

| Source | Handler | Code Location |
|---|---|---|
| `sentinel` | Microsoft Sentinel incident webhook | `webhooks/sentinel.py` |
| `splunk` | Splunk alert webhook | `webhooks/splunk.py` |
| `generic` | Generic JSON webhook | `webhooks/generic.py` |

All webhooks return:

```json
{
  "status": "received",
  "source": "sentinel",
  "mission_id": "550e8400-e29b-41d4-a716-446655440000",
  "alert_id": "incident-8932"
}
```

### Sentinel Webhook

```json
{
  "Incident": {
    "IncidentNumber": "8932",
    "Title": "Suspicious sign-in from unusual location",
    "Severity": "High",
    "SystemAlertId": "sentinel-incident-8932",
    "Products": ["Azure Sentinel"],
    "Tactics": ["InitialAccess", "CredentialAccess"]
  }
}
```

### Splunk Webhook

```json
{
  "search_name": "Failed Logins - Critical Threshold",
  "result": {
    "id": "splunk-alert-456",
    "severity": "critical",
    "src_ip": "10.0.1.100",
    "user": "jdoe",
    "failure_count": 150
  }
}
```

### Generic Webhook

```json
{
  "alert_id": "custom-alert-789",
  "source": "custom-siem",
  "description": "Unusual outbound traffic detected",
  "severity": "medium",
  "payload": { ... }
}
```

## `GET /webhooks/{source}/health`

Health check per webhook source:

```json
{
  "source": "sentinel",
  "status": "healthy",
  "active": true
}
```

## Configuration

```yaml
webhooks:
  sentinel:
    enabled: true
    secret: "${SENTINEL_WEBHOOK_SECRET}"  # optional HMAC verification
  splunk:
    enabled: true
    secret: "${SPLUNK_WEBHOOK_SECRET}"
  generic:
    enabled: true
```

## Error Codes

| Code | Meaning |
|---|---|
| 404 | Unknown webhook source |
| 400 | Malformed payload |
| 500 | Internal handler error |
