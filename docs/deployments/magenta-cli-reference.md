# Magenta CLI Reference

**Command:** `magenta`
**Syntax:** `magenta <command> [OPTIONS] --flag`
**Version:** 1.0

---

## Global Options

| Flag | Short | Description |
|---|---|---|
| `--config` | `-c` | Path to config file (default: `config/default.yaml`) |
| `--env` | `-e` | Environment: `dev`, `staging`, `prod` (default: `dev`) |
| `--verbose` | `-v` | Verbose output |
| `--quiet` | `-q` | Suppress non-error output |
| `--format` | `-f` | Output format: `text`, `json` (default: `text`) |
| `--help` | | Show help message |

---

## `magenta orchestrate`

Mission and swarm lifecycle management.

### `magenta orchestrate start <playbook>`

Start a new mission from a playbook file.

```bash
magenta orchestrate start config/playbooks/phishing.yaml
magenta orchestrate start config/playbooks/phishing.yaml --params '{"severity":"high"}'
magenta orchestrate start sentinel-incident-8932 --from-incident
```

**Options:**
| Flag | Description |
|---|---|
| `--params` | JSON string of mission parameters |
| `--from-incident` | Treat `<playbook>` as an incident ID |
| `--dry-run` | Validate without executing |
| `--wait` | Block until mission completes |

### `magenta orchestrate stop <mission_id>`

Stop a running mission.

```bash
magenta orchestrate stop mission-8932
magenta orchestrate stop mission-8932 --force
```

**Options:**
| Flag | Description |
|---|---|
| `--force` | Force stop without graceful shutdown |

### `magenta orchestrate status <mission_id>`

Show mission status and agent assignments.

```bash
magenta orchestrate status mission-8932
magenta orchestrate status mission-8932 --watch
```

**Options:**
| Flag | Description |
|---|---|
| `--watch` | Continuously watch status updates |

### `magenta orchestrate list`

List all missions.

```bash
magenta orchestrate list
magenta orchestrate list --status active
magenta orchestrate list --limit 20 --format json
```

**Options:**
| Flag | Description |
|---|---|
| `--status` | Filter: `active`, `completed`, `failed`, `all` |
| `--limit` | Max results (default: 50) |
| `--agent` | Filter by agent role |

### `magenta orchestrate logs <mission_id>`

View mission execution logs.

```bash
magenta orchestrate logs mission-8932
magenta orchestrate logs mission-8932 --tail 50
magenta orchestrate logs mission-8932 --level ERROR
```

**Options:**
| Flag | Description |
|---|---|
| `--tail` | Show last N lines |
| `--level` | Filter: `DEBUG`, `INFO`, `WARN`, `ERROR` |
| `--format` | `text` or `json` |

### `magenta orchestrate replay <mission_id>`

Replay a mission from registry data.

```bash
magenta orchestrate replay mission-8932
magenta orchestrate replay mission-8932 --speed 2
```

**Options:**
| Flag | Description |
|---|---|
| `--speed` | Replay speed multiplier |
| `--agent` | Filter to specific agent turns |

---

## `magenta automate`

Playbook, rule, and trigger management.

### `magenta automate playbook list`

List registered playbooks.

```bash
magenta automate playbook list
magenta automate playbook list --tags phishing
```

### `magenta automate playbook apply <file>`

Register or update a playbook.

```bash
magenta automate playbook apply config/playbooks/phishing.yaml
magenta automate playbook apply config/playbooks/phishing.yaml --dry-run
```

### `magenta automate playbook validate <file>`

Validate playbook schema without registering.

```bash
magenta automate playbook validate config/playbooks/phishing.yaml
```

### `magenta automate rule list`

List routing rules.

```bash
magenta automate rule list
magenta automate rule list --enabled-only
```

### `magenta automate rule add <file>`

Add a routing rule from YAML.

```bash
magenta automate rule add config/rules/routing.yaml
```

### `magenta automate trigger list`

List configured triggers.

```bash
magenta automate trigger list
```

### `magenta automate trigger enable <name>`

Enable a trigger.

```bash
magenta automate trigger enable sentinel-incident-webhook
```

### `magenta automate trigger disable <name>`

Disable a trigger.

```bash
magenta automate trigger disable sentinel-incident-webhook
```

---

## `magenta response`

Incident, action, and approval management.

### `magenta response actions list`

List available response actions.

```bash
magenta response actions list
magenta response actions list --role containment
```

### `magenta response actions describe <action>`

Show action details, parameters, and risk.

```bash
magenta response actions describe disable_account
```

### `magenta response actions execute <action>`

Execute a response action.

```bash
magenta response actions execute disable_account --target 'user@fin.com' --reason compromised
magenta response actions execute isolate_host --target 'FIN-PROD-347' --force
```

**Options:**
| Flag | Description |
|---|---|
| `--target` | Target entity identifier |
| `--reason` | Reason code: `compromised`, `malicious`, `policy` |
| `--force` | Skip approval gate |

### `magenta response approval list`

List pending approvals.

```bash
magenta response approval list
magenta response approval list --queue
magenta response approval list --role containment
```

### `magenta response approval approve <id>`

Approve a pending action.

```bash
magenta response approval approve approval-3942
magenta response approval approve approval-3942 --comment "Ransomware confirmed, proceed"
```

### `magenta response approval reject <id>`

Reject a pending action.

```bash
magenta response approval reject approval-3942 --reason "False positive, investigate further"
```

### `magenta response incidents list`

List active incidents.

```bash
magenta response incidents list
magenta response incidents list --severity high
magenta response incidents list --status active
```

---

## `magenta health`

System health monitoring.

### `magenta health check`

Run full system health check.

```bash
magenta health check
magenta health check --format json
```

**Options:**
| Flag | Description |
|---|---|
| `--format` | `text` or `json` |

### `magenta health agents`

Check agent health status.

```bash
magenta health agents
magenta health agents --watch
magenta health agents --role triage
```

### `magenta health models`

Check LLM model health.

```bash
magenta health models
magenta health models --provider ollama
```

### `magenta health pipeline`

Check Event Hubs pipeline health.

```bash
magenta health pipeline
magenta health pipeline --lag-threshold 1000
```

### `magenta health storage`

Check storage health.

```bash
magenta health storage
```

---

## `magenta lab`

Experimentation and testing.

### `magenta lab simulate <scenario>`

Run a mission simulation.

```bash
magenta lab simulate scenarios/phishing.json
magenta lab simulate scenarios/ransomware.json --speed 5
```

### `magenta lab test <agent>`

Test an agent with a prompt.

```bash
magenta lab test triage_agent --prompt "Sev 5 alert: ransomware detected on FIN-PROD-347"
magenta lab test containment --interactive
```

### `magenta lab compare <a> <b>`

Compare two models on a test suite.

```bash
magenta lab compare ollama/qwen2.5:7b ollama/mistral:7b
magenta lab compare ollama/qwen2.5:7b openrouter/gemini-flash --suite classification
```

### `magenta lab evaluate <suite>`

Run a full evaluation benchmark.

```bash
magenta lab evaluate test_suites/soc_triage.json
magenta lab evaluate test_suites/containment.json --output results.json
```
