# GPU Architecture & Sizing

## Component Overview

Magenta uses local LLM inference via OLLAMA for agent reasoning. GPU is the most critical resource for latency-sensitive agent roles (Triage, Containment) and the most expensive.

Agent model assignments from the framework spec:

| Agent Role | Model | Size | VRAM |
|---|---|---|---|
| Triage, Containment | `qwen2.5:7b` / `mistral:7b` | 7B | ~6 GB |
| Enrich, Tool Use | `mistral:7b` / `llama3.1:8b` | 7-8B | ~6-8 GB |
| Swarm Manager | `mixtral:8x7b` / `qwen2.5:32b` | 32-47B | ~20-28 GB |
| Investigation | `deepseek-r1:7b` / `qwen2.5:32b` | 7-32B | 6-20 GB |
| Compliance | `gemini-2.0-flash` (API) | — | N/A (API) |
| Reporting | `qwen2.5:7b` (local or API) | 7B | ~6 GB |

## Sizing Baseline

### Minimal (prototyping / low volume)

| GPU | Models | Max Concurrent Agents | TCO |
|---|---|---|---|
| 1× RTX 4060 (12 GB) | qwen2.5:7b, mistral:7b | 2-3 | Low |
| 1× RTX 3090 (24 GB) | + mixtral:8x7b, qwen2.5:32b | 3-5 | Medium |

### Production — Dedicated Inference Cluster

| Node Type | GPU | Models | Agents per Node |
|---|---|---|---|
| Speed node | 2× RTX 4090 (24 GB each) | 7B models | 6-8 |
| Reasoning node | 1× A100 80 GB | 32B+ models | Swarm Manager only |
| Burst node | Spot instances (A10G / L40S) | Any | Overflow capacity |

### OLLAMA Cluster Topology

```
                    ┌─────────────────┐
                    │  Load Balancer   │
                    │  (nginx / haproxy)│
                    └──────┬──────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌────────────┐  ┌────────────┐  ┌────────────┐
   │ Speed Node │  │ Reasoning  │  │  Burst     │
   │ 2×RTX 4090 │  │ 1×A100 80G │  │ A10G Spot  │
   │ 7B models  │  │ 32B models │  │ Any model  │
   └────────────┘  └────────────┘  └────────────┘
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                    ┌─────────────────┐
                    │   OLLAMA Host    │
                    │  localhost:11434 │
                    └─────────────────┘
```

## VRAM Budget Calculation

Per concurrent agent session:

| Component | 7B Model | 32B Model |
|---|---|---|
| Model weights (FP16) | 14 GB | 64 GB |
| KV cache (4K context) | 1 GB | 4 GB |
| Overhead | 1 GB | 2 GB |
| **Total per session** | **~16 GB** | **~70 GB** |

With quantization (Q4_K_M):

| Component | 7B Model | 32B Model |
|---|---|---|
| Model weights (Q4) | 4.5 GB | 18 GB |
| KV cache (4K context) | 1 GB | 4 GB |
| Overhead | 0.5 GB | 1 GB |
| **Total per session** | **~6 GB** | **~23 GB** |

## Configuration

```yaml
# OLLAMA server config
OLLAMA_HOST: "http://localhost:11434"
OLLAMA_NUM_PARALLEL: 2        # requests per GPU
OLLAMA_MAX_LOADED_MODELS: 3   # keep hot in VRAM
```

```yaml
# Magenta model routing
models:
  default_provider: ollama
  ollama_host: http://ollama-cluster:11434
  default_model: qwen2.5:7b

model_routing:
  triage_agent:
    primary: "ollama/qwen2.5:7b"
    fallback: "gemini/gemini-2.0-flash"
  swarm_manager:
    primary: "ollama/mixtral:8x7b"
    fallback: "ollama/qwen2.5:32b"
```

## Cloud Burst Strategy

When local GPU queue depth exceeds threshold:

1. **Check local OLLAMA** — if `/_/metrics` shows queue > 3, trigger burst
2. **Route to Groq** — for speed-critical models (free tier available)
3. **Route to Gemini** — for reasoning tasks (free tier available)
4. **Provision spot GPU** — (Azure A10G / AWS g5) via IaC automation

## Monitoring

| Metric | Alert Threshold |
|---|---|
| GPU utilization > 95% | 5 min sustained |
| VRAM utilization > 90% | 2 min sustained |
| OLLAMA queue depth > 5 | Immediate |
| Model load/unload events > 10/min | Warning |
