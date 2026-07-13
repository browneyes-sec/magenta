# ADR-007: Agent Ops Tool Registry Pattern

**Status:** Accepted  
**Date:** 2026-06-14  
**Authors:** Agent Engineering Team  
**Deciders:** Platform Architecture, Agent Engineering  

---

## Context

Agent Ops (`magenta/agent_ops/`) exposes 14 MCP tools across 4 domains: Configuration Analysis, IaC Management, Multi-Cloud Orchestration, and FinOps. The tools share common requirements:

- Consistent error handling (all errors must be JSON-serializable with `code`, `message`, `details`).
- Configurable provider dispatch (Azure vs AWS vs GCP vs vSphere).
- Graceful degradation when optional dependencies (Prophet, cloud SDKs) are missing.
- All tools must be discoverable via MCP protocol and registered with JSON Schema input/output.

Two patterns were considered: monolithic handler functions per tool, and a registry-based dispatch pattern.

---

## Decision

Implement a **registry-based provider-as-plugin pattern**:

```
server.py                  # Tool registry, gRPC server, health endpoint
config.py                  # Config tools ↔ parsers (TOML/YAML/JSON/HCL) ↔ validators (JSON Schema)
iac.py                     # IaC tools ↔ terraform CLI subprocess
cloud.py                   # Cloud tools ↔ provider SDK dispatch (Azure/AWS/GCP/vSphere)
finops.py                  # FinOps tools ↔ cost APIs (Azure CM/AWS CE) ↔ Prophet forecast
```

**Tool registry design** (`server.py`):
```python
TOOLS = {
    "config_analyze":          {"handler": config_analyze,          "domain": "config"},
    "config_validate":         {"handler": config_validate,         "domain": "config"},
    "config_diff":             {"handler": config_diff,             "domain": "config"},
    "iac_plan":                {"handler": iac_plan,                "domain": "iac"},
    "iac_apply":               {"handler": iac_apply,               "domain": "iac"},
    "iac_drift_detect":        {"handler": iac_drift_detect,        "domain": "iac"},
    "cloud_provision":         {"handler": cloud_provision,         "domain": "cloud"},
    "cloud_discover":          {"handler": cloud_discover_resources,"domain": "cloud"},
    "cloud_migrate":           {"handler": cloud_migrate,           "domain": "cloud"},
    "finops_cost_analysis":    {"handler": finops_cost_analysis,    "domain": "finops"},
    "finops_recommend_rightsize": {"handler": finops_recommend_rightsize, "domain": "finops"},
    "finops_forecast":         {"handler": finops_forecast,         "domain": "finops"},
    "finops_enforce_budget":   {"handler": finops_enforce_budget,   "domain": "finops"},
    "finops_tag_compliance":   {"handler": finops_tag_compliance,   "domain": "finops"},
}
```

**Provider-as-plugin dispatch** (`cloud.py`):
```python
def _get_provider(provider_id: str):
    if provider_id == "azure": return AzureProvider()
    if provider_id == "aws":   return AWSProvider()
    if provider_id == "gcp":   return GCPProvider()
    if provider_id == "vsphere": return VSphereProvider()
    raise ValueError(f"Unknown provider: {provider_id}")
```

**Graceful degradation** (`finops.py`):
```python
try:
    from prophet import Prophet
except ImportError:
    Prophet = None  # finops_forecast returns error message with install hint
```

---

## Consequences

### Positive
- Adding a new tool = adding a function + one registry entry + one gRPC proto RPC — no routing logic changes.
- Adding a new provider = implementing a provider class — no dispatch code changes.
- Optional dependencies don't block service startup — users get clear error messages instead of import errors.
- Each file has a single responsibility — testable in isolation.

### Negative
- Registry is a Python dict, not data-driven — adding a tool requires code change (not just a config change).
- All tools share the same gRPC server process — a crash in one handler takes down all tools.

### Risks
- Handler crashes — mitigated by per-handler try/except that catches all exceptions and returns structured error responses.
- Provider SDK version conflicts — mitigated by pinning SDK versions in `pyproject.toml` and using `uv sync --frozen` in Dockerfile.

---

## Compliance

Enforced by:
- **Implementation**: all 14 tools registered in `TOOLS` dict in `server.py`.
- **Proto definition**: `soa/proto/agent_ops.proto` defines 15 RPCs (14 tools + health).
- **Service TOML**: `soa/services/agent-ops-service.toml` catalogs all 14 tools with input/output schemas.
- **Testing**: each handler function has a corresponding test in `magnet/` (test suite directory).

---

## Notes

- The `AgentOpsServer` class runs on port 50060 (gRPC) with HTTP health check at `/mcp/agent-ops/health`.
- Future: explore dynamic tool loading from a `tools.d/` directory for plugin-like extensibility.
