# Magenta LLM Policy

## Purpose

Magenta uses a policy-driven LLM Gateway for all SOAR agent interactions. Direct calls to LLM providers are forbidden. This policy ensures consistent routing, cost control, security, and auditability across all agent workflows.

## Scope

- Applies to all Magenta agents and services that invoke LLMs
- Applies to all LLM providers — hosted (OpenAI, Gemini, Groq) and local (Ollama, vLLM)
- Includes all SIEM/SOAR-related workflows (triage, enrichment, containment, investigation, compliance, reporting)

## Core Principles

- **One gateway, many providers** — every LLM call routes through the gateway
- **Policy before model** — routing decisions are governed by policy, not hardcoded
- **Local GPU capacity as primary resilience tier** — Ollama is the default fallback when hosted providers are unavailable or rate-limited
- **Prompt minimalism and retrieval-first context** — minimize token consumption via RAG and structured context
- **Human-in-the-loop for high-risk actions** — any action affecting production systems requires explicit approval

## Routing Policy

### Sensitivity-based routing

| Sensitivity Level | Allowed Providers | Fallback |
|---|---|---|
| `HIGH` | Local Ollama only | Queue/defer; no external egress |
| `MEDIUM` | Local preferred; hosted allowed with policy override | Local |
| `LOW` | Hosted allowed when within quota | Local |

### Priority and latency

- `priority=interactive` — low-latency models (target < 2s), strict token budgets, no queuing
- `priority=batch` — queued processing, can favor local Ollama, no latency SLA

### Fallback Behavior

1. On `429 Too Many Requests` or provider `5xx`, obey `Retry-After` header
2. Retry once with exponential backoff (1s, 2s, 4s)
3. If still failing and policy allows, route to local Ollama
4. Otherwise queue or defer with a notification to the Agent Ops Engineer

### Budget enforcement

- Per-provider token bucket (sliding window)
- Per-workflow daily token quota
- Cost cap: if any single workflow exceeds $0.50/day in hosted API costs, route to local

## Provider Usage Guidelines

- No agent may call external LLMs directly — all calls go through the gateway
- All new workflows must integrate via the LLM Gateway
- Model selection is configured in policy (`config/llm-routing.yaml`), not in code
- New provider adapters require architecture review board approval

## Redaction and Egress

- Sensitive fields must be redacted or replaced with placeholders before any external provider call:

  | Field Type | Redaction |
  |---|---|
  | Usernames, email addresses | Replace with `[USER_REDACTED]` |
  | IP addresses, hostnames | Replace with `[HOST_REDACTED]` |
  | Ticket IDs, incident numbers | Replace with `[REF_REDACTED]` |
  | Secrets, passwords, tokens | Strip entirely |
  | Free-text PII | MATS pattern-matching scrub |

- HIGH-sensitivity incidents must never leave controlled environments — local inference only

## Audit and Logging

Every LLM call must record to the registry (Elasticsearch, Sentinel custom tables, and Data Lake):

| Field | Description |
|---|---|
| `correlation_id` | Links to originating alert and mission |
| `task_type` | triage, enrich, contain, investigate, compliance, report |
| `provider` | ollama, gemini, groq, openrouter |
| `model` | Specific model name |
| `sensitivity_level` | high, medium, low |
| `priority` | interactive, batch |
| `fallback_used` | Boolean |
| `tokens_in` | Approximate input tokens |
| `tokens_out` | Approximate output tokens |
| `latency_ms` | End-to-end latency |
| `redacted` | Boolean — was redaction applied? |
| `risk_score` | Computed risk score for the action |

## Approvals and Risk

- Any action that can change customer-facing or production systems requires explicit human approval
- The approval gate evaluates risk score before escalation (see [Approval Gate](../architecture/resources/approval-gate/readme.md))
- Policy exceptions must be documented, time-bounded, and approved by the SOC Manager

## Compliance and Review

- This policy is reviewed quarterly
- Changes are tracked via pull requests and tagged releases
- Non-compliance is reported to the Architecture Change Board
- Enforcement is automated via CI/CD gate — any workflow bypassing the gateway fails deployment
