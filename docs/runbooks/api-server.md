# Runbook: API Server

## Alert Definition
- **Alert**: `magenta_api_down` (Prometheus: `up{job="magenta-api"} == 0`)
- **Severity**: Critical (pages on-call)
- **Dashboard**: Grafana "Magenta ASOAR Ops" → API Health panel

## Symptoms
- Health endpoint `/api/v1/health` returns 5xx or times out
- All API routes unavailable
- Missions cannot be created/queried via REST
- OpenWebUI integration shows "backend disconnected"

## Immediate Action (First 5 Minutes)
1. Check pod status: `kubectl get pods -n magenta-soa -l app=magenta-api`
2. Check logs: `kubectl logs -n magenta-soa -l app=magenta-api --tail=100`
3. Check events: `kubectl get events -n magenta-soa --sort-by='.lastTimestamp'`
4. If OOMKilled: increase memory limit in `soa/kubernetes/soa/api.yaml`
5. If CrashLoopBackoff: check configmap/secret mounts

## Investigation
1. **Dependency checks**:
   - Redis: `kubectl exec -it <api-pod> -- redis-cli -h magenta-redis ping`
   - PostgreSQL: `kubectl exec -it <api-pod> -- pg_isready -h magenta-postgres`
   - Event Hubs: check `magenta_eventhub_ping` metric
2. **Config validation**: `kubectl get configmap magenta-config -n magenta-soa -o yaml`
3. **Recent deployments**: `kubectl rollout history deployment/magenta-api -n magenta-soa`

## Rollback
```bash
# Rollback to previous revision
kubectl rollout undo deployment/magenta-api -n magenta-soa

# Verify rollback
kubectl rollout status deployment/magenta-api -n magenta-soa --timeout=60s
```

## Escalation
- **5 min**: Page on-call (API down = no mission ingestion)
- **15 min**: Escalate to Architecture Board Chair (production impact)
- **30 min**: Engage Azure support if AKS/infra related

## Post-Mortem Trigger
- Any outage > 5 minutes
- Data loss detected (missions not persisted)
- Root cause: config drift, dependency failure, or code regression

---
*Last updated: 2026-06-16 | Owner: SRE Team | Review: Quarterly*