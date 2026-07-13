"""Idempotency key store — check-before-act pattern for Execution Agent.

Prevents duplicate action execution during agent restarts, Event Hubs
redelivery, or orchestrator retries.

Backed by Azure Table Storage with 24-hour TTL.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime

from magenta.config import settings
from magenta.exceptions import DuplicateActionError

logger = logging.getLogger(__name__)


class IdempotencyStore:
    """
    Azure Table Storage-backed idempotency store.

    Table schema:
        PartitionKey: alert_id[:8]
        RowKey: sha256(alert_id + action + target_id)
        TTL: 24 hours (handled by Table Storage)

    Usage:
        store = IdempotencyStore()
        try:
            await store.check_and_register(alert_id, action, target_id)
            # Proceed with action
        except DuplicateActionError:
            # Skip — already executed
    """

    def __init__(self):
        self._table_client: Any | None = None
        self._initialized = False

    async def _ensure_table(self) -> Any:
        """Lazy-init and return the table client."""
        if self._initialized and self._table_client:
            return self._table_client

        try:
            from azure.data.tables import TableServiceClient

            conn_str = settings.idempotency.storage_connection_string
            if not conn_str:
                logger.warning(
                    "IdempotencyStore: no storage_connection_string configured — "
                    "using in-memory fallback"
                )
                self._table_client = _InMemoryTable()
                self._initialized = True
                return self._table_client

            service = TableServiceClient.from_connection_string(conn_str=conn_str)
            self._table_client = service.get_table_client(settings.idempotency.table_name)
            await self._table_client.create_table_if_not_exists()
            self._initialized = True
            return self._table_client

        except ImportError:
            logger.warning(
                "IdempotencyStore: azure-data-tables not available — using in-memory fallback"
            )
            self._table_client = _InMemoryTable()
            self._initialized = True
            return self._table_client

    def _make_key(self, alert_id: str, action: str, target_id: str) -> tuple[str, str]:
        """Generate PartitionKey and RowKey from alert/action/target."""
        raw = f"{alert_id}:{action}:{target_id}"
        key_hash = hashlib.sha256(raw.encode()).hexdigest()
        partition_key = alert_id[:8]
        return partition_key, key_hash

    async def check_and_register(
        self,
        alert_id: str,
        action: str,
        target_id: str,
    ) -> bool:
        """Check if action was already executed and register if new.

        Returns:
            True if this is the first time (action can proceed).

        Raises:
            DuplicateActionError: If this action was already executed.
        """
        client = await self._ensure_table()
        partition_key, row_key = self._make_key(alert_id, action, target_id)

        entity = {
            "PartitionKey": partition_key,
            "RowKey": row_key,
            "alert_id": alert_id,
            "action": action,
            "target_id": target_id,
            "created_at": datetime.utcnow().isoformat(),
        }

        try:
            await client.upsert_entity(entity)
            logger.debug(
                "Idempotency: registered %s:%s:%s → %s",
                alert_id[:8],
                action,
                target_id,
                row_key[:12],
            )
            return True
        except DuplicateActionError:
            raise
        except Exception as e:
            # If table storage is unavailable, log and allow (fail open)
            logger.warning(
                "Idempotency: store unavailable for %s:%s:%s — allowing (%s)",
                alert_id[:8],
                action,
                target_id,
                e,
            )
            return True

    async def exists(
        self,
        alert_id: str,
        action: str,
        target_id: str,
    ) -> bool:
        """Check if an idempotency key exists without registering."""
        client = await self._ensure_table()
        partition_key, row_key = self._make_key(alert_id, action, target_id)

        try:
            await client.get_entity(partition_key, row_key)
            return True
        except Exception:
            return False


class _InMemoryTable:
    """In-memory fallback for idempotency when Azure Table Storage is unavailable.

    Used during development and testing. Not durable across restarts.
    """

    def __init__(self):
        self._entities: dict[tuple[str, str], dict] = {}

    async def upsert_entity(self, entity: dict) -> dict:
        key = (entity["PartitionKey"], entity["RowKey"])
        if key in self._entities:
            raise DuplicateActionError(f"Action already executed (key: {entity['RowKey'][:12]}...)")
        self._entities[key] = entity
        return entity

    async def get_entity(self, partition_key: str, row_key: str) -> dict:
        key = (partition_key, row_key)
        if key not in self._entities:
            raise KeyError(f"Entity not found: {partition_key}/{row_key}")
        return self._entities[key]

    async def create_table_if_not_exists(self) -> None:
        pass


# Singleton
idempotency_store = IdempotencyStore()
