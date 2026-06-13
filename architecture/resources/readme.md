# Magenta — Architecture Resources

Technical whitepapers and sizing guidelines for every infrastructure layer required to deploy the Magenta ASOAR framework at production grade.

## Index — Infrastructure Layer

| Resource | Path | Focus |
|---|---|---|
| CPU | [cpu/readme.md](cpu/readme.md) | Control plane, agent runtime, API server, worker sizing |
| GPU | [gpu/readme.md](gpu/readme.md) | Local LLM inference, OLLAMA clusters, VRAM allocation |
| Memory | [memory/readme.md](memory/readme.md) | RAM sizing per component, heap config, swap strategy |
| Cache | [cache/readme.md](cache/readme.md) | Redis mission state, response caching, TTL policies |
| Vector | [vector/readme.md](vector/readme.md) | Embedding stores, index types, RAG pipeline sizing |
| Database | [db/readme.md](db/readme.md) | SQL persistence, connection pooling, migration strategy |
| Blob | [blob/readme.md](blob/readme.md) | Data Lake, Parquet/Delta artifacts, retention tiering |
| Elastic | [elastic/readme.md](elastic/readme.md) | Hot registry cluster, index templates, ILM, shard calculus |

## Index — Software Landscape

| Resource | Path | Focus |
|---|---|---|
| Event Hubs | [event-hubs/readme.md](event-hubs/readme.md) | Bus topology, topics, partitions, Capture, Kafka protocol |
| Agent Runtime | [agents-runtime/readme.md](agents-runtime/readme.md) | Azure Functions, Logic Apps, K8s, managed identity, scaling |
| Connectors | [connectors/readme.md](connectors/readme.md) | Sentinel/Splunk/SOAR source agents, polling, webhooks, error handling |
| Normalization | [normalization/readme.md](normalization/readme.md) | ASIM canonical schema, vendor mapping, schema versioning, DLQ |
| SIEM | [siem/readme.md](siem/readme.md) | Sentinel & Splunk integration, pipeline sizing |

## Index — Solution Logic

| Resource | Path | Focus |
|---|---|---|
| Routing Engine | [routing-engine/readme.md](routing-engine/readme.md) | Risk score formula, YAML rules, execution targets, rule priority |
| Idempotency | [idempotency/readme.md](idempotency/readme.md) | Key derivation, check-before-act, Redis/Table Storage backends |
| Approval Gate | [approval-gate/readme.md](approval-gate/readme.md) | Escalation tiers, shadow mode, notification channels, timeout policy |
| Workflows | [workflows/readme.md](workflows/readme.md) | State machines, saga patterns, DAG decomposition |
| Governance Framework | [governance-framework/readme.md](governance-framework/readme.md) | TOGAF ADM mapping, WAF pillars, phase gates, change board |
| Business Units | [business-units/readme.md](business-units/readme.md) | Multi-tenant isolation, row-level security, steward role, onboarding |

## How to Use These Guides

Each resource paper follows the same structure:

1. **Component Overview** — what the layer does in Magenta
2. **Sizing Baseline** — minimum, recommended, and production specs
3. **Configuration Reference** — relevant YAML/CLI/env settings
4. **Scaling Guidance** — vertical vs horizontal, bottleneck analysis
5. **Security & Compliance** — TLS, RBAC, audit considerations
6. **Monitoring** — key metrics, dashboards, alert thresholds
7. **Reference** — links to code, config, and external docs

## Quick Reference — Minimal Production Deployment

| Component | Min Spec | Recommended |
|---|---|---|
| API & Control Plane | 4 CPU, 8 GB RAM | 8 CPU, 16 GB RAM |
| OLLAMA (7B models) | 8 CPU, 12 GB RAM, 6 GB VRAM | 16 CPU, 24 GB RAM, 12 GB VRAM |
| Elasticsearch | 4 CPU, 8 GB RAM, 200 GB SSD | 8 CPU, 16 GB RAM, 1 TB SSD |
| PostgreSQL | 2 CPU, 4 GB RAM | 4 CPU, 8 GB RAM |
| Redis | 1 CPU, 2 GB RAM | 2 CPU, 4 GB RAM |
| Vector Store | 2 CPU, 4 GB RAM | 4 CPU, 8 GB RAM |
| Data Lake | Standard blob storage | Cool tier with lifecycle |
