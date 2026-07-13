"""Magenta Worker — Background task processor for missions, approvals, outbox."""

import asyncio
import logging
import signal

from magenta.orchestration.outbox import get_outbox_publisher
from magenta.response.executor import approval_gate

logger = logging.getLogger(__name__)


class Worker:
    """Background worker that processes missions, approvals, and outbox events."""

    def __init__(self, concurrency: int = 5):
        self._concurrency = concurrency
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        self._running = True
        logger.info("Worker started with concurrency %d", self._concurrency)

        # Start outbox publisher
        publisher = await get_outbox_publisher()
        await publisher.start()

        # Start background loops
        self._tasks.append(asyncio.create_task(self._approval_loop()))
        self._tasks.append(asyncio.create_task(self._mission_loop()))

        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

        publisher = await get_outbox_publisher()
        await publisher.stop()

        logger.info("Worker stopped")

    async def _approval_loop(self) -> None:
        """Process pending approvals."""
        while self._running:
            try:
                pending = await approval_gate.list_pending()
                for approval in pending:
                    logger.debug("Processing approval %s: %s", approval["id"], approval["action"])
            except Exception as exc:
                logger.warning("Approval loop error: %s", exc)
            await asyncio.sleep(30)

    async def _mission_loop(self) -> None:
        """Check for missions that need processing."""
        while self._running:
            try:
                from magenta.core.mission import mission_manager
                from magenta.core.models import MissionStatus

                active = mission_manager.list_active()
                for mission in active:
                    if mission.status == MissionStatus.created:
                        logger.info("Auto-starting mission %s", mission.mission_id)
                        from magenta.orchestration.engine import orchestration_engine

                        await orchestration_engine.start_mission(mission.mission_id)
            except Exception as exc:
                logger.warning("Mission loop error: %s", exc)
            await asyncio.sleep(10)


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    worker = Worker(concurrency=args.concurrency)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(worker.stop()))

    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
