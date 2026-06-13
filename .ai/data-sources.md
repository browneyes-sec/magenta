# Data Sources — Magenta AI Layer

**Abstraction layer for SIEM, SOAR, IT, and threat intelligence data connectivity.**

---

## 1. Source Abstraction Pattern

Every data source implements a common interface, allowing agents to query any source identically:

```python
class DataSource(ABC):
    """Abstract base for all Magenta data sources."""

    @abstractmethod
    async def query(self, query: SourceQuery) -> SourceResult: ...

    @abstractmethod
    async def stream(self, query: SourceQuery) -> AsyncIterator[SourceEvent]: ...

    @property
    @abstractmethod
    def capabilities(self) -> list[SourceCapability]: ...

    @property
    @abstractmethod
    def health(self) -> SourceHealth: ...
```

---

## 2. Source Registry

```yaml
data_sources:
  sentinel:
    type: "siem"
    connector: "azure_log_analytics"
    auth: "managed_identity"
    tables:
      - "SecurityIncident"
      - "SecurityAlert"
      - "SecurityAutomationActivity_CL"
    rate_limit: 100_per_minute

  splunk:
    type: "siem"
    connector: "splunk_rest"
    auth: "api_token"  # stored in Key Vault
    endpoints:
      - "/services/search/jobs"
      - "/services/alerts/fired_alerts"

  splunk_soar:
    type: "soar"
    connector: "splunk_soar_rest"
    auth: "api_token"
    endpoints:
      - "/rest/container"
      - "/rest/playbook"
      - "/rest/audit"

  entra_id:
    type: "identity"
    connector: "microsoft_graph"
    auth: "managed_identity"
    scopes:
      - "User.Read.All"
      - "AuditLog.Read.All"

  defender_atp:
    type: "edr"
    connector: "microsoft_graph_security"
    auth: "managed_identity"
    actions:
      - "isolate_host"
      - "run_av_scan"
      - "collect_forensics"

  service_now:
    type: "itsm"
    connector: "servicenow_rest"
    auth: "api_token"
    tables:
      - "incident"
      - "change_request"
      - "cmdb_ci"

  threat_intel:
    type: "ti"
    connectors:
      - name: "virustotal"
        auth: "api_key"
        rate_limit: 4_per_minute
      - name: "shodan"
        auth: "api_key"
      - name: "alienvault_otx"
        auth: "api_key"

  data_lake:
    type: "storage"
    connector: "azure_data_lake_gen2"
    auth: "managed_identity"
    containers:
      - "raw-alerts"
      - "enriched-events"
      - "actions"
      - "audit"
```

---

## 3. Query Pattern

```python
# Agent queries any source uniformly
result = await data_sources.query(
    SourceQuery(
        source="sentinel",
        query_type="kql",
        query="SecurityIncident | where Severity == 'High' | take 10",
        time_range=TimeRange(hours=24)
    )
)

# Or with structured parameters
result = await data_sources.query(
    SourceQuery(
        source="entra_id",
        query_type="graph",
        query="/users/{id}/signinActivity",
        params={"id": user_id}
    )
)
```

---

## 4. Event Streaming

For real-time alert consumption, sources support streaming:

```python
# Stream alerts from Sentinel
async for alert in data_sources.stream(
    SourceQuery(
        source="sentinel",
        query_type="stream",
        query="SecurityAlert | where TimeGenerated > ago(5m)"
    )
):
    await mission_queue.put(alert)
```

---

## 5. Health Monitoring

```python
class DataSourceHealth:
    status: Literal["healthy", "degraded", "down"]
    latency_ms: float
    error_rate: float
    last_success: datetime
    rate_limit_remaining: int
    quota_reset_at: datetime
```

All source health metrics feed into Azure Monitor for alerting.

---

## 6. Data Source Security

| Source | Auth Method | Secret Location | Rotation |
|---|---|---|---|
| Sentinel | Managed Identity | Entra ID (automatic) | Automatic |
| Splunk | API Token | Azure Key Vault | 90 days |
| Entra ID | Managed Identity | Entra ID (automatic) | Automatic |
| Defender ATP | Managed Identity | Entra ID (automatic) | Automatic |
| ServiceNow | API Token | Azure Key Vault | 90 days |
| VirusTotal | API Key | Azure Key Vault | 180 days |
| Data Lake | Managed Identity | Entra ID (automatic) | Automatic |
