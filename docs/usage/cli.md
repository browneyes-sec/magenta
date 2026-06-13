# CLI Usage for Production Deployment

## Overview

The Magenta CLI exposes five command groups for operations, automation, and management. Built with Typer and Rich for structured output.

```bash
magenta --help
```

```
Usage: magenta [OPTIONS] COMMAND [ARGS]...

  Agentic System Orchestration Automation and Response (ASOAR)

Options:
  -c, --config FILE    Path to config file
  -e, --env TEXT       Environment (dev/staging/prod) [default: dev]
  -v, --verbose        Verbose output
  -f, --format TEXT    Output format (text/json) [default: text]
  --version            Show version
  --help               Show this message

Commands:
  orchestrate  Manage missions, swarms, and orchestration lifecycle
  automate     Manage playbooks, rules, and automation triggers
  response     Manage incidents, response actions, and approvals
  health       System health checks for agents, models, and storage
  lab          Simulation, testing, model comparison, and evaluation
```

## Configuration Precedence

```
CLI flags > Environment variables > Config file > Defaults
```

```bash
# Config file
magenta -c /etc/magenta/prod.yaml orchestrate list

# Environment override
MAGENTA_ENV=prod MAGENTA_SQL__URL="postgresql+asyncpg://..." magenta health
```

## Production Profiles

```yaml
# config/prod.yaml
env: prod
verbose: false

sql:
  url: postgresql+asyncpg://magenta:${DB_PASSWORD}@pg-cluster:5432/magenta
  pool_size: 20

elastic:
  hosts:
    - https://es-node1:9200
    - https://es-node2:9200
  username: magenta-sa
  password: ${ES_PASSWORD}

models:
  default_provider: ollama
  ollama_host: http://ollama-cluster:11434
```

## Command Groups

### orchestrate

```bash
# List active missions
magenta orchestrate list --status executing

# List in JSON format (for scripting)
magenta orchestrate list --format json

# Get mission details
magenta orchestrate get 550e8400-e29b-41d4-a716-446655440000

# Create and start a mission
magenta orchestrate create --alert-id sentinel-8932 --source sentinel
magenta orchestrate start 550e8400-e29b-41d4-a716-446655440000

# Stop a mission
magenta orchestrate stop 550e8400-e29b-41d4-a716-446655440000

# Stream mission logs
magenta orchestrate logs 550e8400-e29b-41d4-a716-446655440000 --tail 500 --follow
```

### automate

```bash
# List playbooks
magenta automate playbook list
magenta automate playbook list --tag ransomware

# Validate playbook
magenta automate playbook validate --file playbooks/phishing.yaml

# Register playbook
magenta automate playbook register --file playbooks/phishing.yaml

# List automation rules
magenta automate rule list
```

### response

```bash
# List pending approvals
magenta response approval list

# Approve/reject an action
magenta response approval approve 550e8400-e29b-41d4-a716-446655440000
magenta response approval reject 550e8400-e29b-41d4-a716-446655440000 --reason "Manual review needed"

# List incidents
magenta response incident list
magenta response incident get sentinel-incident-8932
```

### health

```bash
# Full system health
magenta health

# Component health
magenta health agents
magenta health models
magenta health pipeline
magenta health storage

# Output JSON for monitoring
magenta health --format json
```

### lab

```bash
# Simulate an alert through the pipeline
magenta lab simulate --file test-alert.json

# Evaluate agent prompt
magenta lab evaluate --agent triage --test-suite tests/prompts/triage.json

# Compare model outputs
magenta lab compare --prompt "Classify: failed login from admin" --models qwen2.5:7b,mistral:7b
```

## Automation Scripting

```bash
#!/bin/bash
# cron-magenta-health.sh — run every 5 minutes

if ! magenta health --format json | python3 -c "
import sys, json
status = json.load(sys.stdin)['status']
sys.exit(0 if status == 'healthy' else 1)
"; then
    curl -X POST -H "Content-Type: application/json" \
        -d '{"text": "Magenta health check FAILED"}' \
        https://hooks.slack.com/services/...
fi
```

```python
"""Python automation: watch missions and escalate long-running ones."""
import subprocess, json

missions = json.loads(
    subprocess.check_output(["magenta", "orchestrate", "list", "--format", "json"])
)

for m in missions:
    if m["status"] == "executing":
        elapsed = (datetime.utcnow() - datetime.fromisoformat(m["created_at"])).seconds
        if elapsed > 1800:  # 30 minutes
            subprocess.run(["magenta", "orchestrate", "stop", m["mission_id"]])
```

## Structured Output (JSON)

All commands support `--format json` for machine parsing:

```bash
$ magenta orchestrate list --status executing --format json
[
  {
    "mission_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "executing",
    "alert_id": "sentinel-incident-8932",
    "severity": 4,
    "tasks": 3,
    "team_size": 2,
    "created_at": "2026-06-13T14:00:00+00:00"
  }
]
```

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 3 | Connection error (database, model, SIEM) |
| 4 | Authentication error |
| 5 | Resource not found |
