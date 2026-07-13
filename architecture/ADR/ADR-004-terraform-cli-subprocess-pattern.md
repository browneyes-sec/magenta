# ADR-004: Terraform CLI Subprocess Pattern

**Status:** Accepted  
**Date:** 2026-06-14  
**Authors:** Platform Architecture Team  
**Deciders:** Platform Architecture, Agent Engineering  

---

## Context

Agent Ops (`magenta/agent_ops/iac.py`) must execute Terraform operations — `plan`, `apply`, and drift detection — on behalf of AI agents. Two integration approaches were evaluated:

1. **Python binding** (`python-terraform` or `pyhcl`) — call Terraform through a library.
2. **CLI subprocess** — shell out to the `terraform` binary via `subprocess`.

Key requirements: support `-detailed-exitcode` for drift detection, support `-json` output for plan parsing, work with Terraform 1.8+ features (deferred changes, provider-defined functions), and avoid version lock between Python and Terraform.

---

## Decision

Use **CLI subprocess** (`subprocess.run()`) to invoke the `terraform` binary directly.

**Pattern:**
```python
result = subprocess.run(
    ["terraform", "plan", "-detailed-exitcode", "-json", "-no-color"],
    capture_output=True, text=True, cwd=terraform_dir,
)
# Exit codes: 0 = no changes, 1 = error, 2 = changes detected (drift)
```

**Key design points:**
- **No python-terraform binding**: they lag behind Terraform releases and abstract away exit code semantics.
- **JSON output**: `terraform plan -json` emits machine-readable change logs parsed line-by-line.
- **-detailed-exitcode**: enables drift detection without state comparison logic — Terraform itself tells us if drift exists.
- **Terraform in container**: the binary is bundled in the `Dockerfile.agent-ops` image (multi-stage build from releases.hashicorp.com).
- **Working directory per environment**: Terraform is invoked from `environments/{dev,staging,production}/` with `-var-file` references.

---

## Consequences

### Positive
- Full compatibility with every Terraform version — just update the binary in the Dockerfile.
- Drift detection is free (exit code 2 = drift) with zero custom logic.
- JSON output integrates directly with the `iac_drift_detect` MCP tool response.
- No Python dependency hell — the SDK is the CLI binary.

### Negative
- Binary size: terraform CLI adds ~80MB to the container image.
- No typed Python objects for plan output — must parse JSON strings.
- Error handling is more verbose (must check returncode, stderr, stdout separately).
- Terraform must be installed in the container (already handled in Dockerfile).

### Risks
- Breaking changes in Terraform JSON output format — mitigated by parsing at the `changes`/`resource_changes` top-level keys which are stable across versions.
- Path traversal if `module_path` is user-controlled — mitigated by validating paths against a whitelist of `environments/{dev,staging,production}`.
- Concurrency: two `iac_plan` calls simultaneously could corrupt `.terraform/` state — mitigated by serializing via a module-level lock in `iac.py`.

---

## Compliance

Enforced by:
- **Implementation**: `magenta/agent_ops/iac.py` — all three tools use `subprocess.run()` with `terraform` CLI.
- **Dockerfile**: `Dockerfile.agent-ops` installs Terraform from releases.hashicorp.com.
- **Drift logic**: `iac_drift_detect` relies entirely on `-detailed-exitcode` — no custom state comparison.
- **The `iac_plan` and `iac_apply` tools accept an `environment` parameter constrained to `["dev", "staging", "production"]`.

---

## Notes

- The `terraform` binary is **not** installed in other containers (mcp-bridge, mcp-web) — only agent-ops needs it.
- Future enhancement: use `terraform show -json tfplan` to parse plan details more granularly.
