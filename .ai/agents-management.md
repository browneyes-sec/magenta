# Agents Management — Magenta AI Layer

**Agent lifecycle, registry, health management, OpenRouter, Vercel API Gateway, Opencode Codex, and JSON/T configuration.**

---

## 1. Agent Lifecycle

```
         ┌──────────┐
         │ REGISTER │  ← Agent discovery / API registration
         └─────┬────┘
               │
         ┌─────▼────┐
         │  IDLE    │  ← Available for task assignment
         └─────┬────┘
               │ mission_assigned
               ▼
         ┌──────────┐
         │  ACTIVE  │  ← Executing mission tasks
         └─────┬────┘
               │
      ┌────────┼────────┐
      │        │        │
      ▼        ▼        ▼
   ┌──────┐ ┌──────┐ ┌──────┐
   │DRAIN │ │ERROR │ │DONE  │
   └──┬───┘ └──┬───┘ └──────┘
      │        │
      ▼        ▼
   ┌──────────────┐
   │  DEREGISTER  │
   └──────────────┘
```

---

## 2. Agent Registry

```yaml
agent_registry:
  storage: "azure_table_storage"
  table: "AgentRegistry"

  agents:
    - id: "triage_agent-v3"
      role: "triage"
      version: "3.1.0"
      status: "online"
      models:
        primary: "ollama/qwen2.5:7b"
        fallback: "ollama/mistral:7b"
      tools:
        - "sentinel_query_incidents"
        - "registry_write_activity"
      max_concurrent: 5
      current_load: 0.3
      last_heartbeat: "2026-06-13T19:05:00Z"
      uptime_seconds: 86400

    - id: "containment_specialist-v1"
      role: "containment"
      version: "1.2.0"
      status: "online"
      models:
        primary: "ollama/qwen2.5:7b"
      tools:
        - "entra_disable_account"
        - "defender_isolate_host"
        - "sentinel_update_incident"
        - "registry_write_activity"
      max_concurrent: 3
      current_load: 0.6
      last_heartbeat: "2026-06-13T19:05:01Z"
      uptime_seconds: 43200
```

---

## 3. OpenRouter Agent Gateway

OpenRouter serves as a unified model API gateway with automatic fallback and cost management:

```yaml
openrouter:
  api_key: "${OPENROUTER_API_KEY}"
  site_name: "Magenta ASOAR"

  agent_defaults:
    triage_agent:
      model: "google/gemini-2.0-flash-001"
      fallbacks:
        - "meta-llama/llama-3.3-70b-instruct"
        - "mistralai/mistral-7b-instruct"
      max_cost_per_run: 0.005

    investigation_agent:
      model: "openrouter/auto"
      max_cost_per_run: 0.02
      provider_ordering: ["together", "fireworks", "replicate"]

  cost_controls:
    daily_budget_usd: 10.00
    monthly_budget_usd: 200.00
    alert_email: "soc-ops@contoso.com"
    block_on_exceed: true
```

---

## 4. Vercel API Gateway

Vercel Edge Functions serve as the lightweight middleware layer for agent HTTP APIs, authentication, and rate limiting:

```typescript
// vercel/api/agents/[agent]/execute.ts
import { getAgentConfig, validateAuth } from '@/lib/magenta';

export async function POST(req: Request, { params }: { params: { agent: string } }) {
  // 1. Authenticate request (Entra ID JWT or API key)
  const auth = await validateAuth(req.headers.get('Authorization'));
  if (!auth.authenticated) return Response.json({ error: 'unauthorized' }, { status: 401 });

  // 2. Rate limit per agent
  const rateLimit = await checkRateLimit(auth.tenant, params.agent);
  if (rateLimit.exceeded) return Response.json({ error: 'rate_limit' }, { status: 429 });

  // 3. Route to agent
  const body = await req.json();
  const agent = await getAgentConfig(params.agent);

  // 4. If OLLAMA model → route to local inference
  //    If API model → route through OpenRouter
  if (agent.model.startsWith('ollama/')) {
    const response = await fetch(`http://${agent.ollama_host}/api/chat`, {
      method: 'POST',
      body: JSON.stringify({
        model: agent.model.replace('ollama/', ''),
        messages: [{ role: 'user', content: body.prompt }],
        stream: false,
      }),
    });
    return Response.json(await response.json());
  } else {
    // Route through OpenRouter
    const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.OPENROUTER_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: agent.openrouter_model,
        messages: [{ role: 'user', content: body.prompt }],
      }),
    });
    return Response.json(await response.json());
  }
}
```

---

## 5. Opencode Integration

Opencode provides an agentic coding interface for Magenta development: configuration management, prompt engineering, and framework scaffolding.

```yaml
opencode:
  enabled: true
  config_dir: ".opencode/"
  agent_contexts:
    - path: "context/magenta/CLAUDE.md"
      scope: "framework_design"
    - path: "context/backend/CLAUDE.md"
      scope: "backend_agent"
    - path: "context/data/CLAUDE.md"
      scope: "data_pipeline"
  prompt_templates:
    - name: "new_agent_role"
      path: ".opencode/prompts/new_agent_role.md"
      variables:
        - "role_name"
        - "model_config"
        - "tools"
    - name: "new_mission_playbook"
      path: ".opencode/prompts/new_mission_playbook.md"
```

---

## 6. JSON & T Configuration

Magenta uses **JSON** for runtime configuration (agents, models, routing) and **T (TOML-like)** for human-authored playbooks and mission definitions.

### Agent Configuration (JSON + JSON Schema)

```json
{
  "$schema": "https://magenta.security/schemas/agent-config-v1.json",
  "agent_id": "triage_agent-v3",
  "role": "triage",
  "model": {
    "provider": "ollama",
    "model": "qwen2.5:7b",
    "parameters": {
      "temperature": 0.2,
      "max_tokens": 2048,
      "top_p": 0.9
    }
  },
  "tools": [
    {
      "name": "sentinel_query_incidents",
      "enabled": true,
      "rate_limit": 30
    },
    {
      "name": "registry_write_activity",
      "enabled": true
    }
  ],
  "risk": {
    "tolerance": 0.6,
    "escalation_threshold": 0.8
  },
  "memory": {
    "type": "ephemeral",
    "window": 50,
    "ttl_hours": 24
  }
}
```

### Playbook Configuration (T — TOML-like)

```toml
[mission]
name = "phishing_containment_v2"
description = "End-to-end phishing incident response"
version = "2.1.0"

[trigger]
sources = ["sentinel", "splunk"]
conditions = [{ field = "incident_type", equals = "phishing" }]

[orchestration]
teaming = "supervisor"
swarm_manager = { model = "ollama/mixtral:8x7b" }
max_duration_seconds = 600

[[stages]]
name = "triage"
role = "triage_agent"
sla_seconds = 30
model = "ollama/qwen2.5:7b"

[[stages]]
name = "enrich"
role = "enrich_agent"
sla_seconds = 120
model = "ollama/mistral:7b"

[[stages]]
name = "contain"
role = "containment_agent"
approval_required = true
approval_threshold = 60

[[stages]]
name = "report"
role = "reporting_agent"
model = "groq/mixtral-8x7b-32768"

[governance]
audit_level = "full"
retention_days = 365
compliance_frameworks = ["SOC2", "ISO27001", "NIS2"]
```

---

## 7. Agent Health Dashboard

```yaml
health_dashboard:
  refresh_interval: 10s
  panels:
    - title: "Agent Status"
      type: "table"
      columns:
        - "agent_id"
        - "role"
        - "status"  # online/degraded/down
        - "load"
        - "uptime"
        - "last_heartbeat"
    - title: "Model Performance"
      type: "timeseries"
      metrics:
        - "avg_latency_ms"
        - "p95_latency_ms"
        - "tokens_per_second"
        - "error_rate"
    - title: "Mission Queue"
      type: "table"
      columns:
        - "mission_id"
        - "status"
        - "age_seconds"
        - "assigned_agent"
        - "risk_score"
```

---

## 8. Agent Auto-Scaling

```yaml
auto_scaling:
  triage_agent:
    min_instances: 2
    max_instances: 10
    scale_up:
      metric: "task_queue_depth"
      threshold: 20
      cooldown_seconds: 60
    scale_down:
      metric: "task_queue_depth"
      threshold: 5
      cooldown_seconds: 120

  enrichment_agent:
    min_instances: 2
    max_instances: 6
    scale_up:
      metric: "avg_latency_ms"
      threshold: 5000
      cooldown_seconds: 120
```

---

## 9. Agent Versioning & Rollback

```yaml
agent_versioning:
  strategy: "blue_green"
  registry: "azure_container_registry"
  tags:
    - "agent_id:version"
    - "agent_id:latest"
    - "agent_id:stable"

  rollback:
    auto_on_error_rate: 0.05
    max_rollback_versions: 3
    health_check_period_seconds: 120
```

---

## 10. Management API

| Endpoint | Method | Description |
|---|---|---|
| `/agents` | GET | List all registered agents |
| `/agents/:id` | GET | Get agent details |
| `/agents/:id/status` | PUT | Update agent status (drain/activate) |
| `/agents/:id/config` | PUT | Update agent configuration |
| `/missions` | GET | List active missions |
| `/missions/:id` | GET | Get mission details |
| `/missions/:id/cancel` | POST | Cancel a mission |
| `/models` | GET | List available models and health |
| `/models/:provider/:model` | POST | Test inference |
| `/health` | GET | Overall system health |
