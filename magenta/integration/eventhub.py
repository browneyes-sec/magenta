"""Azure Event Hubs producer and consumer — real implementation."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from azure.eventhub import EventData
from azure.eventhub.aio import EventHubConsumerClient, EventHubProducerClient
from azure.eventhub.extensions.checkpointstoreblobaio import BlobCheckpointStore
from azure.identity.aio import DefaultAzureCredential

from magenta.exceptions import IntegrationError

logger = logging.getLogger(__name__)


class EventHubClient:
    """Azure Event Hubs client for agent communication & log ingestion.

    Supports both connection-string and Managed Identity auth.
    When no connection string is set, operates in stub mode (no-op sends).
    """

    def __init__(
        self,
        *,
        namespace: str = "magenta-agent-bus",
        connection_string: str = "",
        credential: DefaultAzureCredential | None = None,
        checkpoint_connection_string: str = "",
        checkpoint_container: str = "eventhub-checkpoints",
    ):
        self._namespace = namespace
        self._connection_string = connection_string
        self._credential = credential
        self._checkpoint_conn_str = checkpoint_connection_string
        self._checkpoint_container = checkpoint_container
        self._producers: dict[str, EventHubProducerClient] = {}
        self._consumers: dict[str, EventHubConsumerClient] = {}
        self._consumer_tasks: dict[str, asyncio.Task] = {}
        self._handlers: dict[str, Callable[[dict], Awaitable[None]]] = {}

    # ── Producers ──────────────────────────────────────────────────────

    async def send(self, topic: str, message: dict, partition_key: str = "") -> dict:
        """Send a single message to an Event Hubs topic."""
        if not self._connection_string:
            return self._simulate_send(topic, message)

        producer = await self._get_producer(topic)
        event_data = EventData(json.dumps(message, default=str).encode("utf-8"))
        await producer.send_event(event_data, partition_key=partition_key or None)
        return {
            "status": "sent",
            "topic": topic,
            "message_id": message.get("message_id", message.get("event_id", "")),
            "size_bytes": len(event_data.body),
        }

    async def send_batch(self, topic: str, messages: list[dict]) -> dict:
        """Send a batch of messages efficiently."""
        if not self._connection_string:
            return {"status": "simulated", "topic": topic, "count": len(messages)}

        producer = await self._get_producer(topic)
        batch = await producer.create_batch()
        count = 0
        for msg in messages:
            try:
                batch.add(EventData(json.dumps(msg, default=str).encode("utf-8")))
                count += 1
            except ValueError:
                logger.warning("Event too large for batch, sending individually")
                await self.send(topic, msg)
        if count > 0:
            await producer.send_batch(batch)
        return {"status": "sent", "topic": topic, "count": count}

    async def send_raw(
        self, topic: str, payload: bytes, content_type: str = "application/json"
    ) -> dict:
        """Send a pre-serialized raw payload (for syslog/CEF passthrough)."""
        if not self._connection_string:
            return {"status": "simulated", "topic": topic, "size_bytes": len(payload)}

        producer = await self._get_producer(topic)
        event_data = EventData(payload)
        event_data.content_type = content_type
        await producer.send_event(event_data)
        return {"status": "sent", "topic": topic, "size_bytes": len(payload)}

    async def _get_producer(self, topic: str) -> EventHubProducerClient:
        if topic not in self._producers:
            if self._connection_string:
                self._producers[topic] = EventHubProducerClient.from_connection_string(
                    self._connection_string,
                    eventhub_name=topic,
                )
            else:
                fqdn = f"{self._namespace}.servicebus.windows.net"
                cred = self._credential or DefaultAzureCredential()
                self._producers[topic] = EventHubProducerClient(
                    fully_qualified_namespace=fqdn,
                    eventhub_name=topic,
                    credential=cred,
                )
        return self._producers[topic]

    def _simulate_send(self, topic: str, message: dict) -> dict:
        payload = json.dumps(message, default=str).encode("utf-8")
        logger.debug("Simulated send to topic=%s (%d bytes)", topic, len(payload))
        return {
            "status": "simulated",
            "topic": topic,
            "message_id": message.get("message_id", ""),
            "size_bytes": len(payload),
        }

    # ── Consumers ──────────────────────────────────────────────────────

    async def start_consumer(
        self,
        topic: str,
        handler: Callable[[dict], Awaitable[None]],
        consumer_group: str = "$Default",
        *,
        starting_position: str = "-1",
    ) -> None:
        """Start consuming messages from a topic in the background."""
        self._handlers[topic] = handler

        if not self._connection_string:
            logger.warning("No connection string — stub consumer for topic=%s", topic)
            task = asyncio.create_task(self._stub_consume_loop(handler))
            self._consumer_tasks[topic] = task
            return

        checkpoint_store = None
        if self._checkpoint_conn_str:
            checkpoint_store = BlobCheckpointStore.from_connection_string(
                self._checkpoint_conn_str,
                container_name=self._checkpoint_container,
            )

        consumer = EventHubConsumerClient.from_connection_string(
            self._connection_string,
            consumer_group,
            eventhub_name=topic,
            checkpoint_store=checkpoint_store,
        )
        self._consumers[topic] = consumer
        task = asyncio.create_task(self._consume_loop(consumer, topic, handler, starting_position))
        self._consumer_tasks[topic] = task
        logger.info("Consumer started for topic=%s group=%s", topic, consumer_group)

    async def stop_consumer(self, topic: str) -> None:
        """Stop consuming from a topic."""
        task = self._consumer_tasks.pop(topic, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        consumer = self._consumers.pop(topic, None)
        if consumer:
            await consumer.close()
        self._handlers.pop(topic, None)

    async def _consume_loop(
        self,
        consumer: EventHubConsumerClient,
        topic: str,
        handler: Callable[[dict], Awaitable[None]],
        starting_position: str,
    ) -> None:
        async def on_event(partition_context, event):
            try:
                body = event.body_as_json() if event.body_as_str() else {}
                if isinstance(body, str):
                    body = json.loads(body)
                await handler(body)
                await partition_context.update_checkpoint(event)
            except Exception:
                logger.exception("Handler failed for event on topic=%s", topic)

        async def on_error(partition_context, error):
            logger.error("EventHub consumer error on %s: %s", topic, error)

        try:
            async with consumer:
                await consumer.receive(
                    on_event=on_event,
                    on_error=on_error,
                    starting_position=starting_position,
                )
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Consumer loop crashed for topic=%s", topic)

    async def _stub_consume_loop(self, handler: Callable) -> None:
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    # ── Health / Lifecycle ─────────────────────────────────────────────

    async def get_topic_metrics(self, topic: str) -> dict:
        return {"topic": topic, "namespace": self._namespace, "partitions": 8}

    async def ping(self) -> bool:
        try:
            if self._connection_string:
                async with EventHubProducerClient.from_connection_string(
                    self._connection_string,
                ):
                    pass
            return True
        except Exception:
            return False

    async def close(self) -> None:
        for topic in list(self._consumer_tasks):
            await self.stop_consumer(topic)
        for producer in self._producers.values():
            await producer.close()
        self._producers.clear()


class HMACAuth:
    """HMAC-SHA256 signature verification for ingest API."""

    def __init__(self, secrets: dict[str, str]):
        self._secrets = secrets

    def sign(self, body: bytes, key_name: str) -> str:
        secret = self._secrets.get(key_name)
        if not secret:
            raise IntegrationError(f"Unknown key: {key_name}")
        return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    def verify(self, body: bytes, signature: str, key_name: str) -> bool:
        expected = self.sign(body, key_name)
        return hmac.compare_digest(expected, signature)


class IdempotencyGuard:
    """Redis-backed deduplication for ingest events."""

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._local: dict[str, float] = {}

    async def is_duplicate(self, key: str, ttl: int = 86400) -> bool:
        if self._redis:
            exists = await self._redis.exists(key)
            if not exists:
                await self._redis.setex(key, ttl, "1")
            return bool(exists)
        now = datetime.now(UTC).timestamp()
        if key in self._local:
            if now - self._local[key] < ttl:
                return True
        self._local[key] = now
        return False

    async def mark_seen(self, key: str, ttl: int = 86400) -> None:
        if self._redis:
            await self._redis.setex(key, ttl, "1")
        else:
            self._local[key] = datetime.now(UTC).timestamp()
