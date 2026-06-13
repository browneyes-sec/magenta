# Blob Storage Architecture & Sizing

## Component Overview

Magenta uses blob/object storage as its **Cold Registry** — the immutable, long-term archive for automation activity artifacts, evidence bundles, and raw alert payloads.

Current implementation: `data/lake/` with local filesystem (dev) → Azure Data Lake Gen2 / AWS S3 (prod).

## Partition Scheme

```
{mount}/magenta-lake/
├── raw-alerts/
│   └── {source}/
│       └── year={YYYY}/
│           └── month={MM}/
│               └── day={DD}/
│                   └── {alert_id}.json
├── activity/
│   └── year={YYYY}/
│       └── month={MM}/
│           └── day={DD}/
│               └── correlation_id={correlation_id}/
│                   ├── event.json
│                   ├── evidence.json
│                   └── artifacts/
├── missions/
│   └── year={YYYY}/
│       └── month={MM}/
│           └── {mission_id}/
│               ├── mission.json
│               ├── team.json
│               ├── timeline.json
│               └── artifact-bundle/
│                   ├── raw-alert.json
│                   ├── agent-reports/
│                   └── screenshots/
└── audit/
    └── year={YYYY}/
        └── month={MM}/
            └── {correlation_id}.parquet
```

## File Format Strategy

| Data Type | Format | Compression | Reason |
|---|---|---|---|
| Raw alerts / events | JSON | None (broker-native) | SIEM compatibility, human-readable |
| Activity records | Parquet | Snappy | Columnar, analytical queries, Delta Lake compat |
| Mission bundles | JSON | Gzip | Complex nested structure |
| Agent reports | Markdown / JSON | Gzip | Readability + parseability |
| Screenshots / evidence | PNG / PDF | Original | No transcoding |
| Audit aggregates | Parquet (Delta) | Snappy + ZSTD | ACID via Delta Lake, time-travel queries |

## Sizing Model

| Data Source | Volume per Day | Compression | Stored per Day | 30-Day Total | 1-Year Total |
|---|---|---|---|---|---|
| Raw alerts (200/day) | 10 MB | none | 10 MB | 300 MB | 3.6 GB |
| Activity events (2,000/day) | 20 MB | Snappy (Parquet) | 5 MB | 150 MB | 1.8 GB |
| Mission bundles (200/day) | 200 MB | Gzip | 50 MB | 1.5 GB | 18 GB |
| Agent logs (5,000/day) | 100 MB | Snappy (Parquet) | 25 MB | 750 MB | 9 GB |
| Audit (1,000/day) | 10 MB | Snappy (Delta) | 3 MB | 90 MB | 1.1 GB |
| **Total** | **340 MB** | | **93 MB** | **2.8 GB** | **33.5 GB** |

## Retention Tiering

| Tier | Duration | Storage Class | Access Pattern |
|---|---|---|---|
| Hot | 0-30 days | Standard / Hot | Operational queries, active missions |
| Warm | 31-90 days | Cool / Infrequent Access | Investigation lookback |
| Cold | 91-365 days | Cold / Archive | Compliance, audits, threat hunting |
| Frozen | > 365 days | Archive / Glacier | Legal hold, long-term analytics |

## Configuration

```yaml
lake:
  connection_string: "DefaultEndpointsProtocol=https;AccountName=magentalake;..."
  container: magenta-lake
  root: /data/magenta/lake
  parquet_compression: snappy
  retention_days: 365

  lifecycle_rules:
    - name: hot-to-cool
      after_days: 30
      tier: cool
    - name: cool-to-cold
      after_days: 90
      tier: cold
    - name: cold-to-frozen
      after_days: 365
      tier: archive
      delete_after_days: 2555  # 7 years
```

## Monitoring

| Metric | Alert |
|---|---|
| Storage consumed > 80% of budget | Warning |
| Upload failures > 1% | Warning |
| Tier transition errors > 0 | Investigate |
| Query access to frozen tier > 10/day | Consider policy change |
