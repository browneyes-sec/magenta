# SIEM Integration Architecture & Sizing

## Component Overview

Magenta integrates with SIEM platforms at two points:

1. **Alert Ingestion** — receive alerts via webhooks or Event Hubs to trigger missions
2. **Registry Feedback** — write automation activity back to SIEM custom tables for unified investigation

Supported SIEMs:

| SIEM | Ingestion | Feedback | Connector Code |
|---|---|---|---|
| Microsoft Sentinel | Webhook + Event Hubs | Custom Logs API | `webhooks/sentinel.py`, `integration/sentinel.py` |
| Splunk Enterprise | Webhook (Alert Manager) | HEC (HTTP Event Collector) | `webhooks/splunk.py`, `integration/splunk.py` |
| Generic | Webhook (JSON) | None (custom) | `webhooks/generic.py` |

## Alert Pipeline

```
Sentinel Incident ──► Webhook ──► Magenta API ──► Mission Created
     or                          POST /webhooks/sentinel
Splunk Alert ──────► Webhook ──► Magenta API ──► Mission Created
                         POST /webhooks/splunk
     or
Event Hubs ────────► Consumer ──► Magenta API ──► Mission Created
(raw-alerts topic)
```

## Microsoft Sentinel Integration

### Webhook Handler

Endpoint: `POST /webhooks/sentinel`

```python
# From magenta/webhooks/sentinel.py
async def handle_incident(payload: dict) -> dict:
    incident = payload.get("Incident", {})
    alert_id = incident.get("IncidentNumber", "unknown")
    mission = mission_manager.create(
        alert_id=alert_id,
        source_system="sentinel",
        description=incident.get("Title", f"Sentinel incident {alert_id}"),
    )
    # Severity mapping: Critical=5, High=4, Medium=3, Low=2
    return {"mission_id": mission.mission_id, "status": "mission_created"}
```

### Log Ingestion API (Feedback)

```python
# From magenta/integration/sentinel.py (conceptual)
class SentinelClient:
    async def publish_activity(self, activity: AutomationActivity):
        # POST to Sentinel's Log Ingestion API
        # Data -> DCR (Data Collection Rule) -> Custom Log Table
        endpoint = f"https://{workspace_id}.ingest.monitor.azure.com/..."
        body = self._to_cedr_format(activity)  # Common Event Data Format
        await self._http.post(endpoint, data=body, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })
```

### Custom Table Schema

```kql
// Sentinel custom log table: MagentaActivity_CL
| where TimeGenerated > ago(7d)
| where CorrelationId_g == "550e8400-e29b-41d4-a716-446655440000"
| project TimeGenerated, Action_s, Status_s, AgentId_s, RiskScore_d
```

## Splunk Integration

### Webhook Handler

Endpoint: `POST /webhooks/splunk`

```python
# From magenta/webhooks/splunk.py
async def handle_alert(payload: dict) -> dict:
    search_name = payload.get("search_name", "unknown")
    results = payload.get("result", {})
    alert_id = results.get("id", f"splunk-{search_name}")
    mission = mission_manager.create(
        alert_id=alert_id,
        source_system="splunk",
        description=f"Splunk alert: {search_name}",
    )
    mission.severity = severity_map.get(results.get("severity", "medium"), 3)
    return {"mission_id": mission.mission_id, "status": "mission_created"}
```

### HEC Feedback

```python
# From magenta/integration/splunk.py (conceptual)
class SplunkClient:
    async def publish_activity(self, activity: AutomationActivity):
        # POST to Splunk HEC
        event = {
            "time": activity.started_at.timestamp(),
            "host": "magenta",
            "source": "magenta:automation",
            "sourcetype": "_json",
            "event": activity.model_dump(),
        }
        await self._http.post(
            "https://splunk-hec:8088/services/collector",
            json=event,
            headers={"Authorization": f"Splunk {self.hec_token}"},
        )
```

## Event Hubs as Message Bus

```yaml
eventhub:
  connection_string: "${EVENTHUB_CONNECTION_STRING}"
  namespace: magenta-agent-bus
  topics:
    raw_alerts: raw-alerts
    enriched_alerts: enriched-alerts
    actions: actions
    audit: audit
```

Topics are Kafka-compatible (Event Hubs with Kafka endpoint):

| Topic | Producer | Consumer(s) | Schema |
|---|---|---|---|
| `raw-alerts` | Sentinel / Splunk connector | Swarm Manager | Alert event envelope |
| `enriched-alerts` | Triage Agent, Enrich Agent | Contain Agent, Investigate Agent | Alert + enrichment context |
| `actions` | Any action-taking agent | Action Executor, Registry | Action request + status |
| `audit` | Registry Agent | Sentinel Custom Logs, Elasticsearch | `AutomationActivity` event |

## Sizing

| SIEM | Alert Volume | Webhook Payload | Processing Latency |
|---|---|---|---|
| Sentinel | Up to 200/min (Tier 1) | ~10-50 KB | < 1 s |
| Splunk | Up to 100/min | ~5-20 KB | < 1 s |
| Event Hubs | Up to 1000/min | ~1-50 KB | < 100 ms |

## Monitoring

| Metric | Alert |
|---|---|
| Webhook failure rate > 1% | Warning |
| Webhook latency p99 > 3 s | Warning |
| Event Hubs consumer lag > 1000 | Critical |
| Sentinel Log Ingestion quota > 80% | Warning |
| HEC acknowledgment failures > 1% | Warning |
