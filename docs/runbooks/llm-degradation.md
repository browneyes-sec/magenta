# Runbook: LLM Degradation / Provider Outage

## Alert Definition
- **Alert**: `magenta_llm_circuit_breaker_open` (Prometheus: `magenta:circuit_breaker_open_rate > 0.05`)
- **Alert**: `magenta_llm_latency_p99` (Prometheus: `histogram_quantile(0.99, rate(magenta_model_latency_seconds_bucket[5m])) > 30`)
- **Alert**: `magenta_llm_error_rate` (Prometheus: `rate(magenta_model_errors_total[5m]) > 0.1`)
- **Severity**: High
- **Dashboard**: Grafana "Magenta ASOAR Ops" → Model Routing panel

## Symptoms
- Circuit breaker open for one or more model tiers (speed, reasoning, cost_save)
- Model latency P99 > 30 seconds
- High error rate on LLM calls (timeouts, 5xx, rate limits)
- Agents failing to complete tasks, missions timing out
- Fallback routing not working as expected

## Immediate Action (First 5 Minutes)
1. Check circuit breaker status: `kubectl exec -it <api-pod> -- python -c "from magenta.gateway.circuit import get_circuit_status; print(get_circuit_status())"`
2. Check provider health:
   - Ollama: `kubectl exec -it <ollama-pod> -- ollama ps`
   - Hosted APIs: check provider status pages (Groq, Gemini, OpenRouter)
3. Verify fallback chain: `kubectl exec -it <api-pod> -- python -c "from magenta.gateway.router import ModelRouter; r=ModelRouter(); print(r.get_fallback_chain())"`
4. If Ollama down: `kubectl scale deployment ollama -n magenta-mesh --replicas=0` (triggers fallback to hosted)

## Investigation
1. **Token budget exhaustion**:
   - Check `magenta_model_tokens_used_total` vs `daily_token_budget`
   - If budget exceeded: wait for reset or request budget increase
2. **Model routing misconfiguration**:
   - Check `config/llm-routing.yaml` for correct tier ordering
   - Verify `MAGENTA_MODELS_DEFAULT_PROVIDER` set to `ollama`
3. **Resource contention**:
   - GPU memory full (if Ollama on GPU nodes)
   - Concurrent request limit reached

## Rollback
```bash
# Force fallback to cost_save tier (free providers)
kubectl set env deployment/magenta-api -n magenta-soa MAGENTA_MODELS_DEFAULT_PROVIDER=groq

# Disable reasoning tier if hallucinating
kubectl set env deployment/magenta-api -n magenta-soa MAGENTA_MODELS_REASONING_ENABLED=false

# Emergency: static model override
kubectl set env deployment/magenta-api -n magenta-soa MAGENTA_MODELS_DEFAULT_MODEL=qwen2.5:7b
```

## Escalation
- **5 min**: Page on-call (LLM degradation = agent intelligence impaired)
- **15 min**: Engage ML/Platform team (model routing, provider contracts)
- **60 min**: Architecture Board if multi-provider outage (vendor risk)

## Post-Mortem Trigger
- Circuit breaker open > 60 seconds for any tier
- Fallback chain exhausted (all tiers failing)
- Cost spike > 2x budget (token budget alert)
- Hallucinated action executed (safety incident)

---
*Last updated: 2026-06-16 | Owner: Agent Ops Engineer | Review: Quarterly*