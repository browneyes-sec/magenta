#!/usr/bin/env python3
"""Smoke test for staging deployment validation.

Usage:
    python scripts/smoke_test_staging.py --url https://staging-api.example.com --api-key <key>

Exit codes:
    0 - All smoke tests passed
    1 - One or more smoke tests failed
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def api_get(base_url: str, path: str, api_key: str) -> dict:
    """Make GET request to API."""
    url = f"{base_url.rstrip('/')}{path}"
    req = Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        return {"error": str(e), "status_code": e.code}
    except URLError as e:
        return {"error": str(e), "status_code": 0}


def api_post(base_url: str, path: str, data: dict, api_key: str) -> dict:
    """Make POST request to API."""
    url = f"{base_url.rstrip('/')}{path}"
    req = Request(
        url,
        data=json.dumps(data).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        return {"error": str(e), "status_code": e.code}
    except URLError as e:
        return {"error": str(e), "status_code": 0}


def smoke_test_health(base_url: str, api_key: str) -> bool:
    """Test 1: Health endpoint returns healthy."""
    print("  [1/6] Testing /api/v1/health...", end=" ")
    result = api_get(base_url, "/api/v1/health", api_key)
    if result.get("status") == "healthy":
        print("PASS")
        return True
    print(f"FAIL - {result}")
    return False


def smoke_test_metrics(base_url: str, api_key: str) -> bool:
    """Test 2: Metrics endpoint returns workflow data."""
    print("  [2/6] Testing /api/v1/metrics...", end=" ")
    result = api_get(base_url, "/api/v1/metrics", api_key)
    if "workflows" in result or "magenta_" in str(result):
        print("PASS")
        return True
    print(f"FAIL - {result}")
    return False


def smoke_test_list_playbooks(base_url: str, api_key: str) -> bool:
    """Test 3: List playbooks returns array."""
    print("  [3/6] Testing /api/v1/workflows/playbooks...", end=" ")
    result = api_get(base_url, "/api/v1/workflows/playbooks", api_key)
    if isinstance(result, list):
        print(f"PASS ({len(result)} playbooks)")
        return True
    print(f"FAIL - {result}")
    return False


def smoke_test_list_subgraphs(base_url: str, api_key: str) -> bool:
    """Test 4: List subgraphs returns subgraphs."""
    print("  [4/6] Testing /api/v1/workflows/subgraphs/list...", end=" ")
    result = api_get(base_url, "/api/v1/workflows/subgraphs/list", api_key)
    if "subgraphs" in result:
        print(f"PASS ({len(result['subgraphs'])} subgraphs)")
        return True
    print(f"FAIL - {result}")
    return False


def smoke_test_execute_workflow(base_url: str, api_key: str) -> bool:
    """Test 5: Execute workflow returns mission_id."""
    print("  [5/6] Testing workflow execution...", end=" ")
    result = api_post(
        base_url,
        "/api/v1/workflows/execute",
        {
            "playbook_path": "magenta/workflows/examples/phishing-investigation.yaml",
            "alert_id": f"smoke-test-{int(time.time())}",
            "source_system": "sentinel",
        },
        api_key,
    )
    if "mission_id" in result and result.get("status") == "accepted":
        mission_id = result["mission_id"]
        print(f"PASS (mission_id={mission_id})")
        return True
    print(f"FAIL - {result}")
    return False


def smoke_test_workflow_status(base_url: str, api_key: str) -> bool:
    """Test 6: Get workflow status after execution."""
    print("  [6/6] Testing workflow status...", end=" ")
    # First execute to get a mission_id
    exec_result = api_post(
        base_url,
        "/api/v1/workflows/execute",
        {
            "playbook_path": "magenta/workflows/examples/phishing-investigation.yaml",
            "alert_id": f"smoke-status-{int(time.time())}",
            "source_system": "sentinel",
        },
        api_key,
    )
    if "mission_id" not in exec_result:
        print("SKIP (no mission_id from execution)")
        return True  # Non-critical

    mission_id = exec_result["mission_id"]
    time.sleep(0.5)  # Brief wait for async execution
    result = api_get(base_url, f"/api/v1/workflows/{mission_id}/status", api_key)
    if "status" in result:
        print(f"PASS (status={result['status']})")
        return True
    print(f"FAIL - {result}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Staging smoke tests")
    parser.add_argument("--url", required=True, help="Staging API base URL")
    parser.add_argument("--api-key", required=True, help="API key for authentication")
    args = parser.parse_args()

    print(f"\n{'=' * 60}")
    print("MAGENTA STAGING SMOKE TESTS")
    print(f"{'=' * 60}")
    print(f"Target: {args.url}\n")

    tests = [
        ("Health Check", smoke_test_health),
        ("Metrics Endpoint", smoke_test_metrics),
        ("List Playbooks", smoke_test_list_playbooks),
        ("List Subgraphs", smoke_test_list_subgraphs),
        ("Execute Workflow", smoke_test_execute_workflow),
        ("Workflow Status", smoke_test_workflow_status),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            if test_fn(args.url, args.api_key):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ERROR - {name}: {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"RESULTS: {passed} passed, {failed} failed")
    print(f"{'=' * 60}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
