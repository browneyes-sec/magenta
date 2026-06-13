# Magenta

Agentic AI system for fast paced SOAR delivery to enterprise cloud environments.

**AI Agent Security Telemetry Fabric** — a vendor-agnostic platform that autonomously collects detections and incidents from SIEM platforms (Microsoft Sentinel and Splunk), orchestrates automation and response through SOAR, and registers every orchestration step in durable, queryable registries (Azure Data Lake, Elasticsearch, and Sentinel custom tables).

## Timeline

- **Days 1–30:** Foundation Build — ingestion pipeline + registry skeleton
- **Days 31–60:** Orchestration Pilot — enrichment, orchestrator, execution agents
- **Days 61–90:** Business Unit Enablement — hardening, BU onboarding, launch

## Stack

| Layer | Technology |
|---|---|
| SIEM | Microsoft Sentinel · Splunk Enterprise |
| SOAR | Splunk SOAR (PoC) |
| Bus | Azure Event Hubs (Kafka endpoint) |
| Agent Runtime | Azure Functions (Python 3.11) · Logic Apps |
| Hot Registry | Elasticsearch · Sentinel Custom Tables |
| Cold Registry | Azure Data Lake Gen2 (Parquet/Delta) |
| Identity | Entra ID Managed Identities |
| CI/CD | GitHub Actions / Azure DevOps |

## Architecture

See [`/architecture/readme.md`](architecture/readme.md) for the full Design Technical Plan (DTP).

## Context Engineering

See [`/context/readme.md`](context/readme.md) for the multi-agent context engineering layer that structures development across backend, frontend, data, QA, and operations domains.

## Guiding Principles

- **Ingest once, serve many** — raw logs enter one platform; all consumers read from it
- **API-first integration** — pull from SIEM/SOAR APIs over fan-out syslog sinks
- **Immutable audit by default** — every agent action appended to write-once storage
- **Least-privilege identity** — short-lived credentials per agent, scoped RBAC
- **Human-in-the-loop for risk** — high-impact actions require approval gate
- **Cost tiers match value** — hot index for ops queries; cold lake for compliance
