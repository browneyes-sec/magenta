# Open WebUI Integration — Architecture

Magenta ASOAR uses **Open WebUI** as its primary operator control plane, backed by **OLLAMA** for local LLM inference and a 10-service Docker stack for full observability.

## Service Topology

```text
                    External Ports
                    ┌──── 3000 ────┐  ┌──── 3001 ────┐
                    │              │  │              │
                    v              │  v              │
┌───────────────────┴──────────┐   ┌─┴───────────────────┐
│      Open WebUI              │   │     Grafana          │
│  (Operator Control Plane)    │   │  (Dashboards)        │
└───────┬──────────────────────┘   └──────────┬───────────┘
        │                                    │
        │         magenta-internal           │
        │         network                    │
        │                                    │
┌───────┴──────────┐   ┌─────────────────────┴──────────┐
│    OLLAMA        │   │      Prometheus                 │
│  (Local LLM)     │   │   (Metrics Store)               │
└──────────────────┘   └────────────────────────────────┘
        │                                                    ┌──────────────────┐
        │                                                    │   OTel Collector │
        ├────────────────────────────────────────────────────┤   (Traces/Metrics)│
        │                                                    └──────────────────┘
┌───────┴──────────┐   ┌──────────────────────┐   ┌──────────────────┐
│    Pipelines     │   │    MCP Orchestrator  │   │   Open Terminal  │
│ (LangChain Pipe) │   │   (MCPO Proxy)       │   │  (CLI in Browser)│
└──────────────────┘   └──────────────────────┘   └──────────────────┘
        │                        │
┌───────┴──────────┐   ┌────────┴───────────┐   ┌──────────────────┐
│     Redis        │   │     InfluxDB       │   │   Elasticsearch  │
│ (State/Cache)    │   │ (Usage Analytics)  │   │   (Registry)     │
└──────────────────┘   └────────────────────┘   └──────────────────┘
```

## Service Roles

| Service | Port | Role |
|---|---|---|
| `magenta-ollama` | 11434 | Local LLM inference (qwen2.5:7b default) |
| `magenta-open-webui` | **3000** | Operator chat interface, artifact rendering |
| `magenta-pipelines` | 9099 | LangChain pipeline tools (15+ Dictator commands) |
| `magenta-mcpo` | 8001 | MCP-to-OpenAPI proxy for 6 MCP servers |
| `magenta-open-terminal` | 8082 | In-browser Dictator CLI |
| `magenta-otel-collector` | 4317/4318 | OTLP traces/metrics collection |
| `magenta-prometheus` | 9090 | Metrics time-series database |
| `magenta-grafana` | **3001** | Operational dashboards (3 dashboards, 25+ panels) |
| `magenta-influxdb` | 8086 | Open WebUI usage analytics |
| `magenta-redis` | 6379 | Mission state, approval queue, LLM cache, idempotency |

## MCP Servers

Six MCP servers are defined in `magenta/mcp/` and routed through MCPO:

| Server | Tools | Backend |
|---|---|---|
| `sentinel_mcp_server` | run_kql_query, get_alert, list_active_alerts, ingest_to_log_analytics | `magenta.integration.sentinel` |
| `entra_mcp_server` | get_user, list_group_members, get_device, search_user | `magenta.integration.entra` |
| `defender_mcp_server` | get_machine, list_machine_alerts, isolate_machine, get_machine_health | `magenta.integration.defender` |
| `datalake_mcp_server` | list_artifacts, get_artifact, save_artifact, delete_artifact | `magenta.data.lake` |
| `registry_mcp_server` | search_missions, get_mission, list_active_missions, get_dictator_status, search_directives, get_agent_summary | `magenta.data.sql`, `magenta.dictator` |
| `artifacts_mcp_server` | generate_directive_timeline, generate_mission_throughput, generate_policy_status, generate_dead_letter | `magenta.dictator.telemetry` |

## Pipelines

Three Open WebUI pipelines in `soa/docker/pipelines/`:

| Pipeline | Tools | Purpose |
|---|---|---|
| `magenta_dictator_langchain_pipeline.py` | 13+ tools | Issue directives, manage policies, deploy agents, check approvals, generate artifacts |
| `magenta_approval_card.py` | 1 (approval_card) | Interactive HTML approval card with Approve/Deny/Alternative buttons |
| `magenta_artifact_generator.py` | 6 artifact types | Generate HTML dashboard artifacts for chat display |

## Approval Gate Flow

```text
High-risk action > 60 risk
        │
        v
  ActionExecutor._request_approval()
        │
        v
  ApprovalRequest created with 15-min TTL
        │
        ├──> Redis key: approval:{correlation_id} (TTL 900s)
        └──> In-memory fallback
        │
        v
  Operator sees card in Open WebUI chat
        │
        ├──> Approve → POST /api/v1/approvals/{id}/respond?decision=approved
        └──> Deny    → POST /api/v1/approvals/{id}/respond?decision=denied
        │
        v
  Action proceeds or is blocked (shadow mode during pilot)
```

## Observability Stack

- **OTel Collector** receives OTLP traces/metrics on ports 4317 (gRPC) and 4318 (HTTP)
- **Prometheus** scrapes OTel Collector (8889), Open WebUI (8080/metrics), and Pipelines (9099/metrics)
- **Grafana** provisions 3 dashboards from `soa/docker/grafana/dashboards/`:
  - `magenta-asoar-ops` — directive rate, dead-letter, connector health, approval queue, mission throughput, LLM budget, cache hit rates, normalization panels
  - `magenta-threat-blue` — threat level, incidents by severity, MTTR, containment success, enrichment latency, model response times
  - `openwebui-usage` — active sessions, model distribution, LLM latency, token throughput, approval rate, error rate
