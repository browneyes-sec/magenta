# Magent — Probe & Attestation Layer

## Purpose
**Magent** is the probe and attestation mechanism and layer orchestration for agent operations, tools, and memory processes within the Magenta ASOAR framework.

It validates that every agent invocation, tool call, and memory access is:
- **Attested** — cryptographically verifiable chain of custody for every action
- **Probed** — live introspection of agent state, tool output, and memory integrity
- **Orchestrated** — coordinated across the agent mesh with guaranteed ordering and idempotency

## Concepts

### Probe
A probe is a lightweight observation point injected into agent, tool, and memory boundaries. Probes capture:
- Input/output schemas and payloads
- Timing and latency metrics
- Resource utilization (tokens, memory, compute)
- Decision traces for post-hoc audit

Probes are non-blocking by default and can be promoted to guards (enforcement points) at runtime.

### Attestation
Every action in the agent pipeline produces an attestation record:
- Agent ID, mission ID, playbook run ID
- Action hash (content-addressed)
- Idempotency key
- Parent action hash (chain linkage)
- Signed by the executing node's managed identity

Attestations form a tamper-evident Merkle DAG stored in the Data Lake.

### Layer Orchestration
The orchestration layer coordinates probes and attestations across agent teams:

| Layer | Function | Probe Points |
|-------|----------|--------------|
| L1 — Agent | Per-agent introspection | Pre/post invocation, tool call, memory read/write |
| L2 — Team | Inter-agent message validation | Supervisor routing, debate turns, mesh broadcast |
| L3 — Mission | End-to-end mission integrity | Phase transitions, artifact lineage, approval gates |
| L4 — Platform | Infrastructure attestation | Model router, connector health, storage consistency |

## Directory Structure

```
magnet/
├── readme.md          ← This file
├── __init__.py
├── test_agents/       → Agent-level probe tests
├── test_api/          → API layer attestation tests
├── test_cli/          → CLI probe and audit tests
├── test_core/         → Core model and mission attestation
└── test_data/         → Data layer integrity tests
```

## Usage

```
# Run all probe/attestation checks
magnet --check

# Run attestation for a specific mission ID
magnet --attest <mission_id>

# Promote a probe to enforcement guard
magnet --guard --probe <probe_name>
```

## Integration Points

- **Data Lake** — attestation DAG records stored in `/lake/attestations/`
- **Elasticsearch** — probe metrics indexed for real-time dashboarding
- **Event Hubs** — attestation events published to the `attestations` topic
- **LangChain Tracer** — probe data forwarded to LangSmith/LangFuse observability
