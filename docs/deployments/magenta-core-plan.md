# Magenta Core Application — Implementation Plan

**Version:** 1.0
**Classification:** Internal Architecture Reference
**Language:** Python 3.11+
**CLI Framework:** Typer
**API Framework:** FastAPI

---

## 1. Architecture

```
$ magenta (CLI Entry Point — Typer)
  │
  ├── orchestrate     Mission lifecycle, swarm management
  ├── automate        Playbooks, rules, triggers
  ├── response        Incidents, actions, approvals
  ├── health          System health (agents, models, pipeline, storage)
  └── lab             Simulation, testing, model comparison
  
magenta/ (Core Python Package)
  ├── core/           Domain models, business logic
  ├── cli/            CLI command implementations
  ├── api/            FastAPI REST server + routes
  ├── webhooks/       Sentinel, Splunk, generic receivers
  ├── data/           SQL, NoSQL, Elastic, Lake, LangChain
  ├── agents/         Agent role implementations
  ├── orchestration/  Swarm manager, scheduler, dispatcher
  ├── automation/     Rules engine, playbook evaluator
  ├── response/       Action executor, approval gate
  ├── integration/    External connectors (SIEM, SOAR, IT)
  └── models/         LLM abstraction (OLLAMA, OpenRouter, Gemini, Groq)
```

---

## 2. CLI Command Reference

| Command | Group | Description |
|---|---|---|
| `magenta --help` | root | Show help with all command groups |
| `magenta orchestrate` | orchestrate | Mission lifecycle management |
| `magenta orchestrate start <playbook>` | orchestrate | Start a mission |
| `magenta orchestrate stop <mission_id>` | orchestrate | Stop a running mission |
| `magenta orchestrate status <mission_id>` | orchestrate | Mission status with agent assignments |
| `magenta orchestrate list` | orchestrate | List all missions |
| `magenta orchestrate logs <mission_id>` | orchestrate | Mission execution logs |
| `magenta orchestrate replay <mission_id>` | orchestrate | Replay mission from registry |
| `magenta automate` | automate | Playbook and automation management |
| `magenta automate playbook list` | automate | List registered playbooks |
| `magenta automate playbook apply <file>` | automate | Register a playbook |
| `magenta automate playbook validate <file>` | automate | Validate playbook schema |
| `magenta automate rule list` | automate | List routing rules |
| `magenta automate rule add <file>` | automate | Add a routing rule |
| `magenta automate trigger list` | automate | List triggers |
| `magenta automate trigger enable <name>` | automate | Enable trigger |
| `magenta response` | response | Incident and action management |
| `magenta response actions list` | response | List available actions |
| `magenta response actions execute <action>` | response | Execute an action |
| `magenta response approval list` | response | List pending approvals |
| `magenta response approval approve <id>` | response | Approve action |
| `magenta response approval reject <id>` | response | Reject action |
| `magenta response incidents list` | response | List incidents |
| `magenta health` | health | System health checks |
| `magenta health check` | health | Full system health |
| `magenta health agents` | health | Agent health status |
| `magenta health models` | health | LLM health status |
| `magenta health pipeline` | health | Pipeline health |
| `magenta health storage` | health | Storage health |
| `magenta lab` | lab | Simulation and testing |
| `magenta lab simulate <scenario>` | lab | Simulate a mission |
| `magenta lab test <agent>` | lab | Test agent prompt |
| `magenta lab compare <a> <b>` | lab | Compare models |
| `magenta lab evaluate <suite>` | lab | Run evaluation |

---

## 3. Data Layer

| Component | Technology | Purpose |
|---|---|---|
| SQL | SQLAlchemy 2.0 (async) + SQLite/Postgres | Missions, agents, playbooks, users |
| NoSQL | Azure Cosmos DB / MongoDB | Mission state, agent sessions |
| Elasticsearch | elasticsearch-py (async) | Hot registry, full-text search |
| Data Lake | ADLS Gen2 / S3 + Parquet/Delta | Cold archive, compliance, replay |
| LangChain | langchain-community + Chroma | Vector store for RAG, prompt templates |

---

## 4. Implementation Phases

| Phase | Focus | Key Deliverables |
|---|---|---|
| 1 | Skeleton | pyproject.toml, directory structure, `$ magenta --help` |
| 2 | Core + CLI | Pydantic models, all CLI commands, config |
| 3 | Data | SQL models, ES client, Lake client, LangChain integration |
| 4 | Integration | Sentinel, Splunk, Entra, Defender connectors |
| 5 | Agents | All 7 agent roles + Swarm Manager |
| 6 | Engine | Orchestration, automation, response modules |
| 7 | API | FastAPI server, webhook receivers |
| 8 | Lab | Simulation, model comparison, evaluation |
