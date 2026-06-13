# Multi-Agent Architecture Reference — Magenta Framework

**Reference:** Google ADK · AutoGen · CrewAI · LangGraph patterns, adapted for cybersecurity SOAR domain.

---

## 1. Agent Communication Patterns

### 1.1 Direct Messaging (ADK-style)

Agents communicate through structured messages on the Event Hubs bus. Each message carries type, source, destination, payload, and trace context.

```json
{
  "message_type": "task_result",
  "source": "enrich_agent",
  "destination": "swarm_manager",
  "correlation_id": "mission-8932",
  "task_id": "task-enrich-001",
  "payload": {
    "verdict": "malicious",
    "confidence": 0.89,
    "evidence": {"iocs": ["ip:185.220.101.x"], "mitre": "TA0001-T1566"}
  },
  "trace": {
    "model": "ollama/mistral:7b",
    "latency_ms": 3400,
    "tokens_in": 1200,
    "tokens_out": 240,
    "turn": 3
  }
}
```

### 1.2 Broadcast (Event Hubs Topics)

- `raw-alerts` — all source alerts (fan-out to multiple agents)
- `enriched-alerts` — enriched events (consumed by swarm agents)
- `actions` — execution commands (consumed by execution agents)
- `agent-heartbeat` — agent health telemetry (consumed by swarm manager)
- `agent-discovery` — agent capability announcements (service discovery)

### 1.3 Agent Discovery Protocol

Agents register their capabilities on startup:

```yaml
agent_discovery:
  agent_id: "containment_specialist-v2"
  role: "containment"
  tools:
    - "entra_id.disable_account"
    - "defender.isolate_host"
    - "sentinel.update_incident"
  models:
    primary: "ollama/qwen2.5:7b"
    fallback: "ollama/mistral:7b"
  risk_tolerance: 0.4
  max_concurrent_tasks: 3
  load: 0.2  # current utilization
```

The Swarm Manager maintains a live registry of available agents and their load.

---

## 2. Task Decomposition

### 2.1 Mission Decomposition Prompt (Swarm Manager)

```
Incoming alert: {{alert_json}}

Decompose this alert into a set of security response tasks.
For each task specify:
- task_id: unique identifier
- task_type: triage | enrich | contain | investigate | notify | report
- required_tools: list of tools needed
- dependencies: task_ids that must complete first
- risk_score: 0-100 estimated risk
- estimated_complexity: low | medium | high
- delegation_strategy: solo | debate | pipeline

Output as JSON array of tasks.
```

### 2.2 Task Dependency Graph

The Swarm Manager builds a DAG of tasks. Example for a phishing incident:

```
[Triage] ─► [Enrich: URL scan]
  │              │
  │              ├──► [Enrich: sandbox]
  │              │         │
  │              ├──► [Enrich: identity lookup]
  │              │         │
  │              ▼         ▼
  │         [Contain: block URL] ◄── if malicious
  │              │
  │         [Contain: disable account] ◄── if credentials compromised
  │              │
  ▼              ▼
          [Investigate: full timeline]
               │
          [Report: incident summary]
```

---

## 3. Memory Architecture

### 3.1 Memory Tiers

| Tier | Storage | Scope | Retention | Backend |
|---|---|---|---|---|
**Agent Memory | In-context | Current turn | N/A | LLM context window |
| Working Memory | Redis / Table Storage | Current mission | TTL: 24h | Ephemeral key-value |
| Episodic Memory | Elasticsearch | Cross-mission patterns | 90d | Agent reasoning logs |
| Semantic Memory | Vector DB (optional) | SOC knowledge base | Permanent | Embeddings + Chroma/PGVector |

### 3.2 Context Window Management

For OLLAMA models with limited context:

```python
class ContextManager:
    def trim(self, messages: List[Message], max_tokens: int = 4096) -> List[Message]:
        """Trim oldest turns, preserve system prompt and tool definitions."""
        system = [m for m in messages if m.role == "system"]
        tools = [m for m in messages if m.role == "tool"]
        history = [m for m in messages if m.role not in ("system", "tool")]
        
        # Always keep last exchange (current query + response)
        # Drop oldest turns first until under limit
        while token_count(system + tools + history) > max_tokens:
            history.pop(0)
        
        return system + tools + history
```

---

## 4. Tool Integration Pattern

### 4.1 Tool Definition Schema

```yaml
tool:
  name: "disable_entra_account"
  description: "Disable a user account in Entra ID (Azure AD)"
  parameters:
    type: "object"
    required: ["user_principal_name", "reason"]
    properties:
      user_principal_name:
        type: "string"
        description: "UPN of the user to disable"
      reason:
        type: "string"
        enum: ["compromised", "malicious_activity", "policy_violation"]
      notify_manager:
        type: "boolean"
        default: true
  risk_impact: 80
  requires_approval: true
  auth: "managed_identity"
  timeout: 30
```

### 4.2 Tool Execution Lifecycle

```
1. Agent requests tool call (LLM output)
2. Swarm Manager validates:
   - Is agent authorized for this tool?
   - Does action require approval? (risk check)
   - Is idempotency_key unique?
3. If approval required:
   - Publish approval request to human queue
   - Wait for response (or timeout)
4. Execute tool via managed identity
5. Log result to registry
6. Return result to agent context
```

### 4.3 Idempotency for Tool Calls

```python
def execute_with_idempotency(tool_call: ToolCall) -> ToolResult:
    key = hashlib.sha256(
        f"{tool_call.agent_id}:{tool_call.tool_name}:{tool_call.parameters_hash}"
    ).hexdigest()
    
    if idempotency_store.exists(key):
        return idempotency_store.get(key)  # Return cached result
    
    result = tool_call.execute()
    idempotency_store.set(key, result, ttl=86400)
    return result
```

---

## 5. Agent State Machine

Each agent operates as a state machine within a mission:

```
         ┌─────────┐
         │  IDLE   │
         └────┬────┘
              │ mission_assigned
              ▼
         ┌─────────┐
         │ READY   │
         └────┬────┘
              │ task_received
              ▼
         ┌──────────┐
    ┌───►│ EXECUTING │◄────────┐
    │    └─────┬────┘          │
    │          │                │
    │    ┌─────▼──────┐        │
    │    │ NEED_INPUT  │────────┘ (retry)
    │    └─────┬──────┘
    │          │ input_received
    │          ▼
    │    ┌──────────┐
    │    │ ROUTING   │──► AGENT_ESCALATION (needs specialist)
    │    └─────┬────┘
    │          │ decision_made
    │          ▼
    │    ┌──────────┐
    │    │ APPROVAL  │──► HUMAN_APPROVAL (risk > threshold)
    │    └─────┬────┘
    │          │ approved
    │          ▼
    │    ┌───────────┐
    │    │ TOOL_EXEC │
    │    └─────┬─────┘
    │          │ complete
    │          ▼
    │    ┌──────────┐
    │    │ REPORTING │
    │    └─────┬────┘
    │          │ reported
    │          ▼
    │    ┌──────────┐
    │    │  DONE    │
    │    └──────────┘
    │
    └── (next task)
```

---

## 6. Failure Handling

### 6.1 Agent-Level Failures

| Failure | Detection | Recovery |
|---|---|---|
| LLM timeout (model unresponsive) | Heartbeat miss > 30s | Retry with fallback model |
| Tool call error | Exception in tool exec | Retry (3x), then escalate |
| Context overflow | token_count > threshold | Context trimmer activates |
| Hallucinated tool call | Tool name not in registry | Reject + re-prompt |
| Contradictory decisions | Confidence < 0.3 | Trigger debate with second agent |

### 6.2 Swarm-Level Failures

| Failure | Detection | Recovery |
|---|---|---|
| Agent dead (no heartbeat) | 3 missed heartbeats | Reassign tasks to another agent with same role |
| Task dependency deadlock | Cycle detection in DAG | Escalate to human with deadlock report |
| Consensus failure | Agents can't agree after N rounds | Human tiebreaker mode |
| Mission timeout | Max_turns exceeded | Force-complete with best-effort results |

---

## 7. Reference: Google ADK Mapping

| Google ADK Concept | Magenta Equivalent | Notes |
|---|---|---|
| `Agent` class | Agent role configuration | ADK's structured output pattern |
| `tool` decorator | Tool definition YAML | Same parameter schema pattern |
| `transfer_to_agent()` | Event Hubs `task_result` message | ADK's synchronous call vs. Magenta's async bus |
| `before_agent` callback | Swarm Manager pre-processing | Pre-tool validation, idempotency check |
| `after_agent` callback | Registry Agent post-processing | Audit logging, evidence capture |
| `Runner.run()` | `magenta run --mission` | ADK single-process vs. Magenta distributed |
| Articulated Agent (multi-step) | Swarm agent with memory | Same decomposition pattern |
| `CodeExecutionTool` | Sandboxed Python executor | Magenta wraps in container |
