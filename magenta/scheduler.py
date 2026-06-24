"""Magenta Scheduler — Cron scheduler for playbooks, collectors, maintenance."""

import asyncio
import logging
import signal
from datetime import datetime, timedelta

from magenta.core.mission import mission_manager
from magenta.core.models import MissionStatus

logger = logging.getLogger(__name__)


class Scheduler:
    """Cron-like scheduler for recurring tasks."""

    def __init__(self):
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        self._running = True
        logger.info("Scheduler started")

        self._tasks.append(asyncio.create_task(self._cron_loop()))
        self._tasks.append(asyncio.create_task(self._maintenance_loop()))

        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("Scheduler stopped")

    async def _cron_loop(self) -> None:
        """Run scheduled playbooks based on cron expressions."""
        while self._running:
            try:
                # Check for playbooks with cron triggers
                playbooks = mission_manager.list()  # This would be playbook_manager in reality
                now = datetime.utcnow()
                for pb in playbooks:
                    if hasattr(pb, 'trigger') and pb.trigger and pb.trigger.get('type') == 'cron':
                        cron_expr = pb.trigger.get('cron', '')
                        if self._should_run(cron_expr, now):
                            logger.info("Triggering scheduled playbook: %s", pb.name)
                            # Create mission from playbook
                            # This would trigger the actual playbook execution
            except Exception as exc:
                logger.warning("Cron loop error: %s", exc)
            await asyncio.sleep(60)  # Check every minute

    async def _maintenance_loop(self) -> None:
        """Run periodic maintenance tasks."""
        while self._running:
            try:
                # Clean up old completed missions
                await self._cleanup_old_missions()
                # Process outbox retries
                await self._process_outbox_retries()
            except Exception as exc:
                logger.warning("Maintenance loop error: %s", exc)
            await asyncio.sleep(300)  # Every 5 minutes

    def _should_run(self, cron_expr: str, now: datetime) -> bool:
        """Simple cron expression matcher (minute hour day month dow)."""
        try:
            parts = cron_expr.split()
            if len(parts) != 5:
                return False
            minute, hour, day, month, dow = parts
            if minute != '*' and int(minute) != now.minute:
                return False
            if hour != '*' and int(hour) != now.hour:
                return False
            if day != '*' and int(day) != now.day:
                return False
            if month != '*' and int(month) != now.month:
                return False
            if dow != '*' and int(dow) != now.weekday():
                return False
            return True
        except Exception:
            return False

    async def _cleanup_old_missions(self) -> None:
        """Archive missions older than retention period."""
        cutoff = datetime.utcnow() - timedelta(days=30)
        missions = mission_manager.list()
        for m in missions:
            if m.status in (MissionStatus.completed, MissionStatus.failed, MissionStatus.cancelled):
                if m.completed_at and m.completed_at < cutoff:
                    logger.info("Archiving old mission: %s", m.mission_id)
                    # In production, would move to cold-store to archive table instead of delete

    async def _process_outbox_retries(self) -> None:
        """Process failed outbox events for retry."""
        from magenta.data.sql.outbox import get_outbox_publisher
        await get_outbox_publisher()
        # The publisher's _run_loop already handles retries


async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="/app/config/system.toml")
    parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    scheduler = Scheduler()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(scheduler.stop()))

    await scheduler.start()


if __name__ == "__main__":
    asyncio.run(main())
