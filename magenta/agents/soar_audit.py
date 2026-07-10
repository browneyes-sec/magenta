"""SOAR Audit Agent — timer-driven audit collection from Splunk SOAR.

Runs on a 5-minute timer, polls the SOAR /rest/audit endpoint with a
sliding window, normalizes events to automation.activity schema, and
publishes them to the registry.

Designed to never block or crash — failures in one cycle do not affect
subsequent cycles.
"""

from __future__ import annotations

from typing import Any, Optional
from datetime import datetime, timedelta
import asyncio
import logging

from magenta.agents.base import LLMAgent
from magenta.core.models import (
    AgentConfig,
    Mission,
    AutomationActivity,
    ActionStatus,
    Target,
    Executor,
)
from magenta.core.registry import registry_writer
from magenta.integration.soar import SOARConnector
from magenta.exceptions import IntegrationError

logger = logging.getLogger(__name__)


class SOARAuditAgent:
    """
    Timer-driven agent that polls Splunk SOAR audit trail.

    Collects audit events in 5-minute sliding windows, normalizes them
    to the canonical automation.activity schema, and writes all three
    registry sinks.

    Usage:
        agent = SOARAuditAgent(soar_connector=SOARConnector())
        await agent.start()  # runs forever on 5-minute intervals
        # or:
        await agent.run_audit_cycle()  # single cycle
    """

    def __init__(
        self,
        soar_connector: Optional[SOARConnector] = None,
        interval_seconds: int = 300,  # 5 minutes
        window_overlap_seconds: int = 60,  # 1-minute overlap to prevent gaps
    ):
        self.soar = soar_connector or SOARConnector()
        self.interval = interval_seconds
        self.overlap = window_overlap_seconds
        self._last_poll_end: Optional[datetime] = None
        self._cycle_count: int = 0
        self._running = False

    async def start(self) -> None:
        """Start the infinite audit polling loop.

        Runs until cancelled. Designed for use with asyncio.create_task().
        """
        self._running = True
        logger.info(
            "SOARAuditAgent: started (interval=%ds, overlap=%ds)",
            self.interval,
            self.overlap,
        )

        try:
            while self._running:
                await self.run_audit_cycle()
                self._cycle_count += 1
                await asyncio.sleep(self.interval)
        except asyncio.CancelledError:
            logger.info("SOARAuditAgent: stopped")
            self._running = False
        except Exception as e:
            logger.error("SOARAuditAgent: fatal error: %s", e)
            self._running = False
            raise

    async def stop(self) -> None:
        """Signal the audit loop to stop."""
        self._running = False

    async def run_audit_cycle(self) -> int:
        """Execute one audit polling cycle.

        Returns:
            Number of audit events collected and written.
        """
        now = datetime.utcnow()

        # Build sliding window with overlap
        if self._last_poll_end:
            window_start = self._last_poll_end - timedelta(seconds=self.overlap)
        else:
            window_start = now - timedelta(seconds=self.interval + self.overlap)

        window_end = now
        window_start_str = window_start.isoformat()
        window_end_str = window_end.isoformat()

        logger.debug(
            "SOARAuditAgent: cycle %d — window [%s, %s]",
            self._cycle_count + 1,
            window_start_str,
            window_end_str,
        )

        try:
            audit_events = await self.soar.get_audit_trail(
                start=window_start_str,
                end=window_end_str,
            )
        except (IntegrationError, Exception) as e:
            logger.warning(
                "SOARAuditAgent: audit poll failed on cycle %d: %s",
                self._cycle_count + 1,
                e,
            )
            return 0

        if not audit_events:
            self._last_poll_end = window_end
            return 0

        # Normalize and write each event
        written = 0
        for event in audit_events:
            try:
                activity = self._normalize_to_activity(event, window_start, window_end)
                await registry_writer.write_activity(activity)
                written += 1
            except Exception as e:
                logger.warning(
                    "SOARAuditAgent: failed to normalize/write audit event: %s",
                    e,
                )

        self._last_poll_end = window_end
        logger.info(
            "SOARAuditAgent: cycle %d — collected %d events, wrote %d",
            self._cycle_count + 1,
            len(audit_events),
            written,
        )
        return written

    def _normalize_to_activity(
        self,
        event: dict,
        window_start: datetime,
        window_end: datetime,
    ) -> AutomationActivity:
        """Normalize a SOAR audit event to the canonical automation.activity schema.

        Mapping:
            SOAR audit event → AutomationActivity
        """
        container_id = event.get("container_id", event.get("id", ""))
        event_type = event.get("type", "audit_event")
        user = event.get("user", event.get("actor", "unknown"))

        return AutomationActivity(
            schema_version="1.0",
            source_system="splunk",
            source_alert_id=container_id,
            action=f"soar_audit_{event_type}",
            status=ActionStatus.succeeded,
            correlation_id=event.get("correlation_id", ""),
            executor=Executor(
                type="agent",
                id=f"soar_audit/{user}",
            ),
            target=Target(
                type="host",
                id=container_id,
            ),
            tags=["source:soar_audit", f"event_type:{event_type}"],
        )

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def is_running(self) -> bool:
        return self._running


# Convenience singleton
def create_audit_agent(
    soar_connector: Optional[SOARConnector] = None,
) -> SOARAuditAgent:
    """Create a configured SOAR Audit Agent singleton."""
    return SOARAuditAgent(soar_connector=soar_connector)
