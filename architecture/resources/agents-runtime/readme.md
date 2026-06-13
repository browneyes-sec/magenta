# Agent Runtime Architecture & Sizing

## Component Overview

Agents in the Magenta fabric run as stateless, independently deployable units. Two runtime options are used based on agent function:

| Runtime | Agents | Why |
|---|---|---|
| **Azure Functions (Python 3.12)** | Source Agents, Normalizer, Enrichment, Orchestrator, Execution | Event-driven, managed identity auth, consumption pricing for variable load |
| **Azure Logic Apps (Standard)** | Sentinel Source Agent (primary), Orchestrator fallback | Native Sentinel connector, stateful workflows, managed connectors |
| **Azure Container Apps / K8s** | LLM Agent Runtime (Magenta core) | GPU scheduling, long-running agent turns, OLLAMA integration |

## Azure Functions Architecture

### Agent as Function

```python
# Each agent is an Azure Function triggered by Event Hubs
import azure.functions as func
import logging

app = func.FunctionApp()

@app.event_hub_message_trigger(
    arg_name="event",
    event_hub_name="raw-alerts",
    connection="EventHubsConnectionString",
    consumer_group="normalizer",
)
async def normalizer_agent(event: func.EventHubEvent):
    for message in event.get_body().decode():
        alert = json.loads(message)
        enriched = await normalize(alert)
        await publish_to_eventhub("enriched-alerts", enriched)
```

### Deployment Model

| Property | Consumption Plan | Elastic Premium (EP1) |
|---|---|---|
| Scale | Auto-scale to 200 instances | Auto-scale, pre-warmed workers |
| Cold start | ~1-3 s (Python) | ~0.2 s (pre-warmed) |
| Max execution | 10 min | 60 min (unlimited with FastCGI) |
| VNet integration | No | Yes |
| Cost | Pay-per-execution | Pay-per-instance-second |
| Recommendation | Dev, low-volume agents | Production, latency-sensitive agents |

### Per-Agent Configuration

```python
# function_app.py — all agents in one Function App or per-agent
AGENTS = {
    "sentinel-source": {
        "trigger": "timer",  # every 30 seconds
        "consumer_group": None,  # timer trigger doesn't use Event Hubs
        "timeout": 300,
        "identity": "mi-sentinel-source",
        "scopes": ["Sentinel Reader", "Event Hubs Data Sender"],
    },
    "splunk-source": {
        "trigger": "timer",  # every 30 seconds
        "consumer_group": None,
        "timeout": 300,
        "identity": "mi-splunk-source",
        "scopes": ["Event Hubs Data Sender"],
    },
    "normalizer": {
        "trigger": "eventhub",
        "consumer_group": "normalizer",
        "topic": "raw-alerts",
        "timeout": 60,
        "identity": "mi-normalizer",
        "scopes": ["Event Hubs Data Receiver", "Event Hubs Data Sender"],
    },
    "orchestrator": {
        "trigger": "eventhub",
        "consumer_group": "orchestrator",
        "topic": "enriched-alerts",
        "timeout": 120,
        "identity": "mi-orchestrator",
        "scopes": ["Event Hubs Data Receiver", "Event Hubs Data Sender", "Approval Gate Read"],
    },
}
```

### Managed Identity Per Agent

```bash
# One app registration per agent — least privilege
az ad sp create-for-rbac --name "mi-magenta-normalizer" \
    --role "Event Hubs Data Receiver" \
    --scopes /subscriptions/.../namespaces/magenta-agent-bus

az role assignment create \
    --assignee-object-id $(az ad sp list --display-name "mi-magenta-normalizer" --query "[0].id" -o tsv) \
    --role "Event Hubs Data Sender" \
    --scope /subscriptions/.../namespaces/magenta-agent-bus/topics/enriched-alerts
```

## Logic Apps Architecture

Sentinel Source Agent uses Logic Apps for native connector support:

```json
{
  "definition": {
    "triggers": {
      "Recurrence": {
        "type": "Recurrence",
        "recurrence": { "frequency": "Second", "interval": 30 }
      }
    },
    "actions": {
      "Query_Sentinel": {
        "type": "ApiConnection",
        "inputs": {
          "host": { "connectionName": "azuresentinel" },
          "method": "get",
          "path": "/Subscriptions/.../Workspaces/.../Incidents",
          "queries": {
            "$filter": "properties/createdTimeUtc ge ${lastPollTime}"
          }
        }
      },
      "Publish_to_EventHub": {
        "type": "ApiConnection",
        "inputs": {
          "host": { "connectionName": "eventhubs" },
          "method": "post",
          "path": "/namespaces/magenta-agent-bus/messages",
          "body": "@body('Query_Sentinel')"
        }
      }
    }
  }
}
```

## Container/K8s Runtime (LLM Agents)

For Magenta's LLM-powered agents (Triage, Enrich, Contain, etc.):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: magenta-agent-pool
spec:
  replicas: 3
  selector:
    matchLabels:
      app: magenta-agent
  template:
    spec:
      containers:
        - name: agent
          image: magenta/agent:latest
          env:
            - name: MAGENTA_ENV
              value: "prod"
            - name: MAGENTA_EVENTHUB__CONNECTION_STRING
              valueFrom:
                secretKeyRef:
                  name: magenta-eventhub
                  key: connection-string
          resources:
            requests:
              cpu: "1"
              memory: "2Gi"
            limits:
              cpu: "2"
              memory: "4Gi"
```

## Scaling

| Agent Type | Scale Trigger | Scale Behavior |
|---|---|---|
| Source Agents (timer) | Fixed interval | 1 instance (or 2 for HA) |
| Event Hubs triggered | Event Hub backlog | 1 instance per partition |
| LLM Agents (K8s) | CPU/memory/queue | HPA: target 70% CPU |
| Logic Apps | Auto-scale | Managed by platform |

## Monitoring

| Metric | Alert |
|---|---|
| Function execution count drop > 50% | Critical — agent may be down |
| Function failure rate > 5% | Warning |
| Cold start latency > 3 s (Premium) | Warning |
| Event Hubs consumer lag per agent > 500 | Warning |
| Agent execution time > 80% of timeout | Warning |
