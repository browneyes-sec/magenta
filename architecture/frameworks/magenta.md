# Magenta Framework — Agentic System Orchestration Automation and Response (ASOAR)

**Version:** 1.0
**Classification:** Internal Architecture Reference
**Stack:** OLLAMA · Google ADK (reference) · Azure Functions · Event Hubs · Sentinel · Elasticsearch

***

## 0. What is Magenta?

Magenta is an **open-weight agentic framework** for cybersecurity **S**ystem **O**rchestration **A**utomation and **R**esponse. It defines a multi-agent teaming layer that sits between SIEM detection and SOAR execution, enabling SOC teams to deploy, govern, and observe AI agents that collaborate like human teams — with specialization, escalation, consensus, and human oversight baked into the fabric.

Unlike traditional SOAR (rigid playbooks, single-threaded automation), Magenta treats every security operation as a **multi-agent mission**: agents discover tasks, delegate subtasks, share evidence, challenge decisions, and report outcomes into an immutable registry.

Magenta is LLM-agnostic. It runs on OLLAMA-hosted open models (Llama, Qwen, Mistral, DeepSeek), free-tier APIs (Groq, Hugging Face, Google Gemini), or enterprise models — switching via a single configuration key.

***

## 1. Core Concepts

### 1.1 Agent

An **agent** is an autonomous unit with:
- **Role** — a defined cybersecurity function (Triage Agent, Containment Agent, Compliance Agent)
- **Model** — an LLM backend (OLLAMA endpoint, Google Gemini, Hugging Face Inference)
- **Tools** — API access to SIEM, SOAR, Active Directory, ticketing, threat intel
- **Memory** — short-term (conversation context), working (ephemeral evidence), long-term (registry-backed)
- **Persona** — system prompt defining behavior, risk tolerance, and escalation thresholds

```yaml
  agent:
    role: "containment_specialist"
    model: "ollama/mistral:7b"
    tools:
      - entra_id.disable_account
      - sentinel.update_incident
      - service_now.create_ticket
      - defender.isolate_host
    risk_tolerance: 0.4
    escalation_threshold: 0.7
```

### 1.2 Mission

A **mission** is an end-to-end security response workflow triggered by an alert or incident. It has:
- **Initiator** — the alert source (Sentinel incident, Splunk fired alert, manual trigger)
- **Objective** — what must be achieved (contain, investigate, notify, remediate)
- **Team** — dynamically assembled set of agents assigned to roles
- **Artifacts** — evidence, decisions, actions, outcomes — all written to the registry
- **State** — lifecycle: `created → scoped → assigned → executing → review → completed | escalated`

### 1.3 Swarm

A **swarm** is a temporary team of agents collaborating on a mission. Swarms are dynamic — agents join and leave based on task requirements. Swarm patterns include:

| Pattern | Structure | Use Case |
|---|---|---|
| Supervisor | One coordinator delegates to specialists | Complex multi-step incidents |
| Debate | Multiple agents analyze same evidence, converge on verdict | Phishing triage, false positive reduction |
| Pipeline | Sequential handoff: triage → enrich → contain → report | Standard SOAR playbook replacement |
| Mesh | Peer-to-peer: agents broadcast tasks, volunteers claim them | Alert surge handling, load-balanced triage |

---

## 2. Framework Layers

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        MAGENTA FRAMEWORK                                  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │            ORCHESTRATION LAYER — Swarm Manager                      │  │
│  │  Mission lifecycle · Agent assignment · Task decomposition          │  │
│  │  Consensus engine · Escalation router · Human handoff               │  │
│  └─────────────────────────┬──────────────────────────────────────────┘  │
│                            │                                            │
│  ┌─────────────────────────▼──────────────────────────────────────────┐  │
│  │            AGENT LAYER — Role-Specific Agents                       │  │
│  │                                                                    │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐  │  │
│  │  │ Triage   │ │ Enrich   │ │ Contain  │ │ Investig │ │ Report  │  │  │
│  │  │ Agent    │ │ Agent    │ │ Agent    │ │ Agent    │ │ Agent   │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └─────────┘  │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐  │  │
│  │  │ Threat   │ │ Identity │ │Compliance│ │ Forensic │ │ SOC     │  │  │
│  │  │ Intel Ag │ │ Agent    │ │ Agent    │ │ Agent    │ │ Liaison │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └─────────┘  │  │
│  └─────────────────────────┬──────────────────────────────────────────┘  │
│                            │                                            │
│  ┌─────────────────────────▼──────────────────────────────────────────┐  │
│  │            MODEL LAYER — LLM Abstraction                            │  │
│  │                                                                    │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │  OLLAMA (Local) │ Google Gemini │ Hugging Face │ Groq │ ... │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  │  Router: model selector per agent role, fallback, cost tracking    │  │
│  └─────────────────────────┬──────────────────────────────────────────┘  │
│                            │                                            │
│  ┌─────────────────────────▼──────────────────────────────────────────┐  │
│  │            TOOL LAYER — SIEM/SOAR/IT Integration                    │  │
│  │                                                                    │  │
│  │  Sentinel API · Splunk REST · Entra ID Graph · ServiceNow          │  │
│  │  Defender ATP · VirusTotal · Shodan · MITRE ATT&CK                 │  │
│  │  Event Hubs producer/consumer · Registry writer                     │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Multi-Agent Architecture (Reference: Google ADK)

Magenta's agent architecture draws from the **Google Agent Development Kit (ADK)** patterns for structured delegation and tool integration, adapted for cybersecurity domain semantics.

### 3.1 Agent Definitions (ADK-inspired)

Each agent is defined as a configuration object:

```python
@agent(
    role="triage_agent",
    model="ollama/qwen2.5:7b",
    instructions="""
    You are a Triage Agent operating in a SOC environment.
    Your mission is to assess incoming alerts, assign severity,
    and route to the appropriate specialist agent.

    Rules:
    - Severity 5 = Critical → escalate to human immediately
    - Severity 3-4 → pass to Enrich Agent for investigation
    - Severity 1-2 → auto-resolve if confidence > 90%
    - Always check idempotency before routing
    """,
    tools=[
        sentinel_query_incidents,
        sentinel_update_incident_status,
        event_hubs_publish,
        registry_write,
    ],
    memory=EphemeralMemory(window=50),
    delegation=SwarmRouting(supervisor="swarm_manager"),
)
```

### 3.2 Delegation Patterns

| Pattern | ADK Equivalent | Magenta Use |
|---|---|---|
| Sequential handoff | `transfer_to_agent()` | Pipeline: Triage→Enrich→Contain |
| Parallel broadcast | `broadcast_to_agents()` | Multiple analysts on same alert for consensus |
| Supervisor routing | `delegate_to_swarm()` | Swarm Manager assigns subtasks |
| Human escalation | `transfer_to_human()` | Risk > threshold → approval gate |

### 3.3 Swarm Manager (Orchestrator)

The Swarm Manager is a meta-agent that:
1. **Receives** the mission from the Source Agent (via Event Hubs `raw-alerts`)
2. **Decomposes** the alert into tasks (calls LLM with mission decomposition prompt)
3. **Assigns** agents to tasks based on role, availability, and load
4. **Monitors** progress via agent heartbeats and task status
5. **Handles failures** — reassigns tasks, escalates when deadlocked
6. **Completes** the mission — writes `automation.activity` to registry

```yaml
  swarm_manager:
    model: "ollama/mixtral:8x7b"
    max_concurrent_agents: 5
    max_turns: 20
    escalation_policy:
      risk_score_threshold: 70
      max_retries: 3
      human_handoff_after: 300  # seconds
    consensus:
      required_agents: 2
      agreement_threshold: 0.8
      tiebreaker: "human"
```

---

## 4. LLM Abstraction Layer

Magenta abstracts LLM backends so agents are model-agnostic. Models are selected per-role in configuration.

### 4.1 Supported Backends

| Backend | Type | Cost | Best For |
|---|---|---|---|
| OLLAMA | Local (self-hosted) | Free | Sensitive data, low latency, air-gapped SOCs |
| Google Gemini (free tier) | API | Free | Prototyping, low-volume, non-sensitive |
| Hugging Face Inference | API | Free (rate-limited) | Open models, community benchmarks |
| Groq | API | Free tier available | Speed-critical (LPU inference) |
| OpenAI / Anthropic (optional) | API | Paid | Complex reasoning, if budget permits |
| vLLM / TGI | Self-hosted | Infrastructure | Production open-weight deployments |

### 4.2 Router Configuration

```yaml
  model_routing:
    triage_agent:
      primary: "ollama/qwen2.5:7b"
      fallback: "gemini/gemini-2.0-flash"
      max_cost_per_run: 0.01
    containment_agent:
      primary: "ollama/mistral:7b"
      fallback: "ollama/llama3.1:8b"
    compliance_agent:
      primary: "gemini/gemini-2.0-flash"
      fallback: "ollama/qwen2.5:7b"
```

### 4.3 Model Selection Strategy

- **Tier 1 (Speed):** OLLAMA local models for real-time containment actions (< 2s latency)
- **Tier 2 (Reasoning):** Larger models (Mixtral, Qwen 32B) for complex triage decisions
- **Tier 3 (Compliance):** Free API models for audit report generation (cost-insensitive delay)

---

## 5. Teaming Methodologies

Magenta defines five agent teaming structures — see `agentic-teaming-methodologies.md` for depth. Summary:

| Structure | Command & Control | Best For |
|---|---|---|
| **Supervisor** | Hierarchical — one coordinator | Complex incidents requiring multi-step orchestration |
| **Debate** | Democratic — agents argue positions | False positive reduction, verdict convergence |
| **Pipeline** | Sequential — chain of responsibility | Standard playbooks (triage → contain → report) |
| **Mesh** | Peer-to-peer — task marketplace | High-volume alert surges, load balancing |
| **Referee** | Human-in-the-loop — agents propose, human disposes | High-risk actions, compliance-sensitive decisions |

---

## 6. Agent Roles (Cybersecurity Domain)

| Role | Function | Tools | Model Priority |
|---|---|---|---|
| **Triage Agent** | Alert assessment, severity assignment, initial routing | Sentinel, Splunk, Event Hubs | Speed (OLLAMA small) |
| **Enrich Agent** | Context gathering, CMDB lookup, threat intel correlation | ServiceNow, Entra ID, VirusTotal, Shodan | Depth (Mixtral/Qwen) |
| **Containment Agent** | Isolation, account disable, network block | Defender ATP, Entra ID, firewall APIs | Speed (OLLAMA small) |
| **Investigation Agent** | Deep forensic analysis, IoC extraction, timeline reconstruction | Sentinel, Splunk, Azure Data Lake | Reasoning (large model) |
| **Compliance Agent** | Regulatory check, evidence preservation, audit trail | Sentinel custom tables, Data Lake, Key Vault | Accuracy (Gemini/Qwen) |
| **Reporting Agent** | Incident summary, stakeholder brief, KPI update | ServiceNow, email, dashboard APIs | Cost-effective (free API) |
| **Swarm Manager** | Mission orchestration, task decomposition, agent assignment | Event Hubs, registry, monitoring | Reasoning (strongest model) |

---

## 7. Integration with Magenta DTP Pipeline

The framework plugs into the existing **SIEM → Bus → Registry** pipeline:

```
SIEM Alert (Sentinel/Splunk)
  │
  ▼
Event Hubs (raw-alerts)
  │
  ▼
Swarm Manager (decomposes mission)
  │
  ├──► Triage Agent  ──► enriched-alerts
  ├──► Enrich Agent  ──► enriched-alerts
  ├──► Contain Agent ──► actions
  ├──► Investig Agent ──► audit
  ├──► Compliance Ag  ──► audit
  └──► Report Agent  ──► audit
         │
         ▼
   Registry Agent (writes automation.activity)
         │
         ▼
   Elasticsearch · Data Lake · Sentinel Table
```

---

## 8. Human-in-the-Loop Design

### 8.1 Escalation Tiers

| Tier | Trigger | Handoff |
|---|---|---|
| Auto-resolve | Risk < 40, confidence > 90% | No human touch |
| Agent review | 40 ≤ Risk ≤ 70 | Agent recommends actions, human approves/rejects |
| Human lead | Risk > 70, blast_radius = domain | Full human takeover, agents provide recommendations |
| Emergency | Confirmed APT, ransomware, data exfiltration | Agents execute containment immediately, notify SOC in parallel |

### 8.2 Approval Gate Interface

When an agent requires approval, it formats a structured request:

```json
{
  "correlation_id": "uuid",
  "agent": "containment_specialist",
  "action": "isolate_host",
  "target": {"type": "host", "id": "FIN-PROD-347", "criticality": "critical"},
  "risk_score": 85,
  "evidence": {
    "alert_id": "sentinel-incident-8932",
    "finding": "Ransomware indicator detected on endpoint.",
    "confidence": 0.72
  },
  "alternatives": [
    {"action": "disable_network_interface", "risk_score": 45},
    {"action": "create_ticket_for_review", "risk_score": 10}
  ],
  "expires_at": "2026-06-13T20:00:00Z"
}
```

---

## 9. Open Source Model Benchmarks (OLLAMA)

Recommended OLLAMA models for Magenta agent roles, based on cybersecurity task performance:

| Model | Size | Reasoning | Speed | Agent Role Fit |
|---|---|---|---|---|
| `qwen2.5:7b` | 7B | Good | Fast | Triage, Containment |
| `qwen2.5:32b` | 32B | Excellent | Moderate | Swarm Manager, Investigation |
| `mistral:7b` | 7B | Good | Fast | Enrich, Tool Use |
| `mixtral:8x7b` | 47B | Very Good | Moderate | Swarm Manager |
| `llama3.1:8b` | 8B | Good | Fast | Containment, Reporting |
| `deepseek-r1:7b` | 7B | Very Good | Moderate | Investigation, Consensus |
| `phi4:14b` | 14B | Good | Fast | Compliance, Audit |
| `nemotron-mini:4b` | 4B | Adequate | Very Fast | High-volume pre-filtering |

---

## 10. Framework Guardrails

| Guardrail | Mechanism | Enforced By |
|---|---|---|
| No model runs untrusted code | Sandboxed Python executor in container | Agent Runtime |
| No agent bypasses approval | Risk policy checked before every action | Swarm Manager |
| All decisions are logged | Every agent turn → `automation.activity` | Registry Agent |
| Models are pinned per agent | Config-driven, CI/CD validates | Ops CI/CD |
| Human override always wins | Kill switch terminates mission in < 5s | Swarm Manager |
| No secrets in prompts | Prompt pre-processor strips credentials | Agent Runtime |
| Budget-aware routing | Model router tracks cost per run | Model Layer |

---

## 11. Getting Started (Minimal)

```bash
# 1. Install OLLAMA
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull models
ollama pull qwen2.5:7b
ollama pull mistral:7b

# 3. Configure Magenta
cat > magenta.yaml << 'EOF'
swarm_manager:
  model: "ollama/mistral:7b"
  max_agents: 3
agents:
  triage:
    model: "ollama/qwen2.5:7b"
    tools: [sentinel_query, registry_write]
  contain:
    model: "ollama/qwen2.5:7b"
    tools: [entra_disable, defender_isolate]
EOF

# 4. Run swarm
magenta run --mission sentinel-incident-8932
```

---

## 12. Comparison: Magenta vs. Traditional SOAR

| Dimension | Traditional SOAR | Magenta Framework |
|---|---|---|
| Playbook format | Rigid YAML/JSON (if-this-then-that) | Dynamic LLM-driven agent reasoning |
| Decision making | Predefined rules, no context awareness | Context-aware, evidence-grounded |
| Multi-step reasoning | Linear steps only | Parallel, branching, consensus-based |
| Model dependence | No LLM required | OLLAMA-local or free API (no OpenAI required) |
| Audit depth | Log entries | Full agent reasoning chain + evidence references |
| Human handoff | Binary (block/allow) | Graded escalation tiers with recommendations |
| Adaptability | Manual playbook updates | Agents adapt via prompt context + tool feedback |
| Cost | SIEM ingestion + SOAR licensing | OLLAMA (free) + minimal cloud infra |
