# Connectors Architecture

## Component Overview

Connectors bridge external SIEM and SOAR systems to the Magenta event bus. Each connector is a **Source Agent** that polls or receives alerts and publishes them to `raw-alerts` topic as canonical events.

## Connector Inventory

| Connector | Source | Trigger | Protocol | Auth | Code Location |
|---|---|---|---|---|---|
| Sentinel Source | Microsoft Sentinel | Timer (30 s) + Webhook | REST API (Logs Query API) + Logic App | Entra ID App + MI | `integration/sentinel.py`, `webhooks/sentinel.py` |
| Splunk Source | Splunk Enterprise | Timer (30 s) | REST API (`/services/search/jobs`, `/services/alerts/fired_alerts`) | Bearer token | `integration/splunk.py`, `webhooks/splunk.py` |
| SOAR Audit | Splunk SOAR | Timer (5 min) | REST API (`/rest/audit`) | Bearer token | Planned |
| Generic Webhook | Any SIEM | Webhook POST | HTTP/JSON | API Key or HMAC | `webhooks/generic.py` |

## Microsoft Sentinel Connector

### Architecture

```
┌───────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Sentinel      │────►│ Logic App    │────►│ Event Hubs   │────►│ Normalizer      │
│ Incidents API │     │ (timer/web)  │     │ raw-alerts   │     │ Agent           │
└───────────────┘     └──────────────┘     └──────────────┘     └─────────────────┘
```

### Polling Logic

```python
# From magenta/integration/sentinel.py
class SentinelConnector:
    def __init__(self, workspace_id: str, tenant_id: str, client_id: str):
        self.workspace_id = workspace_id
        self.credential = DefaultAzureCredential()
        self.last_poll = datetime.utcnow() - timedelta(minutes=5)

    async def poll_incidents(self) -> list[dict]:
        query = f"""
        SecurityIncident
        | where properties.createdTimeUtc >= datetime({self.last_poll.isoformat()})
        | order by properties.createdTimeUtc asc
        | take 100
        """
        results = await self._run_kql(query)
        self.last_poll = datetime.utcnow()
        return results

    async def _run_kql(self, query: str) -> list[dict]:
        url = f"https://api.loganalytics.io/v1/workspaces/{self.workspace_id}/query"
        token = await self.credential.get_token("https://api.loganalytics.io/.default")
        resp = await httpx.post(url, json={"query": query}, headers={
            "Authorization": f"Bearer {token.token}",
        })
        return self._parse_kql_results(resp.json())
```

### Webhook Receiver (Push)

Endpoint: `POST /webhooks/sentinel`

Sentinel sends incident webhooks when configured via Logic App or Sentinel's own webhook output. See [Webhooks API](../../api/endpoints/webhooks.md) for payload format.

### Error Handling

| Scenario | Behavior |
|---|---|
| API rate limited | Exponential backoff (1s, 2s, 4s, ... max 60s) |
| API unavailable | Skip poll cycle, log warning, increment `missed_polls` counter |
| Invalid payload | Publish to `dead-letter` with original payload and parse error |
| Auth failure | Disable connector, alert operations |

## Splunk Connector

### Architecture

```
┌───────────────┐     ┌────────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Splunk        │────►│ Source Agent   │────►│ Event Hubs   │────►│ Normalizer      │
│ REST API      │     │ (Azure Func)   │     │ raw-alerts   │     │ Agent           │
└───────────────┘     └────────────────┘     └──────────────┘     └─────────────────┘
```

### Polling Logic

```python
# From magenta/integration/splunk.py
class SplunkConnector:
    def __init__(self, host: str, port: int, token: str):
        self.base_url = f"https://{host}:{port}"
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}"}

    async def poll_fired_alerts(self) -> list[dict]:
        url = f"{self.base_url}/services/alerts/fired_alerts"
        params = {"output_mode": "json", "count": 100, "offset": 0}
        resp = await httpx.get(url, headers=self.headers, params=params, verify=False)
        return resp.json().get("entry", [])

    async def run_saved_search(self, search_name: str) -> list[dict]:
        # POST /services/search/jobs — create search job
        job = await self._create_search_job(f"search savedsearch '{search_name}'")
        # Poll for completion
        while True:
            status = await self._get_job_status(job["sid"])
            if status == "DONE":
                break
            await asyncio.sleep(2)
        # GET results
        return await self._get_job_results(job["sid"])
```

### Splunk HEC (Push)

For real-time alert forwarding, configure Splunk alert actions to POST to `POST /webhooks/splunk`.

### Error Handling

| Scenario | Behavior |
|---|---|
| Splunk REST unavailable | Exponential backoff, retain last successful poll time |
| Token expired | Alert ops, store token in Key Vault with auto-rotation |
| Search job timeout ( > 60s) | Cancel job, log partial results |
| Results truncated | Paginate via `offset` parameter |

## SOAR Audit Connector

```python
class SOARAuditConnector:
    """Pulls audit trail from Splunk SOAR REST API."""

    async def poll_audit(self, since: datetime) -> list[dict]:
        url = f"{self.base_url}/rest/audit"
        params = {
            "start": since.isoformat(),
            "end": datetime.utcnow().isoformat(),
            "page_size": 1000,
        }
        resp = await httpx.get(url, headers=self.headers, params=params)
        return resp.json().get("items", [])
```

## Generic Webhook Connector

```python
# From magenta/webhooks/generic.py
async def handle_webhook(payload: dict) -> dict:
    alert_id = payload.get("alert_id", str(hash(str(payload)) % 100000))
    source = payload.get("source", "generic")
    mission = mission_manager.create(alert_id=str(alert_id), source_system="sentinel",
        description=payload.get("description", f"Generic alert {alert_id}"))
    return {"mission_id": mission.mission_id, "status": "mission_created"}
```

## Endpoint & Cloud Collectors (ADR-011)

New collector types extending the connector inventory for Tier 2 (Cloud) and Tier 3 (Endpoint/Customer):

### Collector Inventory (Additions)

| Collector | Source | Trigger | Protocol | Auth | Code Location |
|---|---|---|---|---|---|
| Azure DCR Collector | Azure Monitor / LA | Diagnostic Settings → Event Hubs | Event Hubs | Managed Identity | `integration/collectors/azure_dcr.py` |
| Entra ID Log Poller | Microsoft Graph API | Timer (5 min) | REST API (`/auditLogs`) | Entra ID App + MI | `integration/collectors/entra_logs.py` |
| AWS CloudTrail Collector | CloudTrail S3 / EventBridge | S3 Event → Event Hubs | S3 + EventBridge | AWS IAM Role | `integration/collectors/aws_cloudtrail.py` |
| GCP Cloud Logging Collector | Cloud Logging | Pub/Sub push → Event Hubs | Pub/Sub + Event Hubs bridge | GCP SA + Workload Identity | `integration/collectors/gcp_logging.py` |
| Linux Fluent Bit Collector | rsyslog / journald | HTTPS POST to ingest API | TLS 1.3 + mTLS | mTLS certificate | `integration/collectors/linux_fluentbit.py` |
| Windows WAC Collector | Windows Event Log | WAC gateway → HTTPS → ingest API | TLS 1.3 + Entra ID | Entra ID + RBAC | `integration/collectors/windows_wac.py` |
| Windows WinRM Collector | Windows Event Log | WinRM over SSL (5986) | TLS + gMSA | gMSA | `integration/collectors/windows_winrm.py` |
| Customer SFTP Collector | Customer file drops | SFTP/FTPS poll → ingest API | SSH / TLS | SSH key / cert | `integration/collectors/customer_sftp.py` |
| Generic HTTPS Ingest | Any source with HTTPS | POST to `POST /ingest/v1/logs` | TLS 1.3 | mTLS or HMAC-SHA256 | `api/routes/ingest.py` |

### Terraform Modules

Collector infrastructure is provisioned via per-provider Terraform modules (per ADR-005):

| Module | Provider | Location |
|---|---|---|
| `collectors/azure-dcr/` | Azure | `soa/terraform/modules/collectors/azure-dcr/` |
| `collectors/aws-cloudtrail/` | AWS | `soa/terraform/modules/collectors/aws-cloudtrail/` |
| `collectors/gcp-logging/` | GCP | `soa/terraform/modules/collectors/gcp-logging/` |
| `collectors/ingest-gateway/` | Multi-cloud | `soa/terraform/modules/collectors/ingest-gateway/` |

### Error Handling (Collectors)

| Scenario | Behavior |
|---|---|
| Source unavailable | Buffer locally on collector, exponential backoff retry, alert if > 5 min |
| Ingest API unreachable | Buffer to local disk (Spillover), replay on recovery |
| Payload too large | Split into 1 MB chunks, publish with `chunk_seq` header |
| Auth failure | Disable collector, alert operations, log to dead-letter |
| TLS cert expiry | Alert 30 days before expiry, auto-renew via ACME / Key Vault |

---

## Connector Health

```python
@router.get("/connectors")
async def connector_health():
    return {
        "sentinel": {"status": "healthy", "last_poll": "...", "missed_polls": 0, "alerts_today": 142},
        "splunk": {"status": "healthy", "last_poll": "...", "missed_polls": 1, "alerts_today": 89},
        "soar_audit": {"status": "degraded", "last_poll": "5m ago", "missed_polls": 3},
        "azure_dcr": {"status": "healthy", "bytes_ingested": 2048576, "eps": 1420},
        "aws_cloudtrail": {"status": "healthy", "bytes_ingested": 894567, "eps": 340},
        "linux_fluentbit": {"status": "healthy", "connected_hosts": 12, "eps": 280},
    }
```

## Monitoring

| Metric | Alert |
|---|---|
| Connector down > 5 min | Critical |
| Missed poll cycles > 3 consecutive | Warning |
| Webhook failure rate > 2% | Warning |
| API rate limit hits > 0 | Warning — adjust poll interval |
| Payload parse error rate > 2% | Investigate schema drift |
| Collector ingest throughput drop > 20% | Warning — source or network issue |
| TLS cert expiry < 30 days | Warning |
| Local collector buffer > 80% | Warning — replay needed |
| Consumer group lag (log-normalizer) > 1000 | Critical |
