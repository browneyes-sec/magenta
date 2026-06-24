# ADR-002: MCP as Service Integration Protocol

**Status:** Accepted  
**Date:** 2026-06-14  
**Authors:** Platform Architecture Team  
**Deciders:** Platform Architecture, Agent Engineering  

---

## Context

Magenta SOA must connect AI agents (swarm-managed) to backend services: configuration analysis, IaC execution, multi-cloud provisioning, FinOps analytics, SIEM query, and identity management. Three integration patterns were evaluated:

1. **Direct API calls** — agents call REST/gRPC endpoints directly.
2. **Message queue** — agents publish to Kafka/RabbitMQ, services consume.
3. **MCP (Model Context Protocol)** — agents discover and invoke tools through a protocol bridge.

Key requirements: dynamic discovery (agents shouldn't hardcode endpoints), consistent auth/mTLS across all services, tool-level granularity (not service-level), and streaming support for long-running operations (e.g., `iac_plan`, `cloud_provision`).

---

## Decision

Use **MCP (Model Context Protocol)** as the universal service integration protocol, with the **MCP Bridge** (`mcp-bridge`) as the central gateway.

**Architecture:**
```
Agent → mcp-bridge (port 8080) → mcp-agent-ops (gRPC 50060)
                                → mcp-orchestrator (gRPC 50061)
                                → mcp-finops (HTTP 50062)
                                → mcp-web (HTTP 8081)
                                → mcp-sentinel (gRPC 50051)
                                → ...
```

**Key implementation details:**
- **Service catalog** (`soa/services/catalog.toml`): single source of truth for all MCP services, their transports, ports, and tool lists.
- **MCP protocol version**: pinned to `2025-03-26` across all service TOML files.
- **Transport**: gRPC for long-running/internal services, HTTP for lightweight query services.
- **Auth**: mTLS for gRPC services, JWT for HTTP services, validated by the MCP Bridge.
- **Tool registry**: each service defines its tools in its TOML file with JSON Schema input/output definitions.

---

## Consequences

### Positive
- Agents discover services at runtime via `mcp-bridge:/mcp/discover` — zero hardcoded endpoints.
- Unified auth/rate-limiting/observability at the bridge layer.
- Adding a new capability = writing a service TOML + implementing the handler — no agent changes.
- Protocol is LLM-native (designed by Anthropic for agent-tool interaction).

### Negative
- Latency overhead of one extra hop through the bridge (sub-millisecond in practice).
- Bridge becomes a single point of failure (mitigated by 2+ replicas in staging/production).
- Protocol is relatively new (2025) — ecosystem tools are evolving.

### Risks
- MCP protocol version `2025-03-26` may become stale — mitigated by pinning versions per-service and planning quarterly upgrades.
- Bridge throughput under high agent concurrency — mitigated by horizontal scaling and rate limiting (100 req/s per agent).

---

## Compliance

Enforced by:
- **Service catalog**: `soa/services/catalog.toml` — every service is registered here.
- **Service TOMLs**: each `soa/services/*.toml` declares `mcp.protocol_version = "2025-03-26"`.
- **K8s manifests**: all MCP services expose the standard metrics port (9090) and health endpoint (`/mcp/{service}/health`).
- **MCP Bridge Deployment**: `soa/kubernetes/mcp-services/mcp-bridge.yaml` with mTLS volume mounts.

---

## Notes

- The MCP Bridge is the **only** entry point for agents. Direct service access is blocked by network policy.
- Non-MCP services (e.g., databases, blob storage) are accessed through `mcp-data-mesh` or `mcp-web` as proxies.
