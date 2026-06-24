# Runbook: Event Pipeline (Event Hubs → Outbox → Consumers)

## Alert Definition
- **Alert**: `magenta_event_pipeline_lag` (Prometheus: `magenta:event_pipeline_lag > 200 for 5m`)
- **Alert**: `magenta_outbox_orphan_count` (Prometheus: `magenta:outbox_orphan_count > 0 for 5m`)
- **Severity**: High
- **Dashboard**: Grafana "Magenta ASOAR Ops" → Event Pipeline panel

## Symptoms
- Consumer lag > 200 events for > 5 minutes on any topic
- Outbox events stuck in `pending` status > 5 minutes
- Missions not progressing (stuck in `assigned` or `executing`)
- `raw-alerts` topic growing without consumption

## Immediate Action (First 5 Minutes)
1. Check consumer pods: `kubectl get pods -n magenta-soa -l app=magenta-worker`
2. Check outbox publisher logs: `kubectl logs -n magenta-soa -l app=magenta-worker -c outbox-publisher`
3. Check Event Hubs metrics in Azure Portal: namespace → Event Hubs → Metrics → Incoming/Outgoing messages
4. Restart consumer pods if stuck: `kubectl delete pod -n magenta-soa -l app=magenta-worker`

## Investigation
1. **Event Hubs health**:
   - Partition distribution: `az eventhubs eventhub show --name raw-alerts --namespace-name magenta-agent-bus`
   - Consumer group lag: check `azure_eventhub_consumer_lag` metric per partition
2. **Outbox publisher**:
   - Query stuck events: `SELECT * FROM outbox WHERE status='pending' AND attempts < 10 ORDER BY created_at`
   - Check `last_error` column for failure pattern
3. **Dependency failures**:
   - Redis connectivity (checkpoint store)
   - PostgreSQL write latency
   - Network policies blocking Event Hubs egress

## Rollback
```bash
# Scale consumers to 0 to stop processing
kubectl scale deployment magenta-worker -n magenta-soa --replicas=0

# Fix root cause (config, schema, etc.)

# Scale back up
kubectl scale deployment magenta-worker -n magenta-soa --replicas=3
```

## Escalation
- **10 min**: Page on-call (pipeline lag = missed SLAs)
- **30 min**: Escalate to Platform Team (Event Hubs / infra)
- **60 min**: Architecture Board notified (data loss risk)

## Post-Mortem Trigger
- Any lag > 200 events for > 15 minutes
- Outbox orphaned events > 0 after 10 minutes
- Duplicate actions executed (idempotency failure)
- Schema mismatch causing dead-letter queue growth

---
*Last updated: 2026-06-16 | Owner: SRE Team | Review: Quarterly*