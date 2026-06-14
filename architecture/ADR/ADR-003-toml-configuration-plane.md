# ADR-003: TOML as Configuration Plane

**Status:** Accepted  
**Date:** 2026-06-14  
**Authors:** Platform Architecture Team  
**Deciders:** Platform Architecture, Agent Engineering  

---

## Context

Magenta SOA requires a human-readable, machine-validatable configuration format for service definitions, cloud provider metadata, agent routing rules, FinOps thresholds, and multi-cloud topology. The configuration plane must be:

- **Human-editable**: operators and engineers edit configs directly in PRs.
- **Schema-validatable**: invalid configs must be caught at CI time, not runtime.
- **Multi-file**: separate concerns (providers vs agents vs FinOps vs system).
- **Programmatically consumable**: consumed by Python (agent-ops), Go (mcp-bridge), and Terraform modules.

Three formats were evaluated: TOML, YAML, and HCL. A hybrid approach (TOML + JSON Schema overlay) emerged as the preferred solution.

---

## Decision

Use **TOML as the primary configuration format**, validated against **JSON Schema** files.

**File layout:**
```
soa/config/
├── system.toml        # System-wide settings (domain, ports, auth)
├── providers.toml      # Cloud provider registry (azure, aws, gcp, vsphere, edge)
├── agents.toml         # Agent definitions and MCP bindings
├── finops.toml         # Budget rules, right-sizing thresholds, tag policy
├── multicloud.toml     # Topology, workload placement, failover, cost allocation
└── schemas/
    ├── system.schema.json
    ├── providers.schema.json
    ├── agents.schema.json
    ├── finops.schema.json
    └── multicloud.schema.json
```

**Why TOML over YAML:**
- TOML is stricter (no implicit typing, no `true`/`True`/`YES` ambiguity).
- TOML maps cleanly to Python dicts via `tomli` (stdlib in 3.11+).
- TOML's `[[array]]` syntax is clearer for provider lists than YAML's `- ` bullets.
- No YAML footguns (anchors, aliases, multi-document files).

**Why JSON Schema for validation:**
- Mature ecosystem (`jsonschema` Python library, CI tooling).
- Schema files are themselves validated (`schema.schema.json`).
- Allows `enum`, `pattern`, `minimum`/`maximum` constraints that TOML alone cannot express.
- Referenced by the `config_validate` MCP tool in agent-ops.

---

## Consequences

### Positive
- Config files are clean and readable — operators can edit them without schema knowledge.
- Validation catches: missing fields, wrong types, invalid enums, out-of-range values.
- Schema files serve as living documentation of the config structure.
- Python, Go, and TypeScript consumers all parse TOML natively.

### Negative
- Two formats to maintain (TOML + JSON Schema) — they can drift.
- TOML lacks native `null` — must use empty string or sentinel values for optional fields.
- Nested data structures are more verbose in TOML than YAML.

### Risks
- Schema drift — mitigated by CI gate that runs `config_validate` on every config PR.
- Large TOML files can become unwieldy — mitigated by the split-file strategy (5 files, max ~100 lines each).

---

## Compliance

Enforced by:
- **JSON Schema files**: `soa/config/schemas/*.schema.json` — validated by agent-ops `config_validate` tool.
- **CI workflow**: `terraform-ci.yml` runs `config_validate` on PRs touching `soa/config/`.
- **Agent Ops handler**: `magenta/agent_ops/config.py` — `config_analyze()` checks syntax + schema + security + best-practice.
- **Secret scanning**: `config_analyze` detects 5 regex patterns (`AKIA*`, `-----BEGIN`, `ghp_`, etc.) in config files.

---

## Notes

- Terraform HCL files (`*.tf`) are NOT converted to TOML — HCL is the correct format for IaC.
- The schema registry is file-path-based: `config_validate(file="providers.toml")` auto-discovers `schemas/providers.schema.json`.
