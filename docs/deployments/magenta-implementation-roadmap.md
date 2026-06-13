# Magenta Implementation Roadmap

**8-Phase build plan for the Magenta ASOAR core application.**

---

## Phase 1: Skeleton (Day 1)

**Goal:** Project boots, `$ magenta --help` works, directory structure is complete.

| Task | Files |
|---|---|
| `pyproject.toml` with Typer entry point | `pyproject.toml` |
| Directory scaffolding | `magenta/`, `tests/`, `config/`, `data/` |
| `magenta/main.py` — Typer app entry | `magenta/main.py` |
| `magenta/config.py` — Pydantic Settings | `magenta/config.py` |
| All `__init__.py` files | 20+ init files |
| `magenta/exceptions.py` | `magenta/exceptions.py` |

**Acceptance:** `pip install -e .` → `magenta --help` shows command groups.

---

## Phase 2: Core Domain + CLI (Days 2–3)

**Goal:** All domain models exist, all CLI commands render `--help`, command stubs execute.

| Task | Files |
|---|---|
| Pydantic models: Agent, Mission, Swarm, Playbook, Action | `magenta/core/models.py` |
| Agent base class + registry | `magenta/core/agent.py` |
| Mission lifecycle state machine | `magenta/core/mission.py` |
| Swarm decomposition logic | `magenta/core/swarm.py` |
| Playbook parser (YAML + TOML) | `magenta/core/playbook.py` |
| CLI app root + groups | `magenta/cli/app.py` |
| `orchestrate` commands (start, stop, status, list, logs, replay) | `magenta/cli/orchestrate.py` |
| `automate` commands (playbook, rule, trigger sub-groups) | `magenta/cli/automate.py` |
| `response` commands (actions, approval, incidents) | `magenta/cli/response.py` |
| `health` commands (check, agents, models, pipeline, storage) | `magenta/cli/health.py` |
| `lab` commands (simulate, test, compare, evaluate) | `magenta/cli/lab.py` |
| CLI utilities (table formatting, JSON output, colors) | `magenta/cli/utils.py` |

**Acceptance:** Every CLI command renders correct `--help` and validates arguments.

---

## Phase 3: Data Layer (Days 4–6)

**Goal:** All storage backends connected and testable.

| Task | Files |
|---|---|
| Abstract Repository interface | `magenta/data/base.py` |
| SQLAlchemy async models (Mission, Agent, Playbook, Action, Approval) | `magenta/data/sql/models.py` |
| DB session + connection management | `magenta/data/sql/session.py` |
| Repositories (MissionRepo, AgentRepo, PlaybookRepo, ActionRepo) | `magenta/data/sql/repositories/*.py` |
| NoSQL client (Cosmos DB) | `magenta/data/nosql/client.py` |
| Elasticsearch client + ILM setup | `magenta/data/elastic/client.py` |
| Elasticsearch index mappings | `magenta/data/elastic/indices.py` |
| Elasticsearch query builders | `magenta/data/elastic/queries.py` |
| Data Lake client (ADLS Gen2 + S3) | `magenta/data/lake/client.py` |
| Parquet reader/writer | `magenta/data/lake/parquet.py` |
| Delta Lake operations | `magenta/data/lake/delta.py` |
| LangChain vector store (Chroma) | `magenta/data/langchain/vectorstore.py` |
| Embeddings management | `magenta/data/langchain/embeddings.py` |
| LangChain chains for RAG | `magenta/data/langchain/chains.py` |

**Acceptance:** Each data backend has a working `ping()` health check and basic CRUD.

---

## Phase 4: Integration Layer (Days 7–8)

**Goal:** All external SIEM/SOAR/IT connectors functional.

| Task | Files |
|---|---|
| Microsoft Sentinel connector (Incidents API + Log Ingestion) | `magenta/integration/sentinel.py` |
| Splunk connector (REST search/jobs + fired_alerts) | `magenta/integration/splunk.py` |
| Splunk SOAR connector (audit trail) | `magenta/integration/splunk.py` |
| Entra ID connector (Microsoft Graph) | `magenta/integration/entra.py` |
| Microsoft Defender connector | `magenta/integration/defender.py` |
| ServiceNow connector | `magenta/integration/servicenow.py` |
| Azure Event Hubs producer/consumer | `magenta/integration/eventhub.py` |

**Acceptance:** Each connector has auth, query, and health-check methods.

---

## Phase 5: Agent Implementations (Days 9–11)

**Goal:** All agent roles operational with OLLAMA and model routing.

| Task | Files |
|---|---|
| Abstract BaseAgent with LLM + tool loop | `magenta/agents/base.py` |
| Triage Agent (alert assessment, severity, routing) | `magenta/agents/triage.py` |
| Enrichment Agent (CMDB, TI, identity context) | `magenta/agents/enrich.py` |
| Containment Agent (isolation, disable, block) | `magenta/agents/contain.py` |
| Investigation Agent (deep forensics, timeline) | `magenta/agents/investigate.py` |
| Compliance Agent (regulatory check, audit trail) | `magenta/agents/compliance.py` |
| Reporting Agent (incident summary, stakeholder brief) | `magenta/agents/report.py` |
| Swarm Manager (mission decomposition, assignment) | `magenta/agents/manager.py` |

**Acceptance:** Each agent can be instantiated with a model and process a test alert.

---

## Phase 6: Orchestration Engine (Days 12–14)

**Goal:** End-to-end mission execution pipeline.

| Task | Files |
|---|---|
| Orchestration engine (mission runner) | `magenta/orchestration/engine.py` |
| Task scheduler (cron + interval) | `magenta/orchestration/scheduler.py` |
| Agent task dispatcher | `magenta/orchestration/dispatcher.py` |
| State machine + persistence | `magenta/orchestration/state.py` |
| Automation rules engine (YAML evaluator) | `magenta/automation/engine.py` |
| Rule definitions + parser | `magenta/automation/rules.py` |
| Trigger definitions + watcher | `magenta/automation/triggers.py` |
| Response action executor | `magenta/response/executor.py` |
| Action definitions catalog | `magenta/response/actions.py` |
| Approval gate with escalation | `magenta/response/approval.py` |

**Acceptance:** `magenta orchestrate start phishing.yaml` runs a full mission end-to-end.

---

## Phase 7: API + Webhooks (Days 15–16)

**Goal:** REST API and webhook receivers operational.

| Task | Files |
|---|---|
| FastAPI server with lifespan | `magenta/api/server.py` |
| Auth middleware (Entra ID JWT) | `magenta/api/middleware.py` |
| Dependency injection | `magenta/api/deps.py` |
| Agent management routes | `magenta/api/routes/agents.py` |
| Mission routes | `magenta/api/routes/missions.py` |
| Playbook routes | `magenta/api/routes/playbooks.py` |
| Health routes | `magenta/api/routes/health.py` |
| Search routes | `magenta/api/routes/search.py` |
| Webhook receiver server | `magenta/webhooks/server.py` |
| Sentinel webhook handler | `magenta/webhooks/sentinel.py` |
| Splunk webhook handler | `magenta/webhooks/splunk.py` |
| Generic webhook handler | `magenta/webhooks/generic.py` |

**Acceptance:** API docs render at `/docs`, webhooks accept test payloads.

---

## Phase 8: Lab + Hardening (Days 17–20)

**Goal:** Simulation engine, evaluation suite, production hardening.

| Task | Files |
|---|---|
| Simulation engine (scenario → fake mission) | `magenta/lab/` or extend `cli/lab.py` |
| Model comparison harness | via `cli/lab.py` |
| Evaluation benchmark runner | via `cli/lab.py` |
| Test coverage (Phase 3–7) | `tests/` |
| Security review (OWASP Top 10) | Hardening pass |
| Documentation pass | All docstrings + README |

**Acceptance:** `magenta lab simulate scenarios/phishing.json` produces a full audit trail.
