"""Azure Event Hubs producer and consumer."""

from typing import Any, Optional, Callable, Awaitable
import json
import asyncio

from magenta.exceptions import IntegrationError


class EventHubClient:
    """
    Azure Event Hubs client for agent communication.
    Supports send/receive with Kafka-compatible protocol.
    """

    def __init__(
        self,
        connection_string: str = "",
        namespace: str = "magenta-agent-bus",
        topics: dict[str, str] = None,
    ):
        self.connection_string = connection_string
        self.namespace = namespace
        self.topics = topics or {}
        self._consumer_tasks: dict[str, asyncio.Task] = {}
        self._handlers: dict[str, Callable] = {}

    async def send(self, topic: str, message: dict) -> dict:
        """Send a message to an Event Hubs topic."""
        topic_name = self.topics.get(topic, topic)
        payload = json.dumps(message, default=str).encode("utf-8")

        # Stub — real implementation uses azure-eventhub or kafka-python
        return {
            "status": "sent",
            "topic": topic_name,
            "message_id": message.get("message_id", ""),
            "size_bytes": len(payload),
        }

    async def send_batch(self, topic: str, messages: list[dict]) -> dict:
        """Send a batch of messages."""
        count = len(messages)
        for msg in messages:
            await self.send(topic, msg)
        return {"status": "sent", "topic": topic, "count": count}

    async def start_consumer(
        self,
        topic: str,
        handler: Callable[[dict], Awaitable[None]],
        consumer_group: str = "$Default",
    ) -> None:
        """Start consuming messages from a topic."""
        topic_name = self.topics.get(topic, topic)
        self._handlers[topic_name] = handler

        task = asyncio.create_task(
            self._consume_loop(topic_name, handler)
        )
        self._consumer_tasks[topic_name] = task

    async def stop_consumer(self, topic: str) -> None:
        """Stop consuming from a topic."""
        topic_name = self.topics.get(topic, topic)
        task = self._consumer_tasks.pop(topic_name, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _consume_loop(
        self,
        topic: str,
        handler: Callable[[dict], Awaitable[None]],
    ) -> None:
        """Background consumer loop (stub — real implementation polls Event Hubs)."""
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    async def get_topic_metrics(self, topic: str) -> dict:
        """Get metrics for a topic."""
        return {
            "topic": self.topics.get(topic, topic),
            "lag": 0,
            "throughput": 0,
            "partition_count": 8,
        }

    async def ping(self) -> bool:
        try:
            return True
        except Exception:
            return False
