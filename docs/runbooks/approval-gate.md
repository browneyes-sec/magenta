# Runbook: Approval Gate

## Alert Definition
- **Alert**: `magenta_approval_queue_stale` (Prometheus: `magenta_approval_pending > 0 for 20m`)
- **Alert**: `magenta_approval_gate_down` (Prometheus: `up{job="magenta-approvals"} == 0`)
- **Severity**: Critical (pages on-call immediately)
- **Dashboard**: Grafana "Magenta ASOAR Ops" → Approval Queue panel

## Symptoms
- Approval requests pending > 20 minutes
- High-risk actions (blast_radius=enterprise) blocked indefinitely
- SOC analysts cannot approve/deny via UI or API
- Missions stuck in `review` status

## Immediate Action (First 5 Minutes)
1. Check approvals API: `curl -H "Authorization: Bearer $TOKEN" https://api.magenta.soa/api/v1/approvals/pending`
2. Check pod status: `kubectl get pods -n magenta-soa -l app=magenta-api` (approvals route runs in API)
3. Check Entra ID connectivity: verify JWKS endpoint reachable from API pod
4. If Entra ID token validation failing: check `magenta_entra_jwt_errors_total` metric

## Investigation
1. **Entra ID / Auth**:
   - JWKS cache stale? Restart API pods to refresh
   - Token audience/issuer mismatch? Check `MAGENTA_ENTRA_JWT_AUDIENCE` and `ISSUER` config
2. **Database**:
   - Approval table locks: `SELECT * FROM pg_locks WHERE relation = 'approvals'::regclass`
   - Long-running transactions blocking approvals
3. **Notification delivery**:
   - Teams/Slack webhook failing? Check `magenta_notification_failed_total`
   - Approver not receiving notifications

## Rollback
```bash
# If approval gate logic regression:
kubectl rollout undo deployment/magenta-api -n magenta-soa

# Emergency: disable approval gate for low-risk actions only
kubectl set env deployment/magenta-api -n magenta-soa MAGENTA_APPROVAL_BYPASS_LOW_RISK=true
# NOTE: Requires Architecture Board approval, log in deviation log
```

## Escalation
- **Immediate**: Page on-call (approval gate down = no high-risk actions)
- **10 min**: SOC Manager engaged (manual approval process activation)
- **30 min**: Architecture Board Chair (if bypass needed)

## Post-Mortem Trigger
- Any approval queue drain > 30 minutes
- Unauthorized action execution (bypass without approval)
- Entra ID integration failure affecting auth

---
*Last updated: 2026-06-16 | Owner: SRE Team | Review: Quarterly*