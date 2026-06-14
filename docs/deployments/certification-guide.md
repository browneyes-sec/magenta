# GUI Integration Certification Guide

This guide certifies that the Magenta ASOAR Open WebUI integration layer
(per DTP v3.1) is correctly wired and operational.

## Certification Levels

| Level | Scope | When |
|---|---|---|
| **L1: Static** | File existence, imports, syntax | After every commit |
| **L2: Unit** | All 66+ tests pass | CI pipeline |
| **L3: Integration** | Docker stack boots, APIs respond | After `docker compose up` |
| **L4: E2E** | Operator can deploy agents and approve actions via Open WebUI | Release candidate |

---

## L1: Static Certification

Run the validation script:

```bash
python scripts/certify_integration.py
```

Expected output: `ALL CHECKS PASSED`

Checks performed:
- 31 new files exist with correct paths
- All Python modules import without errors
- Grafana dashboards are valid JSON
- Docker compose is valid YAML
- All 45 API routes contain expected new routes
- MCP tool definitions match expected count (26 tools across 6 servers)
- Pipeline Python files compile without syntax errors

## L2: Unit Certification

```bash
magenta state regression
```

Expected: `66 passed` (or current count)

Additional coverage:
```bash
# Verify directive telemetry fires without error
python -c "
from magenta.dictator.directives import DirectiveType, issue_directive
d = issue_directive(DirectiveType.system_command, 'certification-test', reason='certification')
print(f'Directive {d.directive_id} issued — telemetry OK')
"
```

## L3: Integration Certification

### Prerequisites
- Docker & Docker Compose v2
- 16GB+ RAM
- Magenta repo cloned and venv activated

### 3.1 Start the Stack

```bash
docker compose -f soa/docker/docker-compose.openwebui.yml up -d

# Wait 60s for OLLAMA to initialize
sleep 60

# Verify all 10 containers are running
docker compose -f soa/docker/docker-compose.openwebui.yml ps

# Expected: 10 services all showing "Up" or "healthy"
```

### 3.2 Verify Endpoints

```bash
# Open WebUI
curl -sf http://localhost:3000/health && echo " — Open WebUI OK"

# Grafana
curl -sf http://localhost:3001/api/health && echo " — Grafana OK"

# Prometheus
curl -sf http://localhost:9090/-/healthy && echo " — Prometheus OK"

# Pipeline endpoint
curl -sf http://localhost:9099/health && echo " — Pipelines OK"

# MCPO
curl -sf http://localhost:8001/health && echo " — MCPO OK"

# Magenta API (if running separately)
curl -sf http://localhost:8000/api/v1/health/ && echo " — Magenta API OK"
```

### 3.3 Verify API Routes

```bash
curl -s http://localhost:8000/openapi.json | python -c "
import json, sys
spec = json.load(sys.stdin)
paths = list(spec.get('paths', {}).keys())
new_routes = [p for p in paths if any(r in p for r in ['approvals', 'monitoring', 'instrumentation'])]
print(f'New integration routes: {len(new_routes)}')
for r in sorted(new_routes):
    print(f'  {r}')
"
```

### 3.4 Verify Telemetry Pipeline

```bash
# Issue a directive via CLI
magenta dictator directives --limit 5

# Check directive log
magenta dictator directives --limit 10 | python -m json.tool
```

### 3.5 Verify Approval Gate

```bash
# Trigger a high-risk action
python -c "
from magenta.response.executor import action_executor
from magenta.core.models import ActionType, Target, TargetType, AssetCriticality
import asyncio

async def test():
    result = await action_executor.execute(
        ActionType.isolate_host,
        Target(type=TargetType.host, id='test-vm-001', asset_criticality=AssetCriticality.critical),
        {'reason': 'certification test'},
    )
    print(f'Approval gate response: {result}')

asyncio.run(test())
"
# Expected: {"status": "pending_approval", "approval_id": "..."}
```

### 3.6 Verify MCP Server Registration

```bash
# Check MCP tools are discoverable
curl -s http://localhost:8001/tools | python -c "
import json, sys
tools = json.load(sys.stdin)
print(f'Available MCP tools: {len(tools)}')
for t in tools[:5]:
    print(f'  - {t[\"name\"]}: {t[\"description\"][:60]}')
"
```

### 3.7 Verify Grafana Dashboards

```bash
# Dashboards should be provisioned
curl -s http://localhost:3001/api/search | python -c "
import json, sys
dashboards = json.load(sys.stdin)
print(f'Provisioned dashboards: {len(dashboards)}')
for d in dashboards:
    print(f'  - {d[\"title\"]}')
"
# Expected: magento-asoar-ops, magento-threat-blue, openwebui-usage
```

## L4: End-to-End Certification

### 4.1 Operator Can Log In
1. Open http://localhost:3000
2. Complete admin setup (first login)
3. Verify model list shows `qwen2.5:7b` (or pulled models)

### 4.2 Operator Can Issue Dictator Commands
1. In Open WebUI chat, type: `dictator_status`
2. Expected: JSON response with framework status

### 4.3 Operator Can Deploy an Agent
1. In Open WebUI, type: `dictator_deploy triage`
2. Expected: Agent deployed confirmation with agent_id

### 4.4 Operator Can Review Approvals
1. Type: `approval_card`
2. If pending approvals exist: interactive card with Approve/Deny buttons
3. If no pending approvals: "No Pending Approvals" message

### 4.5 Operator Can Generate Artifacts
1. Type: `generate_artifact mission_throughput`
2. Expected: HTML card with active/completed mission counts
3. Type: `generate_artifact directive_timeline`
4. Expected: Table of recent directives

### 4.6 Operator Can Run Probes
```bash
# Via Open Terminal (http://localhost:8082)
magenta state probe

# Expected: Dictator probe returns healthy status
```

### 4.7 Grafana Dashboards Render
1. Open http://localhost:3001
2. Browse to "Magenta ASOAR — Operations"
3. Verify panels render (may take 5-10 min for data to appear)

## Certification Sign-off

| Level | Date | Tester | Result |
|---|---|---|---|
| L1: Static | | | PASS / FAIL |
| L2: Unit | | | PASS / FAIL |
| L3: Integration | | | PASS / FAIL |
| L4: E2E | | | PASS / FAIL |

**Overall Certification: PASS / FAIL**

Notes:
- Shadow mode: approvals are logged but not enforced during pilot
- Connectors (Sentinel/Entra/Defender) return "not configured" until credentials are provided
- OLLAMA must have at least one model pulled (`docker exec magenta-ollama ollama pull qwen2.5:7b`)
