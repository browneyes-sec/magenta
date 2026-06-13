# Compute & GPU — Magenta AI Layer

**Infrastructure for running AI models: inference servers, GPU clusters, OLLAMA farms, and serverless compute.**

---

## 1. Compute Topology

```
┌─────────────────────────────────────────────────────────────────────┐
│                      OLLAMA FARM (Local / On-Prem)                   │
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ GPU Node │ │ GPU Node │ │ CPU Node │ │ GPU Node │ │ GPU Node │  │
│  │ A100 80GB│ │ A100 80GB│ │ (embed)  │ │ RTX 4090 │ │ RTX 4090 │  │
│  │ mixtral  │ │ qwen32b  │ │ all-Mini │ │ qwen7b   │ │ mistral  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                                                                     │
│  OLLAMA_ORIGINS="*"  │  Model distribution: OLLAMA_HOME/shared       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   CLOUD GPU (Burst / Failover)                       │
│                                                                     │
│  Azure NC-series (V100/A100)  │  RunPod  │  Lambda  │  Modal        │
│  - Model fine-tuning         │  - Overflow  │  - Spikes │  - Serverless │
│  - Heavy reasoning tasks     │  - Batch     │  - Dev    │  - Embedding │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. OLLAMA Cluster Configuration

### Docker Compose (Multi-Node OLLAMA)

```yaml
version: "3.8"
services:
  ollama-master:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama
      - ./model_config.yaml:/etc/ollama/config.yaml
    environment:
      - OLLAMA_ORIGINS=*
      - OLLAMA_HOST=0.0.0.0
      - OLLAMA_NUM_PARALLEL=4
      - OLLAMA_MAX_LOADED_MODELS=6
      - OLLAMA_KEEP_ALIVE=5m
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 2
              capabilities: [gpu]

  ollama-worker-1:
    image: ollama/ollama
    volumes:
      - ollama_models_shared:/root/.ollama:ro
    environment:
      - OLLAMA_HOST=0.0.0.0
      - OLLAMA_NUM_PARALLEL=2
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### Model Preloading

```bash
# Pre-pull models for fast agent startup
ollama pull qwen2.5:7b
ollama pull qwen2.5:32b
ollama pull mistral:7b
ollama pull mixtral:8x7b
ollama pull deepseek-r1:7b
ollama pull llama3.1:8b
ollama pull phi4:14b
ollama pull nemotron-mini:4b
ollama pull all-minilm:l6-v2  # embeddings
```

---

## 3. Model Distribution & Load Balancing

```yaml
compute_cluster:
  nodes:
    - name: "gpu-a100-01"
      model: "A100 80GB"
      capacity: "large_models"
      served_models: ["mixtral:8x7b", "qwen2.5:32b"]
      ollama_host: "192.168.1.10:11434"
    - name: "gpu-4090-01"
      model: "RTX 4090 24GB"
      capacity: "medium_models"
      served_models: ["qwen2.5:7b", "deepseek-r1:7b"]
      ollama_host: "192.168.1.20:11434"
    - name: "gpu-4090-02"
      model: "RTX 4090 24GB"
      capacity: "medium_models"
      served_models: ["mistral:7b", "llama3.1:8b"]
      ollama_host: "192.168.1.21:11434"
    - name: "cpu-embed-01"
      model: "CPU (32 cores)"
      capacity: "embeddings"
      served_models: ["all-minilm:l6-v2", "phi4:14b"]
      ollama_host: "192.168.1.30:11434"

  routing:
    strategy: "latency_based"
    health_check_interval: 30s
    fallback:
      - cloud: "azure_nc_series"
      - cloud: "runpod"
```

---

## 4. GPU Resource Allocation Per Agent

| Agent Role | Recommended GPU | VRAM | Model Size | Parallel Requests |
|---|---|---|---|---|
| Swarm Manager | A100 80GB / 2x RTX 4090 | 48-80GB | Mixtral 8x7b (47B) | 4 |
| Investigation Agent | A100 80GB | 48-80GB | Qwen 32B | 2 |
| Triage Agent | RTX 4090 24GB | 16-24GB | Qwen 7B / Mistral 7B | 8 |
| Containment Agent | RTX 4090 24GB | 16-24GB | Qwen 7B / Llama 8B | 8 |
| Enrich Agent | RTX 4090 24GB | 16-24GB | Mistral 7B | 6 |
| Compliance Agent | RTX 4090 / CPU | 8-16GB | Phi4 14B / Qwen 7B | 4 |
| Reporting Agent | CPU | N/A | Mistral 7B (CPU) | 10 |
| High-Volume Filter | CPU / Mini GPU | 4-8GB | Nemotron 4B | 20 |

---

## 5. Cloud GPU Burst Configuration

```yaml
cloud_burst:
  enabled: true
  providers:
    azure:
      sku: "Standard_NC96ads_A100_v4"
      count: 2
      auto_shutdown_minutes: 30
      trigger: "ollama_cluster_load > 0.8"
    runpod:
      gpu_type: "RTX_6000_Ada"
      max_pods: 5
      trigger: "alert_volume > 100/min"
  fallback_strategy: "least_loaded_provider"
```

---

## 6. Model Serving Performance Benchmarks

| Model | Size | GPU | Tokens/s | Latency (p50) | Latency (p95) |
|---|---|---|---|---|---|
| `qwen2.5:7b` | 7B | RTX 4090 | 85 | 1.2s | 2.8s |
| `mistral:7b` | 7B | RTX 4090 | 92 | 1.1s | 2.5s |
| `deepseek-r1:7b` | 7B | RTX 4090 | 68 | 1.5s | 3.2s |
| `llama3.1:8b` | 8B | RTX 4090 | 78 | 1.3s | 2.9s |
| `mixtral:8x7b` | 47B | A100 80GB | 45 | 2.2s | 5.1s |
| `qwen2.5:32b` | 32B | A100 80GB | 38 | 2.6s | 5.8s |
| `phi4:14b` | 14B | RTX 4090 | 55 | 1.8s | 3.9s |
| `nemotron-mini:4b` | 4B | CPU (32c) | 25 | 4.0s | 8.0s |

---

## 7. Cost-Efficiency Strategy

| Tier | Hardware | Model | Cost/million tokens | Use Case |
|---|---|---|---|---|
| Hot | RTX 4090 (local) | Qwen 7B / Mistral 7B | $0.00 | Real-time triage, containment |
| Warm | A100 (local) | Mixtral 8x7b / Qwen 32B | $0.00 | Complex reasoning, investigation |
| Cold | CPU (local) | Nemotron 4B / Phi4 | $0.00 | High-volume pre-filtering |
| Burst | Cloud GPU | Any | ~$0.50-1.50/hr | Overflow, spikes, fine-tuning |
| API | Free tier | Gemini Flash / Groq | $0.00 | Reports, compliance, non-sensitive |
