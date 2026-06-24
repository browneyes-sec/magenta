# Magenta Chaos Engineering Suite

Agent-based fault injection and resilience validation for the Magenta ASOAR platform.

## Overview

The Chaos Engineering Suite injects controlled faults into the Magenta framework, validates system recovery via existing probes and regression tests, and produces structured certification reports with short/long-term recommendations.

**Zero infrastructure or codebase logic changes** — all chaos is agent-based probe injection and attestation.

## Quick Start

```bash
# Run all enabled scenarios (1-click)
$ magenta chaos run

# Run a specific scenario with intensity 3
$ magenta chaos run --scenario agent_failure --intensity 3

# Dry run (no injection)
$ magenta chaos run --dry-run

# Run with stealth mode (delayed logging)
$ magenta chaos run --stealth

# List available scenarios
$ magenta chaos scenarios

# View latest certification report
$ magenta chaos report
```

## Architecture

```
chaos_engineering/
├── chaos.py                     # Core engine (1-click entry)
├── chaos.toml                   # Scenario configuration (TOML)
├── scenarios/                   # Pre-defined fault scenarios
│   ├── agent_failure.py         # Kill agent mid-mission
│   ├── directive_flood.py       # Overwhelm Dictator
│   ├── model_degradation.py     # LLM provider outage
│   ├── mission_timeout.py       # Mission SLA breach
│   ├── registry_poison.py       # Malformed agent configs
│   ├── pipeline_backpressure.py # Event pipeline congestion
│   └── custom.py                # User-defined scenarios
├── injection/                   # Fault injection primitives
│   ├── agent_injector.py
│   ├── directive_injector.py
│   ├── mission_injector.py
│   └── registry_injector.py
├── attestation/                 # Post-chaos validation
│   ├── preparing.py             # Pre-flight component detection
│   ├── probe_runner.py          # Runs magnet/probes/
│   ├── regression_runner.py     # Runs magnet/ tests
│   └── report_generator.py      # Produces certification reports
└── reports/                     # Raw logs (INFO/WARN/FATAL)
```

## Intensity & Stealth

| Level | Injection Count | Stealth | Description |
|---|---|---|---|
| 1 | 1 target | Off | Single fault, immediate logging |
| 2 | 2 targets | Off | Dual fault, immediate logging |
| 3 | 3 targets | On (30s) | Triple fault, logging delayed 30s |
| 4 | 4 targets | On (60s) | Quad fault, logging delayed 60s |
| 5 | 5 targets | On (120s) | Max fault, logging delayed 120s |

**Stealth mode** delays log emission to simulate "undetected" faults — tests whether probes catch faults without explicit log signals.

## Configuration (chaos.toml)

```toml
[defaults]
intensity = 3
stealth = false
timeout = 300
auto_validate = true

[scenarios.agent_failure]
enabled = true
severity = "medium"
max_intensity = 5
stealth_capable = true
targets = ["triage", "enrich", "contain"]

[scenarios.custom]
enabled = false
module = "path/to/custom.py"
class_name = "MyCustomScenario"
```

## Custom Scenarios

1. Create a Python file with a scenario class:

```python
class MyCustomScenario:
    name = "my_custom"
    description = "My custom chaos scenario"
    severity = "low"

    def __init__(self, intensity: int = 1):
        self.intensity = intensity

    def check_components(self, components) -> tuple[bool, str]:
        return True, ""

    def run(self, components, stealth: bool):
        # Your injection logic
        pass

    def validate(self, components) -> list[dict]:
        # Your validation logic
        pass

    def recommend(self) -> dict:
        return {"short_term": [...], "long_term": [...]}
```

2. Configure in `chaos.toml`:

```toml
[scenarios.custom]
enabled = true
module = "chaos_engineering/scenarios/my_custom.py"
class_name = "MyCustomScenario"
```

3. Run: `$ magenta chaos run --scenario custom`

## Preparing Stage

Before any chaos injection, the preparing stage scans the environment:

```
Preparing Stage Results:
  ✅ Agents: 5 registered
  ✅ Probes: 3 available (dictator, pipeline, registry)
  ✅ Regression: full suite (magnet/)
  ✅ Dictator: importable
  ⚠️ Pipeline: outbox module found, EventHub stub mode
  ℹ️ Skipped: EventHub (no connection string)
```

Components that aren't available are **skipped** — no false positives.

## Certification Reports

Each run produces a condensed certification deposited in `docs/certifications/`:

```
docs/certifications/
├── magenta_chaos-16_06_26-001.md   # First run on June 16, 2026
├── magenta_chaos-16_06_26-001.json # JSON export
├── magenta_chaos-16_06_26-002.md   # Second run same day
└── magenta_chaos-17_06_26-001.md   # First run on June 17
```

Naming convention: `magenta_chaos-DD_MM_YY-NNN.md`

## Raw Logs

`chaos_engineering/reports/` contains per-run logs:

```
chaos_engineering/reports/
├── chaos-16_06_26-001/
│   ├── run.log              # INFO/WARN/FATAL entries
│   ├── stealth.log          # Stealth injection audit trail
│   ├── injection.json       # Injection details
│   ├── probes_pre.json      # Baseline probes
│   ├── probes_post.json     # Post-chaos probes
│   └── regression.json      # Regression results
```

Log levels:
- **INFO**: Injection events, recovery events, validation passes
- **WARN**: Circuit breakers opened, retries exceeded, near-misses
- **FATAL**: Data loss, SLA breach, regression failures

## DTP-03 Alignment

| DTP-03 §5.3 Scenario | Chaos Scenario | Validation |
|---|---|---|
| Kill API pod mid-mission | `agent_failure` | Mission continues from checkpoint |
| Kill Redis | (deferred to infra chaos) | — |
| Kill Ollama | `model_degradation` | Circuit breaker opens, fallback activates |
| EH partition leader failure | `pipeline_backpressure` | Consumer reconnects within 30s |
| Inject network latency | (deferred to infra chaos) | — |
| Poison pill event | `registry_poison` | Registry rejects, no crash |

## Integration with Existing Tests

- **Probes**: Reuses existing `magnet/probes/` for validation
- **Regression**: Runs `pytest magnet/` (full) or `pytest magnet/test_core/ magnet/test_agents/` (lightweight fallback)
- **Dictator**: Chaos runs through Dictator oversight for audit trail

## No-Change Policy

This suite is part of the **software development and production hardening initiative**. It:
- Does NOT modify infrastructure
- Does NOT change codebase logic
- Does NOT require additional deployments
- Only uses existing agent-based probes and test frameworks
