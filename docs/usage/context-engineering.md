# Context Engineering for Magenta

## Overview

Context Engineering is the discipline of crafting the system prompts, agent instructions, and memory structures that shape agent behavior. Magenta provides a **Context Engineering Layer** (`context/`) with domain-specific context files for LLM-assisted development.

## Context File Structure

```
context/
├── readme.md               # Context Engineering Layer overview
├── backend/
│   └── CLAUDE.md           # Backend agent context (Azure Functions, Event Hubs)
├── data/
│   └── CLAUDE.md           # Data agent context (Elasticsearch, Data Lake, schemas)
├── frontend/
│   └── CLAUDE.md           # Frontend agent context (Registry Portal, Kibana)
├── magenta/
│   ├── readme.md           # Framework context overview
│   ├── agentic-teaming-methodologies.md  # 5 teaming structures
│   └── multiagentarchitecture-ref.md     # Multi-agent deep reference
├── ops/
│   └── CLAUDE.md           # Ops agent context (IaC, CI/CD, monitoring)
└── qa/
    └── CLAUDE.md           # QA agent context (testing strategies)
```

Each CLAUDE.md file follows this structure:

```markdown
# Role: [Domain Name]
You are a [role description].

## Project Context
[Overview of what this domain contributes to Magenta]

## Technology Stack
[List of relevant technologies, frameworks, tools]

## Architecture Decisions
[Key ADRs relevant to this domain]

## Current Tasks
[Templates for common task prompts]

## Common Patterns
[Code patterns, conventions, anti-patterns]
```

## Agent Persona Definitions

Each agent role has a system persona defined in its `instructions` field:

```yaml
triage_agent:
  instructions: |
    You are a Triage Agent operating in a SOC environment.
    Your mission is to assess incoming alerts, assign severity,
    and route to the appropriate specialist agent.

    Rules:
    - Severity 5 = Critical -> escalate to human immediately
    - Severity 3-4 -> pass to Enrich Agent for investigation
    - Severity 1-2 -> auto-resolve if confidence > 90%
    - Always check idempotency before routing
```

## Agent Memory Architecture

| Memory Type | Storage | Duration | Content |
|---|---|---|---|
| Short-term | LLM context window | Per turn | Current conversation, recent evidence |
| Working | In-memory (agent process) | Per mission | Ephemeral evidence, partial results |
| Long-term | Vector store + SQL | Persistent | Past missions, agent decisions, patterns |

### Context Window Budget

For a 4K context window (~3,200 tokens safely usable):

| Component | Tokens | % of Budget |
|---|---|---|
| System prompt + rules | 600 | 19% |
| Mission context + evidence | 1,200 | 38% |
| Conversation history (5 turns) | 1,000 | 31% |
| Tool definitions | 300 | 9% |
| Reserved | 100 | 3% |

## Prompt Template Patterns

### Classification Prompt (Triage)

```
Given the following security alert, classify it:
- Severity (1-5)
- Confidence (0.0-1.0)
- Initial recommended action

Alert: {alert_json}

Respond in JSON format:
{
  "severity": int,
  "confidence": float,
  "recommended_action": str,
  "reasoning": str
}
```

### Investigation Prompt (Enrich/Investigate)

```
You are investigating alert {alert_id} from {source_system}.
Available evidence: {evidence_summary}

Tools available:
{tools_list}

Objective: Determine the root cause and provide actionable recommendations.
Previous findings: {previous_agent_findings}
```

## System Prompt Versioning

System prompts are versioned alongside the codebase:

```
context/magenta/instructions/v1/triage.txt
context/magenta/instructions/v2/triage.txt
```

Version is pinned per agent in config:

```yaml
triage_agent:
  instruction_version: "v2"
  instructions_file: "context/magenta/instructions/v2/triage.txt"
```

## Prompt Injection Guardrails

| Guardrail | Implementation |
|---|---|
| Input sanitization | Strip control characters, limit input length |
| Instruction boundary | Wrap user input in delimiters: `=== USER INPUT ENDS HERE ===` |
| Output validation | Validate JSON schema before processing |
| Role confinement | System prompt re-asserted after each user input |
