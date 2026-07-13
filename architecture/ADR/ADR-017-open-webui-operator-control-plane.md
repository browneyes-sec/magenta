# ADR-017: Open WebUI as Operator Control Plane

**Status:** Accepted  
**Date:** 2026-06-19  
**Authors:** Platform Architecture Team  
**Deciders:** Platform Architecture, Agent Engineering, Security  

---

## Context

Magenta ASOAR requires an operator GUI for mission orchestration, agent deployment, approval gates, and artifact visualization. The platform operates as an agentic SOAR with:

- Dictator super-agent framework (directives, policies, oversight)
- MCP-based service integration (9 registered services)
- LLM gateway with sensitivity-based routing (ADR-002, ADR-014)
- Vectorized data mesh with episodic/semantic/procedural memory (ADR-010)

Evaluated options:

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Custom Next.js/React** | Full control, custom UX | 8-12 weeks dev, maintenance burden | Rejected |
| **Chainlit** | Python-native, LLM integration | Limited pipeline ecosystem, no Docker image | Rejected |
| **Gradio** | ML-focused, fast prototyping | Limited operator UX, no chat history | Rejected |
| **Open WebUI** | Docker-native, pipeline ecosystem, OLLAMA integration, chat UX, zero custom frontend | Filter/pipe type confusion, pipeline server quirks, no native RBAC | **Selected** |

---

## Decision

Use **Open WebUI** as the operator control plane, integrated via:

1. **LangChain pipelines** (HTTP transport) — 3 pipelines exposing 20 tools via Magenta API
2. **MCPO proxy** — MCP servers exposed via HTTP for direct tool access
3. **OLLAMA** — Local LLM inference (qwen2.5:1.5b + nomic-embed-text)

**Architecture:**

```
Open WebUI (port 3000)
    │
    ├──→ Pipelines (port 9099) ──→ magenta-api:8000 ──→ MCP Bridge ──→ MCP Servers
    │       └─ Dictator Pipeline (13 tools)
    │       └─ Approval Card (1 tool, HTML cards)
    │       └─ Artifact Generator (6 tools, HTML dashboards)
    │
    ├──→ MCPO (port 8001) ──→ magenta-api:8000/mcp/* ──→ Registry, Artifacts
    │
    └──→ OLLAMA (port 11434) ──→ LLM inference + embeddings
```

**Governance:** Open WebUI **never bypasses** Magenta SOA or data mesh. All access routes through governed gateway endpoints (`magenta-api:8000`, `mcp-bridge`).

---

## Consequences

### Positive

- Zero custom frontend development (8-12 weeks saved)
- Native pipeline ecosystem with Valves configuration
- OLLAMA integration for local LLM inference (no API keys)
- Chat-based operator UX familiar to SOC analysts
- Pipeline tools map 1:1 to Dictator directives and MCP tools
- HTML artifact cards render natively in chat

### Negative

- Pipeline type confusion (filter vs pipe) — resolved by removing `inlet`/`outlet` methods
- Pipeline server `get_all_pipelines()` only handles `manifold` and `filter` types; `pipe` type falls to untyped branch
- No native RBAC — mitigated by API key enforcement at Magenta API layer
- Single-process pipeline server — no HA in MVS; production uses Core overlay with replicas

### Risks

- Upstream breaking changes in `ghcr.io/open-webui/pipelines:main`
- Pipeline server quirks (chat/completions rejects filter types by design)
- MVS memory budget: +256 MB for magenta-api in MVS stack

---

## Compliance

| ADR | Alignment |
|-----|-----------|
| ADR-002 (MCP) | Pipelines call magenta-api `/mcp/*` endpoints; MCPO proxies MCP servers via HTTP |
| ADR-015 (MVS) | MVS stack includes API (+256 MB) for pipeline→API connectivity |
| ADR-016 (Golden Images) | Pipeline container uses upstream image; API uses distroless base |
| ADR-014 (Mesh/Memory) | Pipelines query mesh via `/api/v1/mesh/*`; embeddings via OLLAMA `nomic-embed-text` |

**Pipeline implementation:**
- Pure HTTP clients (httpx) — zero `magenta.*` imports
- Valves configuration via `valve_override.json`
- Version tracking via `soa/instrumentation/version.json`

---

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Custom Next.js app | 8-12 weeks dev time; duplicate chat UX |
| Chainlit | No Docker ecosystem; no pipeline support |
| Gradio | ML-demo focused; not operator-grade |
| Direct API + custom UI | Rebuilds Open WebUI features |

---

## References

- `soa/docker/docker-compose.mvs.yml` — MVS stack with API, Pipelines, Open WebUI
- `soa/docker/pipelines/` — 3 pipeline modules (HTTP clients)
- `soa/docker/mcpo-config.mvs.json` — MCPO HTTP transport config
- `magenta/api/routes/mcp.py` — MCP bridge endpoints
- `soa/instrumentation/version.json` — Pipeline version tracking
- `soa/docker/valve_override.json` — Pipeline Valves config