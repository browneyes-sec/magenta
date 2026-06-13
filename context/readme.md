# Context Engineering Layer

This directory defines the multi-agent context engineering layer for the Magenta system. Each subdirectory represents a domain of agentic functionality, containing `CLAUDE.md` files that provide LLM agents (like Cursor, Claude Code, or GitHub Copilot) with the context, conventions, and guardrails needed to work effectively within that domain.

## Purpose

The context engineering layer ensures:

- **Consistency** — every agent operates with the same architectural knowledge
- **Safety** — guardrails prevent common errors (e.g., committing secrets, misconfiguring RBAC)
- **Feedback loops** — structured patterns for code review, testing, and operational handoff
- **Domain isolation** — backend agents don't accidentally modify frontend concerns, and vice versa

## Structure

| Directory | Domain | Primary Responsibilities |
|---|---|---|
| `backend/` | Backend Agents | Azure Functions, Logic Apps, API integrations, Event Hubs producers/consumers |
| `frontend/` | Frontend Agents | Automation Registry Portal, dashboards, Kibana/Grafana configurations |
| `data/` | Data Agents | Data Lake schemas, Delta/Parquet pipelines, Sentinel custom tables, Elasticsearch mappings |
| `qa/` | QA Agents | Test strategies, integration test frameworks, chaos engineering, acceptance criteria validation |
| `ops/` | Ops Agents | CI/CD pipelines, IaC (Bicep/Terraform), monitoring, incident response, RBAC compliance |

## How to Use

Each `CLAUDE.md` file contains:

1. **Domain context** — technology stack, architectural role, key files
2. **Conventions** — coding patterns, naming, documentation standards
3. **Guardrails** — rules the agent must follow (do's and don'ts)
4. **Feedback loops** — review triggers, test requirements, deployment gates
5. **Cross-domain interfaces** — how this domain interacts with others

When starting work on a task, the relevant agent reads its domain's `CLAUDE.md` and the shared architecture reference in `/architecture/readme.md` before generating code or making changes.

## Cross-Domain Communication

Events flow between domains via the canonical `automation.activity` schema defined in `/architecture/readme.md`. Each domain owns specific aspects:

- **Backend** produces and consumes Event Hubs messages
- **Data** owns the schema registry and storage layer
- **Frontend** consumes from Elasticsearch/Sentinel for visualization
- **QA** validates end-to-end flows across all domains
- **Ops** deploys and monitors all components

## Feedback and Guardrail Philosophy

The context engineering layer implements three tiers of feedback:

| Tier | Mechanism | Scope |
|---|---|---|
| **Immediate** | `CLAUDE.md` guardrails | Prevents errors during code generation |
| **Review** | Automated checks (lint, typecheck, test) | Catches issues before commit |
| **Post-hoc** | Acceptance criteria + KPI baselines | Validates correctness in production |

This follows a shift-left safety model: the most expensive error is one found in production; the cheapest is one prevented by context-aware code generation.
