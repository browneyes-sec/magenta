# Open WebUI Customization Guide

## Custom Tools

### Adding a New Pipeline Tool

1. Add the handler method to `soa/docker/pipelines/magenta_dictator_langchain_pipeline.py`:

```python
async def _my_new_tool(self, args: str) -> str:
    """Implement tool logic."""
    ...
    return result
```

2. Register it in the `_route_tool` method's `tools` dict:

```python
tools = {
    ...
    "my_new_tool": self._my_new_tool,
}
```

3. Add to `soa/instrumentation/version.json` pipeline_tools list.

### Adding a New MCP Server

1. Create `magenta/mcp/my_server_mcp_server.py` following the existing pattern:

```python
class MyServerMCPServer:
    name = "my_server"
    description = "..."
    
    async def my_tool(self, arg: str) -> dict:
        """Implement tool."""
        ...
    
    async def get_tools(self) -> list[dict]:
        return [{
            "name": "my_tool",
            "description": "...",
            "inputSchema": {...},
        }]

my_server_mcp = MyServerMCPServer()
```

2. Add to `magenta/mcp/__init__.py` exports.
3. Add to `soa/docker/mcpo-config.json` server list.

## Artifact Templates

### Creating a New Artifact Type

1. Add a generator method to `magenta/mcp/artifacts_mcp_server.py`:

```python
async def generate_my_artifact(self) -> dict:
    html = "<div>...</div>"
    return {"status": "success", "artifact_type": "my_artifact", "html": html}
```

2. Register in `get_tools()`.

3. Add schema to `soa/instrumentation/artifact_registry.json`.

4. Add generator to `soa/docker/pipelines/magenta_artifact_generator.py`.

## Model Configuration

### Changing Default Models

Edit `config/default.yaml`:

```yaml
models:
  default_provider: ollama
  default_model: qwen2.5:7b
  ollama_host: http://magenta-ollama:11434
```

### Adding a New Model Provider

1. Create provider client in `magenta/models/`.
2. Register in `magenta/models/router.py` tiered fallback chain.
3. Add credentials to `config/default.yaml` or env vars.

## Grafana Dashboard Customization

Dashboards are in `soa/docker/grafana/dashboards/`. To add a panel:

1. Edit the JSON file.
2. Add panel object with `title`, `type`, `gridPos`, and `targets`.
3. Restart Grafana: `docker compose restart magenta-grafana`.

Available Prometheus metrics from Magenta (prefixed `magenta_`):

| Metric | Type | Labels |
|---|---|---|
| `magenta_directive_issued_total` | Counter | type, priority |
| `magenta_directive_failed_total` | Counter | type |
| `magenta_mission_active_total` | Gauge | — |
| `magenta_mission_completed_total` | Counter | — |
| `magenta_approval_pending_total` | Gauge | — |
| `magenta_connector_healthy` | Gauge | connector |
| `magenta_llm_tokens_total` | Counter | provider, model, direction |
| `magenta_llm_budget_utilization_ratio` | Gauge | provider |
| `magenta_cache_hits_total` | Counter | — |
| `magenta_normalization_total` | Counter | — |

## Pipeline Valves

Edit `soa/docker/pipelines/valve_override.json` to configure pipeline behavior:

```json
{
  "magenta_dictator_langchain_pipeline": {
    "enabled": true,
    "priority": 10
  }
}
```

## Security

- Change `WEBUI_SECRET_KEY` env var in production.
- Set `ENABLE_SIGNUP: "false"` (already default).
- Configure Grafana admin password via `GRAFANA_PASSWORD`.
- Expose only ports 3000 and 3001 externally; all other services are on `magenta-internal` network.
- Shadow mode for approvals by default — switch to enforcing in `config/default.yaml` when ready.
