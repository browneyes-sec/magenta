# Configuration Reference

## Environment Variables

All configuration is managed via environment variables with the `MAGENTA_` prefix, or via YAML files in `config/`.

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MAGENTA_ENV` | `dev` | Environment: `dev`, `staging`, `prod` |
| `MAGENTA_DATA_DIR` | `data/` | Data directory path |
| `MAGENTA_CONFIG_DIR` | `config/` | Configuration directory path |

### Model / LLM Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MAGENTA_MODELS_DEFAULT_PROVIDER` | `ollama` | Default LLM provider |
| `MAGENTA_MODELS_DEFAULT_MODEL` | `qwen2.5:7b` | Default model name |
| `MAGENTA_MODELS_OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `MAGENTA_MODELS_OPENROUTER_KEY` | — | OpenRouter API key |
| `MAGENTA_MODELS_GEMINI_KEY` | — | Google Gemini API key |
| `MAGENTA_MODELS_GROQ_KEY` | — | Groq API key |

### Event Hubs Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MAGENTA_EVENTHUB_CONNECTION_STRING` | — | Event Hubs connection string |
| `MAGENTA_EVENTHUB_NAMESPACE` | `magenta-agent-bus` | Event Hubs namespace |
| `MAGENTA_EVENTHUB_TOPICS` | `{...}` | Topic name mappings |

### Sentinel Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MAGENTA_SENTINEL_TENANT_ID` | — | Azure Entra ID tenant ID |
| `MAGENTA_SENTINEL_CLIENT_ID` | — | Azure Entra ID app registration client ID |
| `MAGENTA_SENTINEL_CLIENT_SECRET` | — | Client secret (use Managed Identity in production) |
| `MAGENTA_SENTINEL_WORKSPACE_ID` | — | Log Analytics workspace ID |

### Splunk Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MAGENTA_SPLUNK_HOST` | `localhost` | Splunk Enterprise host |
| `MAGENTA_SPLUNK_PORT` | `8089` | Splunk REST API port |
| `MAGENTA_SPLUNK_USERNAME` | — | Splunk username |
| `MAGENTA_SPLUNK_PASSWORD` | — | Splunk password |
| `MAGENTA_SPLUNK_VERIFY_SSL` | `true` | SSL verification enabled |
| `MAGENTA_SPLUNK_CA_BUNDLE_PATH` | — | Custom CA bundle path |

### SOAR Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MAGENTA_SOAR_HOST` | `localhost` | Splunk SOAR host |
| `MAGENTA_SOAR_PORT` | `443` | Splunk SOAR API port |
| `MAGENTA_SOAR_USERNAME` | — | SOAR service account username |
| `MAGENTA_SOAR_PASSWORD` | — | SOAR service account password |
| `MAGENTA_SOAR_VERIFY_SSL` | `true` | SSL verification enabled |
| `MAGENTA_SOAR_CA_BUNDLE_PATH` | — | Custom CA bundle path |
| `MAGENTA_SOAR_FAILURE_THRESHOLD` | `5` | Circuit breaker failure threshold |
| `MAGENTA_SOAR_RESET_TIMEOUT` | `30` | Circuit breaker reset timeout (seconds) |

### Idempotency Store Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MAGENTA_IDEMPOTENCY_STORAGE_CONNECTION_STRING` | — | Azure Table Storage connection string |
| `MAGENTA_IDEMPOTENCY_TABLE_NAME` | `IdempotencyKeys` | Table name |
| `MAGENTA_IDEMPOTENCY_TTL_HOURS` | `24` | Key TTL in hours |

### Elasticsearch Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MAGENTA_ELASTIC_HOSTS` | `["http://localhost:9200"]` | Elasticsearch node URLs |
| `MAGENTA_ELASTIC_USERNAME` | — | Elasticsearch username |
| `MAGENTA_ELASTIC_PASSWORD` | — | Elasticsearch password |
| `MAGENTA_ELASTIC_INDEX_PREFIX` | `magenta` | Index name prefix |

### Delta Lake Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MAGENTA_DELTA_URI` | `/data/magenta/delta` | Delta Lake table path |
| `MAGENTA_DELTA_MODE` | `append` | Write mode |
| `MAGENTA_DELTA_PARTITION_BY` | `["source_system"]` | Partition columns |

---

## Configuration Files

Settings can also be loaded from YAML files in `config/`:

```yaml
# config/default.yaml
env: dev
models:
  default_provider: ollama
  ollama_host: http://localhost:11434
soar:
  host: soar.internal
  port: 443
  verify_ssl: true
splunk:
  host: splunk.internal
  port: 8089
```

Load order (later overrides earlier):
1. `config/default.yaml`
2. Environment variables (`MAGENTA_*`)
3. `config/prod.yaml` (in production)
4. `config/*.local.yaml` (local overrides, gitignored)
