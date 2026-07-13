# Runbook: Agent Malfunction

## Alert Definition
- **Alert**: `magenta_agent_down` (Prometheus: `magenta_agent_heartbeat_missing > 3`)
- **Alert**: `magenta_agent_error_rate` (Prometheus: `rate(magenta_agent_errors_total[5m]) > 0.1`)
- **Severity**: High
- **Dashboard**: Grafana "Magenta ASOAR Ops" → Agent Health panel

## Symptoms
- Agent heartbeat missing for > 3 intervals (default 30s interval = 90s)
- Agent status stuck in `error` or `waiting_input`
- Mission tasks assigned to agent not progressing
- High error rate on `execute_tool` or `process` calls

## Immediate Action (First 5 Minutes)
1. Identify affected agent(s): `kubectl get pods -n magenta-agents -l role=<role>`
2. Check agent logs: `kubectl logs -n magenta-agents -l role=<role> --tail=200`
3. Check mission stuck on agent: `kubectl exec -it <api-pod> -- python -c "from magenta.core.mission import mission_manager; print([m for m in mission_manager.all() if any(a.agent_id == '<agent_id>' for a in m.team)])"`
4. Reset agent: `kubectl delete pod -n magenta-agents -l role=<role>,agent_id=<agent_id>`

## Investigation
1. **LLM Provider Issues**:
   - Ollama unresponsive: `kubectl exec -it <ollama-pod> -- ollama list`
   - Hosted API (Groq/Gemini) rate limited: check `magenta_model_provider_errors_total`
   - Circuit breaker open: `magenta_model_circuit_open_total` metric
2. **Tool Execution Failures**:
   - MCP Bridge connectivity: `curl http://mcp-bridge:8080/mcp/health`
   - Tool timeout: check `magenta_tool_latency_seconds` histogram
3. **Resource Exhaustion**:
   - OOMKilled: check pod events, increase memory limit
   - CPU throttling: check `container_cpu_cfs_throttled_periods_total`

## Rollback
```bash
# Rollback agent deployment to previous version
kubectl rollout undo deployment/agent-<role> -n magenta-agents

# Drain missions from malfunctioning agent
kubectl exec -it <api-pod> -- python -c "
from magenta.core.mission import mission_manager
from magenta.core.agent import agent_registry
for mission in mission_manager.all():
    for agent_config in mission.team:
        if agent_config.agent_id == '<bad_agent_id>':
            agent_registry.unregister(agent_config.agent_id)
            mission_manager.reassign_tasks(mission.mission_id, agent_config.role)
"
```

## Escalation
- **10 min**: Page on-call (agent down = mission capacity reduced)
- **30 min**: Engage Agent Ops Engineer (model routing, prompt issues)
- **60 min**: Architecture Board if systemic (multiple agents, model provider outage)

## Post-Mortem Trigger
- Agent down > 10 minutes causing mission SLA breach
- Cascade failure (one agent failure triggers others)
- LLM hallucination causing incorrect action (safety incident)
- Prompt injection attempt detected

---
*Last updated: 2026-06-16 | Owner: Agent Ops Engineer | Review: Quarterly*