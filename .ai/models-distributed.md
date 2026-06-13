# AI Models — Distributed Intelligence System — Magenta AI Layer

**Model routing, tiered intelligence, fallback chains, and distributed inference across LLMs, SLMs, and free API gateways.**

---

## 1. Intelligence Tier Architecture

```
                          ┌───────────────────────┐
                          │   Agent Request        │
                          │   (role + task type)   │
                          └───────────┬───────────┘
                                      │
                            Model Router
                                      │
                          ┌───────────▼───────────┐
                          │   Intelligence Tier     │
                          │   Selector              │
                          └───────────┬───────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
     ┌────────────────┐   ┌────────────────┐   ┌────────────────┐
     │   Tier 1       │   │   Tier 2       │   │   Tier 3       │
     │   Speed        │   │   Reasoning    │   │   Cost-Save    │
     │   (SLM < 7B)   │   │   (LLM 7-32B)  │   │   (Free APIs)  │
     └────────────────┘   └────────────────┘   └────────────────┘
              │                       │                       │
              ▼                       ▼                       ▼
     ┌────────────────┐   ┌────────────────┐   ┌────────────────┐
     │ OLLAMA Local   │   │ OLLAMA Local   │   │ Google Gemini  │
     │ Qwen 7B        │   │ Mixtral 8x7B   │   │ Groq (free)    │
     │ Mistral 7B     │   │ Qwen 32B       │   │ Hugging Face   │
     │ Llama 8B       │   │ DeepSeek 7B    │   │ OpenRouter(fr) │
     └────────────────┘   └────────────────┘   └────────────────┘
```

---

## 2. Model Router

```yaml
model_router:
  strategy: "tiered_with_fallback"

  tiers:
    speed:
      description: "Low-latency SLMs for real-time actions"
      max_latency_ms: 2000
      models:
        - provider: "ollama"
          model: "qwen2.5:7b"
          weight: 60
        - provider: "ollama"
          model: "mistral:7b"
          weight: 30
        - provider: "ollama"
          model: "llama3.1:8b"
          weight: 10
      fallback: "reasoning"

    reasoning:
      description: "Strong models for complex decisions"
      max_latency_ms: 10000
      models:
        - provider: "ollama"
          model: "mixtral:8x7b"
          weight: 50
        - provider: "ollama"
          model: "qwen2.5:32b"
          weight: 30
        - provider: "ollama"
          model: "deepseek-r1:7b"
          weight: 20
      fallback: "cost_save"

    cost_save:
      description: "Free API models for non-sensitive tasks"
      models:
        - provider: "gemini"
          model: "gemini-2.0-flash"
          weight: 50
          rate_limit: 60_per_minute
        - provider: "groq"
          model: "mixtral-8x7b-32768"
          weight: 30
          rate_limit: 30_per_minute
        - provider: "openrouter"
          model: "google/gemini-2.0-flash-001"
          weight: 20
          rate_limit: 20_per_minute
      fallback: "speed"

  health_check:
    interval: 30s
    timeout: 5s
    unhealthy_threshold: 3
```

---

## 3. Fallback Chain Execution

```python
class ModelRouter:
    async def route(self, request: ModelRequest) -> ModelResponse:
        tier = self.select_tier(request.role, request.task_type)

        for attempt in range(self.max_attempts):
            model = self.pick_model(tier)

            try:
                start = time.monotonic()
                response = await self.invoke(model, request)
                latency = time.monotonic() - start

                if latency > tier.max_latency_ms / 1000:
                    self.record_slow(model)
                    continue  # try next model

                return response

            except (ModelTimeout, ModelError, RateLimitError) as e:
                self.record_failure(model, e)
                continue  # fallback

        # All models failed → emergency fallback
        return await self.emergency_fallback(request)
```

---

## 4. Model-to-Role Assignment

```yaml
role_model_mapping:
  swarm_manager:
    tier: "reasoning"
    primary: "ollama/mixtral:8x7b"
    fallback: "ollama/qwen2.5:32b"
    emergency: "gemini/gemini-2.0-flash"

  triage_agent:
    tier: "speed"
    primary: "ollama/qwen2.5:7b"
    fallback: "ollama/mistral:7b"
    emergency: "ollama/nemotron-mini:4b"

  containment_agent:
    tier: "speed"
    primary: "ollama/qwen2.5:7b"
    fallback: "ollama/llama3.1:8b"

  enrich_agent:
    tier: "speed"
    primary: "ollama/mistral:7b"
    fallback: "ollama/qwen2.5:7b"

  investigation_agent:
    tier: "reasoning"
    primary: "ollama/deepseek-r1:7b"
    fallback: "ollama/qwen2.5:32b"

  compliance_agent:
    tier: "cost_save"
    primary: "gemini/gemini-2.0-flash"
    fallback: "groq/mixtral-8x7b-32768"

  reporting_agent:
    tier: "cost_save"
    primary: "groq/mixtral-8x7b-32768"
    fallback: "openrouter/google/gemini-2.0-flash-001"
```

---

## 5. SLM (Small Language Model) Strategy

For high-volume pre-filtering and real-time containment, SLMs (< 4B params) run on CPU or low-power GPU:

```yaml
slm_pool:
  enabled: true
  models:
    - name: "nemotron-mini:4b"
      hardware: "cpu"
      throughput: 200_requests_per_minute
      use_cases:
        - "pre_filter_benign"
        - "extract_iocs_from_text"
        - "classify_alert_type"
    - name: "phi4:14b"
      hardware: "cpu"
      throughput: 80_requests_per_minute
      use_cases:
        - "compliance_check_prefilter"
        - "entity_extraction"
        - "severity_classification"
```

---

## 6. OpenRouter Integration

OpenRouter provides a unified API gateway to 200+ models with built-in fallback and cost tracking:

```python
import openrouter

client = openrouter.OpenRouter(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    site_url="https://magenta.security",
    site_name="Magenta ASOAR"
)

response = await client.chat.completions.create(
    model="openrouter/auto",  # auto-picks best available
    messages=[{"role": "user", "content": prompt}],
    # Fallback chain
    models=[
        "google/gemini-2.0-flash-001",
        "meta-llama/llama-3.3-70b-instruct",
        "mistralai/mistral-7b-instruct",
    ],
    route="fallback"
)
```

```yaml
openrouter_config:
  api_key: "${OPENROUTER_API_KEY}"  # Key Vault
  default_model: "openrouter/auto"
  fallback_models:
    - "google/gemini-2.0-flash-001"
    - "meta-llama/llama-3.3-70b-instruct"
    - "mistralai/mistral-7b-instruct"
  cost_tracking:
    enabled: true
    budget_alert_usd: 50.00
    monthly_cap_usd: 200.00
  rate_limiting:
    requests_per_minute: 60
    tokens_per_minute: 100000
```

---

## 7. Vercel API Gateway Integration

Vercel serves as the serverless API gateway for model inference, handling auth, rate limiting, and routing:

```typescript
// vercel/api/chat/route.ts — Model proxy
export async function POST(request: Request) {
  const { agent, prompt, model } = await request.json();

  const response = await fetch(getModelEndpoint(agent, model), {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${getModelKey(agent, model)}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: getModelName(agent, model),
      messages: [{ role: 'user', content: prompt }],
      stream: false,
    }),
  });

  // Forward to agent
  return Response.json(await response.json());
}
```

---

## 8. Model Performance Monitoring

```yaml
model_monitoring:
  metrics:
    - name: "tokens_per_second"
      threshold_min: 30
    - name: "first_token_latency"
      threshold_max_ms: 500
    - name: "error_rate"
      threshold_max: 0.05
    - name: "context_window_utilization"
      threshold_max: 0.85

  alerts:
    - metric: "error_rate"
      condition: "> 0.1"
      action: "page_oncall"
    - metric: "latency_p95"
      condition: "> 10s"
      action: "fallback_to_cold_tier"
```

---

## 9. Model Governance

| Governance | Mechanism |
|---|---|
| Model version pinning | Every agent config specifies exact model tag |
| Prompt audit | All prompts + responses logged to registry |
| Cost allocation | Per-mission token usage tracked in registry |
| Model rotation | Deprecated models blocked via Model Router config |
| Red team testing | Monthly adversarial prompt testing against agent models |
