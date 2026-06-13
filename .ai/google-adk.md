# Google ADK — Magenta AI Layer

**Reference:** Google Agent Development Kit (ADK) patterns adapted for Magenta's distributed cybersecurity architecture.

---

## 1. Why Google ADK as Reference

Google ADK provides structured patterns for:
- **Articulated agents** — multi-step reasoning with tool orchestration
- **Structured output** — typed, validated agent responses (via Pydantic/JSON Schema)
- **Delegation** — `transfer_to_agent()` for agent-to-agent handoff
- **Middleware** — `before_agent` / `after_agent` hooks for governance
- **Multimodality** — code execution, file I/O, web search as native tools

Magenta adapts these patterns for an async, Event Hubs-driven architecture.

---

## 2. Agent Definition (ADK Style)

```python
from google.adk import Agent, tool

@tool
def disable_entra_account(user_principal_name: str, reason: str) -> dict:
    """
    Disable a user account in Entra ID.
    Requires managed identity with User administrator role.
    """
    result = graph_client.users[user_principal_name].update(
        body={"accountEnabled": False}
    )
    return {"status": "success", "target": user_principal_name}

@tool
def query_sentinel_incidents(kql_filter: str) -> list:
    """
    Query Microsoft Sentinel for active incidents.
    Returns list of incident objects.
    """
    return sentinel_client.query(f"SecurityIncident | where {kql_filter}")

containment_agent = Agent(
    model="ollama/qwen2.5:7b",
    name="containment_specialist_v2",
    instructions="""
    You are a containment specialist in a SOC environment.
    Actionable tools: disable_entra_account, isolate_defender_host, block_ip_firewall.
    Never act without evidence. Always confirm target exists before acting.
    """,
    tools=[disable_entra_account, query_sentinel_incidents],
    output_schema=ContainmentVerdict,  # Pydantic model
    before_agent_callback=validate_authorization,
    after_agent_callback=log_to_registry,
)
```

---

## 3. Articulated Agent Pattern (Multi-Step)

ADK articulated agents maintain state across turns with explicit tools:

```python
investigation_agent = Agent(
    model="ollama/mixtral:8x7b",
    name="investigator",
    instructions="You are a forensic investigator. Build a timeline of events.",
    tools=[
        query_sentinel_tables,
        query_splunk_events,
        query_data_lake,
        write_evidence_to_registry,
    ],
    # ADK articulates: LLM call → tool result → LLM call → tool result → ...
    max_turns=20,
)
```

---

## 4. Delegation Pattern (Transfer to Agent)

```python
@tool
def escalate_to_containment(incident_summary: str) -> str:
    """Transfer incident to the containment specialist for action."""
    return transfer_to_agent(containment_agent)

triage_agent = Agent(
    model="ollama/qwen2.5:7b",
    name="triage_agent",
    instructions="""
    Assess alerts and route them.
    - Severity 1-2: auto-resolve
    - Severity 3-4: enrich first, then route
    - Severity 5: escalate_to_containment immediately
    """,
    tools=[escalate_to_containment, resolve_incident],
)
```

In Magenta's async architecture, this translates to:

```python
# ADK synchronous call: transfer_to_agent(containment_agent)
# Magenta async equivalent:
async def escalate_to_containment(incident_summary: str) -> str:
    await event_hub.send("actions", {
        "type": "task_assignment",
        "target_role": "containment_agent",
        "payload": {"incident_summary": incident_summary},
        "correlation_id": current_mission.id,
    })
    return {"status": "assigned", "agent": "containment_agent"}
```

---

## 5. Structured Output Schema

ADK enforces typed outputs via Pydantic. Magenta extends this with cybersecurity-specific schemas:

```python
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional

class Verdict(str, Enum):
    MALICIOUS = "malicious"
    BENIGN = "benign"
    UNKNOWN = "unknown"
    ESCALATE = "escalate"

class TriageVerdict(BaseModel):
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    severity: int = Field(ge=1, le=5)
    mitre_tactics: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    reasoning_summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    idempotency_key: str

# Agent with structured output
triage_agent = Agent(
    model="ollama/qwen2.5:7b",
    output_schema=TriageVerdict,
    # ADK enforces JSON Schema validation on output
)
```

---

## 6. Middleware (before_agent / after_agent)

```python
async def validate_authorization(agent_context: AgentContext) -> AgentContext:
    """Before agent runs: verify agent is authorized for this mission."""
    if agent_context.mission.risk_score > agent_context.agent.risk_tolerance:
        raise AuthorizationError(f"Risk {agent_context.mission.risk_score} exceeds tolerance {agent_context.agent.risk_tolerance}")
    return agent_context

async def log_to_registry(agent_context: AgentContext) -> None:
    """After agent runs: write full turn to registry."""
    await registry_client.write_activity({
        "agent_id": agent_context.agent.id,
        "mission_id": agent_context.mission.id,
        "turns": agent_context.turns,
        "tool_calls": agent_context.tool_calls,
        "tokens_used": agent_context.token_count,
        "latency_ms": agent_context.elapsed_ms,
    })

containment_agent = Agent(
    ...
    before_agent_callback=validate_authorization,
    after_agent_callback=log_to_registry,
)
```

---

## 7. ADK ↔ Magenta Mapping Summary

| ADK Feature | ADK Implementation | Magenta Implementation |
|---|---|---|
| Agent definition | `Agent(model, tools, instructions)` | YAML config → Dynamically loaded |
| Tool definition | `@tool` decorator | YAML tool schema → SDK binding |
| Structured output | Pydantic `output_schema` | JSON Schema validation on emit |
| Agent delegation | `transfer_to_agent()` | Event Hubs `task_assignment` message |
| Middleware | `before_agent` / `after_agent` callback | Swarm Manager validation + Registry Agent logging |
| Articulated agent (multi-turn) | `max_turns` with state | Agent memory manager (Redis) |
| Multimodal | Native file + web tools | Tool extension via MCP protocol |
| Runner | `Runner.run()` | `magenta run --mission` |
| Session management | `session_service` | Event Hubs `correlation_id` trace |
