# ADR-011: Telemetry Collection Plane

**Status:** Accepted  
**Date:** 2026-06-15  
**Authors:** Platform Architecture Team  
**Deciders:** Platform Architecture, Security, Engineering  

---

## Context

Magenta ASOAR currently ingests security alerts via SIEM-native APIs (Sentinel Incidents, Splunk fired alerts) — this is sufficient for **alert-driven ASOAR** but insufficient for **investigation-driven ASOAR**:

- Agents lack access to raw endpoint logs (Windows Event, Linux syslog) for investigation context.
- Cloud audit logs (Azure Activity, AWS CloudTrail, GCP Cloud Logging) arrive only if already in Sentinel Log Analytics — bypassing the Magenta mesh for cross-cloud correlation.
- The ADR-010 vectorized data mesh exists (`architecture/data-mesh/readme.md`) with Qdrant, OLLAMA, and a mesh gateway, but the pipeline has no raw-log source — it only ingests SIEM alerts and agent memories.
- Customer/partner logs (SFTP drops, HTTPS pushes) have no defined ingestion path.

The Data Transport Protocol (§2.1) principle *ingest once, serve many* demands a single collection plane feeding the same bus and mesh, not parallel silos.

A **SIEM-first architecture** was considered (keep raw logs in existing SIEM, query via KQL/Search on demand) but rejected because:
1. Log volume would inflate SIEM licensing costs.
2. Cross-cloud correlation would require multiple SIEM connectors.
3. Agent retrieval latency from SIEM APIs is unpredictable (>5s P95).

---

## Decision

Add a **three-tier Telemetry Collection Plane** as a new architectural layer:

```
Tier 1 — SIEM-Native (existing, extended)
  Sentinel Incidents API, Splunk fired alerts → raw-alerts

Tier 2 — Cloud Log Analytics (new)
  Azure Monitor DCR, AWS CloudTrail, GCP Cloud Logging → raw-logs

Tier 3 — Endpoint / Customer Collection (new)
  Windows (WAC/WinRM-SSL), Linux (Fluent Bit/SFTP),
  Customer file drops (SFTP/HTTPS) → raw-logs
```

### Key design rules

1. **One bus, two lanes.** The existing Event Hubs topology gets a `raw-logs` topic alongside `raw-alerts`. Both feed into the normalizer, but with different schemas and consumer groups.

2. **No topic rename.** The plan considered renaming `enriched-alerts` → `enriched-events` to generalize it for both alerts and logs. This is rejected as a breaking change with no migration benefit. Instead, the normalizer emits two distinct schemas on separate topics:
   - `enriched-alerts` — `automation.activity` (existing, unchanged)
   - `enriched-events` — `security.event` (new, log-specific)

3. **Normalizer split.** Two normalization paths:
   - `raw-alerts → Normalizer → enriched-alerts` (existing `automation.activity` schema)
   - `raw-logs → Log Normalizer → enriched-events` (new `security.event` schema)

4. **Vectorizer ingests both.** The ADR-010 vectorization pipeline consumes `enriched-events` for endpoint/cloud context and `enriched-alerts` for SIEM context, storing in the same Qdrant mesh with distinct product prefixes.

5. **Ingest API as the universal collector endpoint.** `POST /ingest/v1/logs` with mTLS/HMAC auth is the recommended path for Tier 3 collectors. SFTP/FTPS staging is a fallback for air-gapped sources.

6. **Per-collector managed identity.** No shared service accounts. Each collector gets an Azure Managed Identity / AWS IAM Role with scoped RBAC — aligned with ADR-005 per-provider module pattern.

7. **All TLS, no plaintext.** Reject FTP, WinRM HTTP (5985), unencrypted syslog. Minimum TLS 1.2, prefer TLS 1.3. Field-level redaction via `magenta/gateway/redact.py` before embedding.

---

## Consequences

### Positive

- Agents gain raw log context for investigation (endpoint.*, cloud.* products).
- Cross-cloud log correlation flows through a single mesh query.
- Collector topology is documented and repeatable via TCF planning gates.
- No SIEM licensing cost increase for log retention.
- Existing alert pipeline (`raw-alerts → enriched-alerts`) is untouched — zero regression risk.

### Negative

- New operational surface: collector deployment, TLS certificate rotation, SFTP key management.
- Log volume could be 10-100x alert volume — requires tiered vectorization (only security-relevant channels + BM25 pre-filter).
- Windows collection via WAC/WinRM-SSL introduces domain-joined dependencies not present in the current cloud-native architecture.

### Mitigations

- **Volume**: Chunk strategy (512 tokens, 64 overlap) + `idempotency_key` dedup in Log Normalizer + sensitivity-based routing (HIGH → local OLLAMA only).
- **Windows**: Prefer Azure Monitor Agent (AMA) where possible; WAC is the documented fallback with DMZ collector zone isolation.
- **RDP**: Explicitly excluded as a log transport path — documented as break-glass human access only.
- **PII**: Redact before embed via existing `redact.py` pipeline.

---

## Compliance

| ADR-011 Provision | ADR-010 (Data Mesh) | ADR-003 (TOML) | ADR-005 (Per-Provider) | ADR-009 (Network) |
|---|---|---|---|---|
| raw-logs topic on Event Hubs | Extends §2 Source Domains | Topic config in TOML | Event Hubs per provider | Traffic via hub |
| security.event schema | Extends §3 product catalog | Schema ref in TOML | — | — |
| Per-collector identity | — | Provider config in TOML | New module: `collectors/` | DMZ collector zone |
| Endpoint/cloud mesh products | Extends §3 catalog | Product def in TOML | — | — |

---

## Implementation

See `architecture/frameworks/telemetry-collection-framework.md` for detailed planning gates (6-gate source onboarding process).

Phased buildout:
- **Phase 0** — This ADR + TCF doc + extended resource docs
- **Phase 1** — Event Hubs client (real impl), ingest API, Log Normalizer
- **Phase 2** — Cloud connectors (Azure DCR, AWS CloudTrail, GCP Cloud Logging)
- **Phase 3** — Endpoint collectors (Linux Fluent Bit, Windows WAC, customer SFTP/HTTPS)
- **Phase 4** — Vectorization pipeline for log products
- **Phase 5** — Registry agent dual-write + collector Grafana panels
