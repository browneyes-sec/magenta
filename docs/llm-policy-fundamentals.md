# LLM Gateway and Policy Fundamentals

## Executive Overview

Magenta is an agentic AI framework for cybersecurity SOAR operations. Every agent — triage, enrichment, containment, investigation, compliance, reporting — relies on LLM inference for reasoning, classification, and action selection. This document describes the **policy-driven LLM Gateway** that sits between Magenta agents and all model providers, including hosted APIs and local GPU inference.

The gateway enforces routing policy, rate-limit resilience, redaction, audit logging, and cost controls — ensuring that agent LLM usage is secure, observable, and cost-predictable regardless of which provider serves a given request.

## Problem Statement

1. **SOAR workloads generate bursty, high-volume LLM traffic.** Alert surges can spike 10× baseline within minutes, overwhelming hosted provider rate limits.
2. **Hosted providers enforce TPM/RPM limits and return 429 on excess usage.** Without a gateway, every agent independently hits these limits, causing cascading failures.
3. **Direct agent-to-provider calls cause inconsistent policies.** One agent may use Gemini, another Ollama — with no centralized redaction, cost tracking, or fallback coordination.
4. **Weak auditability.** Without a gateway, there is no single point to record every LLM decision, model used, tokens consumed, and latency incurred.
5. **Sensitive SOC data cannot egress to untrusted providers.** HIGH-sensitivity incidents must stay on-premises, but agents need a policy mechanism to enforce this without hardcoded provider selection.

## Design Principles

- **One gateway, many providers** — every LLM call routes through the gateway regardless of provider or model
- **Policy-driven routing** — model selection, fallback, and cost controls are configured in policy, not code
- **Local GPU (Ollama/vLLM) as strategic capacity** — on-premises inference provides resilience, data sovereignty, and predictable latency
- **Minimal prompts with retrieval-first context engineering** — RAG over Elasticsearch and Data Lake reduces token consumption and improves response quality
- **Retry with control and respect for provider rate-limit guidance** — exponential backoff obeying `Retry-After` headers, circuit breakers for degraded providers
- **Full auditability for every LLM decision** — every call logged to Elasticsearch, Sentinel custom tables, and Azure Data Lake

## Reference Architecture

### High-Level Flow

```
Incident (Sentinel / Splunk)
    │
    ▼
Event Hubs (raw-alerts)
    │
    ▼
Magenta Agent (Triage, Enrich, Contain, ...)
    │  sends LLM request to Gateway
    ▼
┌─────────────────────────────────────┐
│         LLM Gateway                  │
│                                     │
│  1. Evaluate policy & quotas        │
│  2. Select provider (hosted/local)   │
│  3. Apply redaction & compaction     │
│  4. Execute with retry & fallback    │
│  5. Log decision + response          │
│  6. Return to agent                  │
└─────────────────────────────────────┘
    │
    ├──► Hosted Provider (Gemini, Groq, OpenRouter)
    ├──► Local Inference (Ollama on GPU nodes)
    └──► Queue / Defer (if all exhausted)
    │
    ▼
Registry (Elasticsearch + Sentinel + ADLS)
    │
    ▼
Approval Gate (if risk_score > threshold)
    │
    ▼
SOAR Execution (Splunk SOAR / Logic Apps / Functions)
```

### Components

| Component | Technology | Role |
|---|---|---|
| **LLM Gateway** | FastAPI on Azure Container Apps / AKS | Request routing, policy evaluation, redaction, retry, logging |
| **Provider Adapters** | Python (httpx) | Provider-specific API formatting, auth, error mapping |
| **Local Inference** | Ollama on GPU nodes | On-premises model serving, primary resilience tier |
| **Rate-Limit Store** | Redis | Token bucket state, concurrency caps, circuit breaker state |
| **Semantic Cache** | Redis + Vector Store | Near-duplicate request deduplication |
| **Context Store** | Elasticsearch + Data Lake | Incident history, agent memory, RAG documents |
| **Registry** | Elasticsearch + Sentinel + ADLS | Audit trail for every LLM decision |
| **Identity** | Entra ID Managed Identities + Key Vault | Provider credentials, gateway authentication |

## Routing and Policy Model

### Request Contract

Every LLM request to the gateway includes:

```json
{
  "correlation_id": "uuid",
  "task_type": "triage | enrich | contain | investigate | compliance | report",
  "sensitivity_level": "high | medium | low",
  "priority": "interactive | batch",
  "max_latency_ms": 5000,
  "max_output_tokens": 1024,
  "context_refs": ["es://incident/8932", "lake://missions/..."],
  "fallback_policy": "local_only | local_preferred | any",
  "approval_required": false,
  "prompt": "classify this alert: ...",
  "system_instructions": "You are a triage agent..."
}
```

### Policy Evaluation

```yaml
# Gateway evaluates this policy per request:
policies:
  - match:
      sensitivity_level: high
    routing:
      providers: ["ollama"]
      fallback: "queue"
    redaction:
      enabled: false  # no egress at all
    quotas:
      max_tokens_per_minute: 100000

  - match:
      task_type: triage
      sensitivity_level: medium
    routing:
      providers: ["ollama", "gemini"]
      preferred: "ollama"
      fallback: "gemini"
    redaction:
      enabled: true
      fields: ["usernames", "ip_addresses"]

  - match:
      task_type: report
      sensitivity_level: low
    routing:
      providers: ["gemini", "groq", "ollama"]
      preferred: "gemini"
      fallback: "ollama"
    quotas:
      max_cost_per_day: 0.50
```

### Example Routing Decisions

| Request | Policy Match | Provider Selected | Rationale |
|---|---|---|---|
| Triage — HIGH sensitivity ransomware | `sensitivity: high` | Ollama (local) | No external egress allowed |
| Enrich — MEDIUM, threat intel lookup | `task: enrich, sens: medium` | Ollama (preferred) | Local capacity available |
| Report — LOW, daily summary | `task: report, sens: low` | Gemini (hosted) | Within quota, lower cost |
| Any — 429 from Gemini | Fallback rule → Ollama | Ollama | Rate-limit resilience |
| Any — all providers exhausted | Fallback rule → queue | Queued | Defer, notify Agent Ops |

## Rate-Limit Resilience

### Token Estimation

Before dispatching to a hosted provider, the gateway estimates token usage:

```python
def estimate_tokens(prompt: str, system: str, max_output: int) -> int:
    input_tokens = len(prompt.split()) * 1.3 + len(system.split()) * 1.3
    return int(input_tokens) + max_output
```

### Token Bucket (Redis)

```python
class TokenBucket:
    def __init__(self, redis, key: str, capacity: int, refill_rate: float):
        self._redis = redis
        self._key = f"token-bucket:{key}"
        self._capacity = capacity
        self._refill = refill_rate

    async def consume(self, tokens: int) -> bool:
        current = await self._redis.get(self._key)
        if current is None:
            await self._redis.set(self._key, self._capacity, ex=60)
            current = self._capacity
        current = float(current)
        if current >= tokens:
            await self._redis.decrby(self._key, tokens)
            return True
        return False
```

### Circuit Breaker

```python
class CircuitBreaker:
    STATES = {"closed", "open", "half-open"}

    def __init__(self, redis, provider: str, failure_threshold: int = 5):
        self._redis = redis
        self._key = f"cb:{provider}"
        self._threshold = failure_threshold

    async def record_failure(self):
        count = await self._redis.incr(f"{self._key}:failures")
        if count >= self._threshold:
            await self._redis.set(f"{self._key}:state", "open", ex=30)

    async def allow_request(self) -> bool:
        state = await self._redis.get(f"{self._key}:state")
        return state != "open"
```

## Context Engineering

- **Retrieval over replay** — incident context is retrieved from Elasticsearch and Data Lake rather than replayed from chat history
- **Rolling incident summaries** — instead of passing full conversation history, agents receive a condensed summary of prior turns
- **Task-specific prompt templates** — each agent role has a versioned prompt template (see [Prompt Engineering](usage/prompt-engineering.md))
- **Redaction layer** — before any external provider call, sensitive fields are stripped or replaced

## Local Inference with Ollama

- Runs open-weight models (qwen2.5, mistral, mixtral, deepseek-r1) on enterprise GPU infrastructure
- Exposes HTTP API at configurable endpoint (`MAGENTA_MODELS__OLLAMA_HOST`)
- Acts as default capacity tier for:
  - Bulk processing (batch priority)
  - HIGH-sensitivity incidents (data sovereignty)
  - Hosted-provider fallback (rate-limit resilience)
- See [GPU Architecture](architecture/resources/gpu/readme.md) for capacity planning

## Implementation Plan (DTP Snapshot)

### Phase 1 — Foundation (Days 1-30)
- Gateway skeleton with FastAPI
- One hosted adapter (Gemini) and one local adapter (Ollama)
- Basic policy evaluation (sensitivity-based routing)
- Audit logging path to Elasticsearch
- Token bucket rate limiting (Redis)

### Phase 2 — Pilot (Days 31-60)
- RAG integration with Elasticsearch
- Redaction layer for PII/sensitive fields
- Sensitivity-based routing with policy YAML
- HTTP 429 handling with backoff and fallback
- Approval gate integration

### Phase 3 — Hardening (Days 61-90)
- BU-specific routing policies
- GPU capacity planning and scaling
- SLO monitoring and cost dashboards
- Runbooks for provider degradation
- Semantic cache for near-duplicate requests

## Nonfunctional Requirements

| Requirement | Target |
|---|---|
| Gateway availability (pilot) | 99.9% |
| Gateway availability (production) | 99.95% |
| P99 latency overhead (gateway itself) | < 50 ms |
| No direct agent-to-provider traffic post-cutover | 100% |
| Policy and prompt versioning via CI/CD | Required |
| Full traceability from LLM request to SOAR action | Required |
| Redaction accuracy | 100% for known patterns |

## References

| Document | Link |
|---|---|
| Magenta LLM Policy (operational) | [context/llm-policy.md](../context/llm-policy.md) |
| GPU Architecture & Sizing | [architecture/resources/gpu/readme.md](../architecture/resources/gpu/readme.md) |
| Prompt Engineering Guide | [docs/usage/prompt-engineering.md](usage/prompt-engineering.md) |
| Approval Gate Architecture | [architecture/resources/approval-gate/readme.md](../architecture/resources/approval-gate/readme.md) |
