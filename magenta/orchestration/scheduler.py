"""Task scheduler for periodic and cron-based missions."""

from typing import Any, Callable, Awaitable, Optional
import asyncio
from datetime import datetime
import re


class Scheduler:
    """Simple async scheduler for periodic and cron-like tasks."""

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._handlers: dict[str, Callable] = {}

    async def add_interval(
        self,
        name: str,
        handler: Callable[[], Awaitable[None]],
        interval_seconds: int,
    ) -> None:
        """Add a task that runs at a fixed interval."""
        self._handlers[name] = handler

        async def loop():
            try:
                while True:
                    await handler()
                    await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                pass

        self._tasks[name] = asyncio.create_task(loop())

    async def remove(self, name: str) -> None:
        """Remove a scheduled task."""
        task = self._tasks.pop(name, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._handlers.pop(name, None)

    async def list(self) -> list[dict]:
        """List scheduled tasks."""
        return [
            {"name": name, "running": not task.done()}
            for name, task in self._tasks.items()
        ]

    async def stop_all(self) -> None:
        """Stop all scheduled tasks."""
        for name in list(self._tasks.keys()):
            await self.remove(name)


scheduler = Scheduler()
