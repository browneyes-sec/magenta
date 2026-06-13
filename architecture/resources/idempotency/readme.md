# Idempotency Architecture

## Component Overview

Idempotency prevents duplicate execution of the same action for the same alert-target combination. Every `automation.activity` event carries an `idempotency_key` that must be checked before action execution.

DTP reference: §2.3 (idempotency_key), §7.2, §9 (Risk Register: duplicate execution)

## Idempotency Key Derivation

```python
def generate_idempotency_key(source_alert_id: str, action: str, target_id: str) -> str:
    """
    Deterministic key from alert + action + target.
    Same input always produces same key.
    """
    raw = f"{source_alert_id}:{action}:{target_id}"
    return hashlib.sha256(raw.encode()).hexdigest()
```

Example:
```
Input:  "sentinel-incident-8932:disable_account:jdoe@contoso.com"
Output: "a1b2c3d4e5f6..."  (SHA-256 hex digest)
```

## Lifecycle

```
Alert arrives
    │
    ▼
Normalizer Agent
    │ generates idempotency_key ← sha256(source_alert_id + action + target_id)
    │ publishes to enriched-alerts with key
    ▼
Orchestrator Agent
    │ evaluates routing rules, determines action
    │ CHECK: idempotency store for key
    │
    ├── Key EXISTS with status "succeeded" ──► SKIP (already done)
    ├── Key EXISTS with status "failed" ──► RETRY (if within retry limit)
    ├── Key EXISTS with status "executing" ──► WAIT (concurrent execution)
    └── Key NOT FOUND ──► PROCEED with execution
```

## Check-Before-Act Pattern

```python
class IdempotencyStore:
    def __init__(self, backend: str = "redis"):
        if backend == "redis":
            self._store = RedisIdempotencyStore()
        else:
            self._store = TableStorageIdempotencyStore()

    async def check_and_claim(self, key: str, ttl: int = 86400) -> IdempotencyResult:
        """
        Atomic check-and-set to prevent race conditions.
        Returns:
          - new: first time seeing this key
          - already_done: key exists with terminal status
          - in_progress: another execution is running
        """
        existing = await self._store.get(key)
        if existing:
            if existing["status"] in ("succeeded", "rejected"):
                return IdempotencyResult(status="already_done", detail=existing)
            elif existing["status"] == "failed":
                # Allow retry if below max retries
                if existing.get("retry_count", 0) < 3:
                    return IdempotencyResult(status="new")
                return IdempotencyResult(status="already_done", detail=existing)
            else:
                return IdempotencyResult(status="in_progress")

        # Claim the key atomically
        claimed = await self._store.setnx(key, {
            "status": "executing",
            "started_at": datetime.utcnow().isoformat(),
            "retry_count": 0,
        }, ttl=ttl)
        if not claimed:
            return IdempotencyResult(status="in_progress")

        return IdempotencyResult(status="new")

    async def complete(self, key: str, status: str, result: dict):
        """Mark key as completed with final status."""
        await self._store.update(key, {
            "status": status,
            "completed_at": datetime.utcnow().isoformat(),
            "result": result,
        })
```

## Backend Options

### Redis

```python
class RedisIdempotencyStore:
    def __init__(self, redis_client, prefix="idempotency"):
        self._redis = redis_client
        self._prefix = prefix

    async def get(self, key: str) -> Optional[dict]:
        data = await self._redis.get(f"{self._prefix}:{key}")
        return json.loads(data) if data else None

    async def setnx(self, key: str, value: dict, ttl: int) -> bool:
        return await self._redis.setnx(f"{self._prefix}:{key}", json.dumps(value))

    async def update(self, key: str, value: dict):
        await self._redis.set(f"{self._prefix}:{key}", json.dumps(value))
```

### Azure Table Storage

```python
class TableStorageIdempotencyStore:
    def __init__(self, connection_string: str, table_name: str = "Idempotency"):
        from azure.data.tables import TableClient
        self._client = TableClient.from_connection_string(connection_string, table_name)

    async def get(self, key: str) -> Optional[dict]:
        try:
            entity = await self._client.get_entity(partition_key="idempotency", row_key=key)
            return dict(entity)
        except ResourceNotFoundError:
            return None

    async def setnx(self, key: str, value: dict, ttl: int) -> bool:
        try:
            await self._client.create_entity({
                "PartitionKey": "idempotency",
                "RowKey": key,
                **value,
                "expires_at": datetime.utcnow() + timedelta(seconds=ttl),
            })
            return True
        except ResourceExistsError:
            return False

    async def update(self, key: str, value: dict):
        await self._client.upsert_entity({
            "PartitionKey": "idempotency",
            "RowKey": key,
            **value,
        })
```

## Configuration

```yaml
idempotency:
  backend: redis
  ttl_hours: 24
  key_prefix: "idempotency"
  retry_policy:
    max_retries: 3
    backoff_seconds: [5, 30, 120]
    retryable_statuses: ["failed", "timeout"]

  # For Table Storage:
  connection_string: "${IDEMPOTENCY_STORAGE_CONNECTION}"
  table_name: "Idempotency"
```

## Coverage Matrix

| Action Type | Idempotency Critical? | Duplicate Risk |
|---|---|---|
| `disable_account` | High | Account already disabled → error |
| `isolate_host` | High | Already isolated → unnecessary disruption |
| `create_ticket` | Medium | Duplicate tickets → analyst confusion |
| `block_ip` | High | Already blocked → no-op, but clean audit needed |
| `reset_password` | High | Duplicate resets → user lockout |
| `enable_mfa` | Medium | Already enabled → no-op |
| `notify_user` | Low | Duplicate notification → annoyance |
| `escalate_ticket` | Medium | Duplicate escalations → noise |

## Race Condition Protection

When multiple orchestrator instances consume the same alert:

```
Instance A: check idempotency → not found → SETNX → success → execute
Instance B: check idempotency → not found → SETNX → fail (exists) → skip
                                    ↑
                            Atomic operation prevents
                            concurrent execution
```

## Monitoring

| Metric | Alert |
|---|---|
| Idempotency hit rate (duplicates prevented) | Report — show value |
| Idempotency store latency p99 > 20 ms | Warning |
| SETNX contention errors > 0.1% | Warning |
| Expired key retention cleanup > 1000/hour | Info — tune TTL |
| Retry count > max_retries > 0 | Investigate failing actions |
