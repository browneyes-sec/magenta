# Telemetry Collection Framework (TCF)

**Extends:** ADR-011 (Telemetry Collection Plane), ADR-010 (Vectorized Data Mesh)

Each source domain onboarding follows **6 planning gates** that ensure consistent collection, normalization, indexing, and observability.

---

## Gate 1 — Source Discovery & Classification

Identify and classify the log source before any collection mechanism is selected.

| Field | Description | Example |
|---|---|---|
| `source_domain` | Logical domain identifier | `endpoint.windows`, `cloud.azure.activity` |
| `data_class` | Security classification | `security_event`, `audit`, `application`, `infrastructure` |
| `volume_estimate` | Expected events/day and peak EPS | `2M/day, 500 EPS peak` |
| `sensitivity` | Data sensitivity (HIGH → local OLLAMA only, no cloud embedding) | `LOW`, `MEDIUM`, `HIGH` |
| `retention_tier` | Hot/Warm/Cold retention | `hot(ES/7d)`, `warm(mesh/90d)`, `cold(lake/indefinite)` |
| `compliance_scope` | Regulatory scope | `IL5`, `PCI`, `SOC2`, `none` |
| `stakeholder` | Consuming agents or teams | `investigate-agent`, `enrichment-agent` |

**Deliverable:** Source classification record in `soa/config/sources.toml`.

---

## Gate 2 — Collection Mechanism Selection

Select the appropriate collection mechanism based on source OS, network topology, and deployment constraints.

### Windows

| Factor | Primary (AMA) | Fallback (WAC/WinRM-SSL) |
|---|---|---|
| Agent | Azure Monitor Agent | Windows Admin Center gateway |
| Transport | TLS 1.2+ to Azure | HTTPS 443 (WAC) / WinRM 5986 |
| Events | WEF subscription → LA | `Get-WinEvent` export via PowerShell |
| Auth | Managed Identity | Entra ID + RBAC / gMSA |
| Setup | Azure Arc + DCR | WAC gateway install + collector cert |

**RDP is NOT a log transport path** — break-glass human access only. Documented explicitly to avoid security auditor flags.

### Linux

| Factor | Primary (HTTPS) | Fallback (SFTP/FTPS) |
|---|---|---|
| Agent | Fluent Bit / rsyslog with HTTPS output plugin | Log aggregator → SFTP drop |
| Transport | TLS 1.3 POST to `POST /ingest/v1/logs` | SSH (AES-GCM) / TLS 1.2+ |
| Format | NDJSON or syslog over HTTPS | Raw syslog files or NDJSON |
| Auth | mTLS or HMAC-signed body | SSH key (per-collector) |

### Cloud

| Source | Mechanism | Topic |
|---|---|---|
| Azure Monitor / Log Analytics | DCR + DCE or Diagnostic Settings → Event Hubs | `raw-logs` |
| Azure Entra ID (sign-in/audit) | Graph API poller → Event Hubs | `raw-logs` |
| AWS CloudTrail / CloudWatch | EventBridge → Event Hubs (partner) or S3 → HTTPS pull | `raw-logs` |
| GCP Cloud Logging | Pub/Sub → Event Hubs bridge | `raw-logs` |

### Customer arbitrary

| Method | Protocol | Auth | When to use |
|---|---|---|---|
| HTTPS push | `POST /ingest/v1/logs` | mTLS or HMAC | Source can initiate outbound |
| SFTP/FTPS drop | SFTP/FTPS to staging area | SSH key / TLS cert | Air-gapped, no outbound |
| S3 / Azure Blob signed URL | Pre-signed URL pull | Cloud IAM | Cloud-native sources |

---

## Gate 3 — Canonical Schema Mapping

Raw logs normalize to the **`security.event`** schema (separate from `automation.activity` used for alert-driven SOAR actions):

```json
{
  "schema_version": "1.0",
  "event_type": "security.event",
  "event_id": "<uuid>",
  "correlation_id": "<uuid>",
  "idempotency_key": "<sha256(source + timestamp + host + event_id)>",
  "source_system": "windows_event | linux_syslog | cloud.azure | cloud.aws | cloud.gcp | customer.custom",
  "source_host": "<fqdn>",
  "timestamp": "<ISO8601>",
  "severity": "informational | low | medium | high | critical",
  "category": "authentication | network | process | audit | application",
  "raw_ref": "adl://lake/raw-logs/<date>/<event_id>.json",
  "normalized_fields": {
    "ActorUsername": "",
    "TargetIPAddress": "",
    "ProcessName": "",
    "EventID": ""
  },
  "tags": ["env:prod", "bu:finance", "data-class:internal"]
}
```

### Mapping rules

- **Windows Events**: `EventID` + `Provider` → `category`, `Security ID` → `ActorUsername`, `IpAddress` → `TargetIPAddress`
- **Linux Syslog**: `facility` + `severity` → `category`, hostname → `source_host`, message body → copy to `normalized_fields`
- **Cloud logs**: `operationName` → `category`, `callerIpAddress` → `TargetIPAddress`, `identity` → `ActorUsername`

Mappings live alongside existing vendor maps in `architecture/resources/normalization/readme.md`.

---

## Gate 4 — Bus Topic Assignment

Topics on the Security Automation Bus (Azure Event Hubs):

| Topic | Schema | Retention | Producers | Consumers |
|---|---|---|---|---|
| `raw-logs` | Source-native JSON/syslog/CEF | 7 days | Endpoint collectors, cloud connectors, ingest API | Log Normalizer, Capture → Lake |
| `raw-alerts` | Source-native JSON (unchanged) | 7 days | Sentinel/Splunk source agents | Normalizer |
| `enriched-alerts` | `automation.activity` (unchanged) | 1 day | Normalizer | Orchestrator, Registry |
| `enriched-events` | `security.event` (new) | 1 day | Log Normalizer | Vectorizer, Investigate agents |
| `cdc-{source}` | Debezium envelopes | 3 days | External DB sources | Vectorizer |
| `audit` | `automation.activity` | 7 days | Registry, Execution | Registry sink |
| `dead-letter` | Original payload + error | 48 h | Any producer | Debugging, replay |

### Consumer groups (additions)

| Consumer Group | Topic | Agent |
|---|---|---|
| `log-normalizer` | `raw-logs` | Log Normalizer |
| `vectorizer-logs` | `enriched-events` | Vectorization pipeline |
| `investigate` | `enriched-events` | Investigate agents (direct) |

---

## Gate 5 — Data Mesh Product Registration

Registered in mesh catalog (`architecture/data-mesh/readme.md` §3):

| Product ID | Source | Vectorized | Qdrant Collection | Agent use |
|---|---|---|---|---|
| `endpoint.windows.events` | WEF / AMA / WAC | Yes | `endpoint_windows` | Investigate context |
| `endpoint.linux.syslog` | rsyslog / Fluent Bit | Yes | `endpoint_linux` | Investigate context |
| `customer.logs.custom` | SFTP / HTTPS drops | Yes | `customer_custom` | Mission-specific RAG |
| `cloud.azure.activity` | LA / Event Hubs | Yes | `cloud_azure` | Enrichment, compliance |
| `cloud.azure.identity` | Entra ID Graph API | Yes | `cloud_azure_identity` | Identity audit |
| `cloud.aws.activity` | CloudTrail | Yes | `cloud_aws` | Enrichment |
| `cloud.gcp.activity` | Cloud Logging | Yes | `cloud_gcp` | Enrichment |
| `siem.alerts` | Sentinel / Splunk (existing) | Yes | `siem_alerts` | Triage, orchestration |
| `agent.memory.episodic` | Agent runtime (existing) | Yes | `mem-episodic` | Swarm recall |

### Log chunking strategy

| Content Type | Strategy | Chunk Size | Overlap |
|---|---|---|---|
| Windows Event XML | Semantic split on message body | 512 tokens | 64 tokens |
| Linux syslog (single-line) | Line-level | 256 tokens | 0 |
| Linux syslog (multi-line stack trace) | Stack trace grouping | 1024 tokens | 128 tokens |
| Cloud JSON (Azure/AWS/GCP) | Document-level (one activity = one embedding) | N/A | N/A |
| Customer custom (CSV/JSON) | Configurable per-source (TOML defined) | 512 tokens | 64 tokens |

---

## Gate 6 — Security, Compliance & Observability

### Transport security

| Channel | Protocol | Encryption | Auth |
|---|---|---|---|
| HTTPS push | TLS 1.3 | AES-GCM | mTLS or HMAC-SHA256 |
| SFTP | SSH | AES-GCM | SSH key (per-collector) |
| FTPS | TLS 1.2+ | AES | Cert + credential |
| WAC | TLS 1.3 | AES-GCM | Entra ID + RBAC |
| WinRM-SSL | TLS on 5986 | AES | gMSA / hybrid |
| Event Hubs | AMQP / HTTPS | TLS + SAS | Managed Identity |

### PII redaction

Apply `magenta/gateway/redact.py` before vector embedding:
- Usernames, IPs, emails, hostnames
- Phone numbers, credit cards
- API keys, connection strings

Redacted fields are stored in `raw_ref` (raw lake copy) but excluded from vector payloads.

### Observability

| Metric | Alert | Threshold |
|---|---|---|
| Collector down | Critical | > 5 min |
| Ingest throughput drop | Warning | > 20% from baseline |
| Normalization failure rate | Warning | > 2% |
| Dead-letter queue depth | Investigate | > 100 |
| Vectorization lag | Warning | > 60 s |
| TLS cert expiry | Warning | < 30 days |

### Network placement

```
Customer Network         DMZ Collector Zone        Magenta Platform
┌──────────────┐    ┌──────────────────────┐    ┌──────────────────┐
│ Windows Srv  │───▶│ WAC Gateway          │───▶│ Ingest Gateway   │
│ Linux Srv    │───▶│ Fluent Bit Aggregator │───▶│ (TLS, mTLS)     │
│ Cust Logs    │───▶│ SFTP Staging         │───▶│                  │
└──────────────┘    └──────────────────────┘    └────────┬─────────┘
                                                         │
                                                    ┌────▼─────────┐
                                                    │ Event Hubs   │
                                                    │ raw-logs     │
                                                    └────┬─────────┘
                                                         │
                                                    ┌────▼─────────┐
                                                    │ Log Normalizer│
                                                    │ → enriched   │
                                                    └────┬─────────┘
                                                         │
                                                    ┌────▼─────────┐
                                                    │ Mesh Gateway │
                                                    │ (Qdrant)     │
                                                    └──────────────┘
```
