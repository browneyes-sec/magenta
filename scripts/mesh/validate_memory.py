#!/usr/bin/env python3
"""Operational memory validation script.

Checks:
  1. Qdrant connection health
  2. Collection existence and vector counts
  3. Embedding model availability (bge-m3 via OLLAMA)
  4. Write → Read round-trip latency
  5. Schema compliance (tenant_id, memory_type fields)
  6. Drift detection (embedding dimension mismatch)
  7. Retention policy enforcement

Usage:
    python scripts/mesh/validate_memory.py --env prod --output json
    python scripts/mesh/validate_memory.py --env dev --verbose
    python scripts/mesh/validate_memory.py --env dev --write-test  # runs write/read round-trip
"""

import argparse
import json
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum

import httpx


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    PASS = "pass"


@dataclass
class CheckResult:
    name: str
    severity: Severity
    message: str
    details: dict = field(default_factory=dict)
    latency_ms: float = 0.0


@dataclass
class ValidationReport:
    environment: str
    timestamp: str
    checks: list[CheckResult] = field(default_factory=list)
    overall_status: str = "unknown"

    def add(self, check: CheckResult):
        self.checks.append(check)

    def finalize(self):
        criticals = sum(1 for c in self.checks if c.severity == Severity.CRITICAL)
        warnings = sum(1 for c in self.checks if c.severity == Severity.WARNING)
        if criticals > 0:
            self.overall_status = "FAIL"
        elif warnings > 0:
            self.overall_status = "DEGRADED"
        else:
            self.overall_status = "HEALTHY"

    def to_dict(self):
        return {
            "environment": self.environment,
            "timestamp": self.timestamp,
            "overall_status": self.overall_status,
            "summary": {
                "total": len(self.checks),
                "pass": sum(1 for c in self.checks if c.severity == Severity.PASS),
                "warnings": sum(1 for c in self.checks if c.severity == Severity.WARNING),
                "critical": sum(1 for c in self.checks if c.severity == Severity.CRITICAL),
            },
            "checks": [asdict(c) for c in self.checks],
        }


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

EXPECTED_COLLECTIONS = {
    "mem_episodic": {"dim": 768, "metric": "cosine"},
    "mem_semantic": {"dim": 768, "metric": "cosine"},
    "mem_procedural": {"dim": 768, "metric": "cosine"},
}

REQUIRED_FIELDS = [
    "text",
    "agent_role",
    "mission_id",
    "tenant_id",
    "memory_type",
    "created_at",
    "source_tool",
]


def check_qdrant_health(base_url: str, report: ValidationReport):
    """Check Qdrant is reachable and healthy."""
    start = time.time()
    try:
        r = httpx.get(f"{base_url}/healthz", timeout=5.0)
        latency = (time.time() - start) * 1000
        if r.status_code == 200:
            report.add(
                CheckResult(
                    name="qdrant_health",
                    severity=Severity.PASS,
                    message=f"Qdrant healthy at {base_url}",
                    latency_ms=round(latency, 1),
                )
            )
        else:
            report.add(
                CheckResult(
                    name="qdrant_health",
                    severity=Severity.CRITICAL,
                    message=f"Qdrant returned {r.status_code}",
                    latency_ms=round(latency, 1),
                )
            )
    except Exception as e:
        latency = (time.time() - start) * 1000
        report.add(
            CheckResult(
                name="qdrant_health",
                severity=Severity.CRITICAL,
                message=f"Qdrant unreachable: {e}",
                latency_ms=round(latency, 1),
            )
        )


def check_collections(base_url: str, report: ValidationReport):
    """Verify all expected collections exist with correct config."""
    start = time.time()
    try:
        r = httpx.get(f"{base_url}/collections", timeout=10.0)
        # Qdrant returns {result: {collections: [...]}}
        collections = {c["name"]: c for c in r.json().get("result", {}).get("collections", [])}
        latency = (time.time() - start) * 1000

        for name, expected in EXPECTED_COLLECTIONS.items():
            if name not in collections:
                report.add(
                    CheckResult(
                        name=f"collection_{name}",
                        severity=Severity.CRITICAL,
                        message=f"Missing collection: {name}",
                    )
                )
                continue

            # Get detailed collection info for vector config
            try:
                r2 = httpx.get(f"{base_url}/collections/{name}", timeout=10.0)
                col_info = r2.json().get("result", {})
                vectors_config = col_info.get("config", {}).get("params", {}).get("vectors", {})
                actual_dim = vectors_config.get("size")
                actual_metric = vectors_config.get("distance")
            except Exception:
                actual_dim = None
                actual_metric = None

            issues = []
            if actual_dim != expected["dim"]:
                issues.append(f"dim={actual_dim} (expected {expected['dim']})")
            if actual_metric and actual_metric.lower() != expected["metric"].lower():
                issues.append(f"metric={actual_metric} (expected {expected['metric']})")

            if issues:
                report.add(
                    CheckResult(
                        name=f"collection_{name}_config",
                        severity=Severity.WARNING,
                        message=f"Config mismatch: {'; '.join(issues)}",
                        details={"actual_dim": actual_dim, "actual_metric": actual_metric},
                    )
                )
            else:
                report.add(
                    CheckResult(
                        name=f"collection_{name}_config",
                        severity=Severity.PASS,
                        message=f"{name}: dim={actual_dim}, metric={actual_metric}",
                    )
                )

        report.add(
            CheckResult(
                name="collections_list",
                severity=Severity.INFO,
                message=f"Found {len(collections)} collections",
                latency_ms=round(latency, 1),
            )
        )

    except Exception as e:
        report.add(
            CheckResult(
                name="collections_list",
                severity=Severity.CRITICAL,
                message=f"Failed to list collections: {e}",
            )
        )


def check_vector_counts(base_url: str, report: ValidationReport):
    """Check vector counts per collection."""
    for name in EXPECTED_COLLECTIONS:
        try:
            r = httpx.get(f"{base_url}/collections/{name}", timeout=10.0)
            info = r.json().get("result", {})
            points_count = info.get("points_count", 0)
            status = info.get("status", "unknown")

            severity = Severity.PASS
            if status != "green":
                severity = Severity.WARNING
            if points_count == 0:
                severity = Severity.WARNING

            report.add(
                CheckResult(
                    name=f"vector_count_{name}",
                    severity=severity,
                    message=f"{name}: {points_count} vectors, status={status}",
                    details={"count": points_count, "status": status},
                )
            )
        except Exception as e:
            report.add(
                CheckResult(
                    name=f"vector_count_{name}",
                    severity=Severity.WARNING,
                    message=f"Could not check {name}: {e}",
                )
            )


def check_embedding_model(ollama_url: str, report: ValidationReport):
    """Verify bge-m3 embedding model is available."""
    start = time.time()
    try:
        r = httpx.get(f"{ollama_url}/api/tags", timeout=5.0)
        latency = (time.time() - start) * 1000
        models = [m["name"] for m in r.json().get("models", [])]

        if any("nomic-embed-text" in m for m in models):
            report.add(
                CheckResult(
                    name="embedding_model",
                    severity=Severity.PASS,
                    message="nomic-embed-text model available",
                    latency_ms=round(latency, 1),
                )
            )
        else:
            report.add(
                CheckResult(
                    name="embedding_model",
                    severity=Severity.CRITICAL,
                    message=f"nomic-embed-text not found. Available: {models}",
                    latency_ms=round(latency, 1),
                )
            )
    except Exception as e:
        report.add(
            CheckResult(
                name="embedding_model",
                severity=Severity.WARNING,
                message=f"Could not check OLLAMA: {e}",
                latency_ms=round(time.time() - start) * 1000,
            )
        )


def check_write_read_roundtrip(qdrant_url: str, ollama_url: str, report: ValidationReport):
    """Write a test vector, search it, verify round-trip."""
    test_text = f"operational validation test {int(time.time())}"
    test_payload = {
        "text": test_text,
        "agent_role": "validator",
        "mission_id": "ops-validation",
        "tenant_id": "ops-test",
        "memory_type": "episodic",
        "source_tool": "validate_memory.py",
        "created_at": int(time.time() * 1000),
    }

    # Step 1: Generate embedding
    try:
        embed_start = time.time()
        r = httpx.post(
            f"{ollama_url}/api/embed",
            json={
                "model": "nomic-embed-text",
                "input": test_text,
            },
            timeout=15.0,
        )
        embed_latency = (time.time() - embed_start) * 1000
        embedding = r.json()["embeddings"][0]
    except Exception as e:
        report.add(
            CheckResult(
                name="roundtrip_embed",
                severity=Severity.CRITICAL,
                message=f"Embedding generation failed: {e}",
            )
        )
        return

    # Step 2: Write to Qdrant
    write_start = time.time()
    test_id = str(uuid.uuid4())
    try:
        r = httpx.put(
            f"{qdrant_url}/collections/mem_episodic/points",
            json={
                "points": [
                    {
                        "id": test_id,
                        "vector": embedding,
                        "payload": test_payload,
                    }
                ]
            },
            timeout=10.0,
        )
        write_latency = (time.time() - write_start) * 1000
        if r.status_code != 200:
            raise Exception(f"Write returned {r.status_code}: {r.text}")
    except Exception as e:
        report.add(
            CheckResult(
                name="roundtrip_write",
                severity=Severity.CRITICAL,
                message=f"Write failed: {e}",
                latency_ms=round(write_latency, 1),
            )
        )
        return

    # Step 3: Search for it
    search_start = time.time()
    try:
        r = httpx.post(
            f"{qdrant_url}/collections/mem_episodic/points/search",
            json={
                "vector": embedding,
                "limit": 1,
                "with_payload": True,
            },
            timeout=10.0,
        )
        search_latency = (time.time() - search_start) * 1000
        results = r.json().get("result", [])
        if results and results[0]["id"] == test_id:
            total_latency = (time.time() - embed_start) * 1000
            report.add(
                CheckResult(
                    name="roundtrip_full",
                    severity=Severity.PASS,
                    message="Write→Search round-trip OK",
                    details={
                        "embed_ms": round(embed_latency, 1),
                        "write_ms": round(write_latency, 1),
                        "search_ms": round(search_latency, 1),
                        "total_ms": round(total_latency, 1),
                    },
                    latency_ms=round(total_latency, 1),
                )
            )
        else:
            report.add(
                CheckResult(
                    name="roundtrip_search",
                    severity=Severity.CRITICAL,
                    message="Written point not found in search results",
                )
            )
    except Exception as e:
        report.add(
            CheckResult(
                name="roundtrip_search",
                severity=Severity.CRITICAL,
                message=f"Search failed: {e}",
                latency_ms=round(search_latency, 1),
            )
        )

    # Cleanup: delete test point
    try:
        httpx.post(
            f"{qdrant_url}/collections/episodic_memory/points/delete",
            json={"points": [test_id]},
            timeout=5.0,
        )
    except Exception:
        pass  # best-effort cleanup


def check_schema_compliance(qdrant_url: str, report: ValidationReport):
    """Sample points and verify required fields exist."""
    for name in EXPECTED_COLLECTIONS:
        try:
            r = httpx.post(
                f"{qdrant_url}/collections/{name}/points/scroll",
                json={"limit": 10, "with_payload": True},
                timeout=10.0,
            )
            points = r.json().get("result", {}).get("points", [])
            if not points:
                report.add(
                    CheckResult(
                        name=f"schema_{name}",
                        severity=Severity.INFO,
                        message=f"{name}: no points to validate",
                    )
                )
                continue

            missing_fields = {f: 0 for f in REQUIRED_FIELDS}
            for pt in points:
                payload = pt.get("payload", {})
                for f in REQUIRED_FIELDS:
                    if f not in payload or payload[f] is None:
                        missing_fields[f] += 1

            issues = {f: c for f, c in missing_fields.items() if c > 0}
            if issues:
                report.add(
                    CheckResult(
                        name=f"schema_{name}",
                        severity=Severity.WARNING,
                        message=f"{name}: missing fields in {issues}",
                        details={"missing": issues, "sample_size": len(points)},
                    )
                )
            else:
                report.add(
                    CheckResult(
                        name=f"schema_{name}",
                        severity=Severity.PASS,
                        message=f"{name}: all required fields present ({len(points)} points)",
                    )
                )
        except Exception as e:
            report.add(
                CheckResult(
                    name=f"schema_{name}",
                    severity=Severity.WARNING,
                    message=f"Could not validate schema for {name}: {e}",
                )
            )


def check_retention(qdrant_url: str, max_age_days: int, report: ValidationReport):
    """Check if any points exceed retention policy."""
    cutoff_ms = int((time.time() - max_age_days * 86400) * 1000)
    for name in EXPECTED_COLLECTIONS:
        try:
            r = httpx.post(
                f"{qdrant_url}/collections/{name}/points/scroll",
                json={
                    "limit": 1000,
                    "with_payload": True,
                    "filter": {"must": [{"key": "created_at", "range": {"lt": cutoff_ms}}]},
                },
                timeout=15.0,
            )
            expired = len(r.json().get("result", {}).get("points", []))
            if expired > 0:
                report.add(
                    CheckResult(
                        name=f"retention_{name}",
                        severity=Severity.WARNING,
                        message=f"{name}: {expired} points older than {max_age_days} days",
                        details={"expired_count": expired, "max_age_days": max_age_days},
                    )
                )
            else:
                report.add(
                    CheckResult(
                        name=f"retention_{name}",
                        severity=Severity.PASS,
                        message=f"{name}: no points older than {max_age_days} days",
                    )
                )
        except Exception as e:
            report.add(
                CheckResult(
                    name=f"retention_{name}",
                    severity=Severity.WARNING,
                    message=f"Could not check retention for {name}: {e}",
                )
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

ENVIRONMENTS = {
    "dev": {
        "qdrant": "http://localhost:6333",
        "ollama": "http://localhost:11434",
        "max_age_days": 7,
    },
    "staging": {
        "qdrant": "http://qdrant-staging:6333",
        "ollama": "http://ollama-staging:11434",
        "max_age_days": 30,
    },
    "prod": {
        "qdrant": "http://qdrant-prod:6333",
        "ollama": "http://ollama-prod:11434",
        "max_age_days": 90,
    },
}


def main():
    parser = argparse.ArgumentParser(description="Validate memory infrastructure")
    parser.add_argument("--env", choices=ENVIRONMENTS.keys(), default="dev")
    parser.add_argument("--output", choices=["json", "text"], default="text")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--write-test", action="store_true", help="Run write/read round-trip test")
    parser.add_argument("--qdrant-url", help="Override Qdrant URL")
    parser.add_argument("--ollama-url", help="Override OLLAMA URL")
    parser.add_argument("--max-age-days", type=int, help="Override retention check")
    args = parser.parse_args()

    config = ENVIRONMENTS[args.env]
    qdrant_url = args.qdrant_url or config["qdrant"]
    ollama_url = args.ollama_url or config["ollama"]
    max_age_days = args.max_age_days or config["max_age_days"]

    import datetime

    report = ValidationReport(
        environment=args.env,
        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
    )

    print(f"\n{'=' * 60}")
    print(f"  Memory Infrastructure Validation — {args.env.upper()}")
    print(f"{'=' * 60}\n")

    # Run checks
    check_qdrant_health(qdrant_url, report)
    check_collections(qdrant_url, report)
    check_vector_counts(qdrant_url, report)
    check_embedding_model(ollama_url, report)
    check_schema_compliance(qdrant_url, report)
    check_retention(qdrant_url, max_age_days, report)
    if args.write_test:
        check_write_read_roundtrip(qdrant_url, ollama_url, report)

    report.finalize()

    # Output
    if args.output == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        for check in report.checks:
            icon = {
                Severity.PASS: "\u2705",
                Severity.WARNING: "\u26a0\ufe0f",
                Severity.CRITICAL: "\u274c",
                Severity.INFO: "\u2139\ufe0f",
            }[check.severity]
            latency = f" ({check.latency_ms}ms)" if check.latency_ms else ""
            print(f"  {icon} {check.name}: {check.message}{latency}")
            if args.verbose and check.details:
                for k, v in check.details.items():
                    print(f"      {k}: {v}")

        print(f"\n{'=' * 60}")
        print(f"  Overall: {report.overall_status}")
        summary = report.to_dict()["summary"]
        print(
            f"  Pass: {summary['pass']}  Warn: {summary['warnings']}  Critical: {summary['critical']}"
        )
        print(f"{'=' * 60}\n")

    sys.exit(0 if report.overall_status == "HEALTHY" else 1)


if __name__ == "__main__":
    main()
