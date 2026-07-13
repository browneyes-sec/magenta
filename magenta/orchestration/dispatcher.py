"""Task dispatcher — routes tasks to available agents and dispatches to SOAR."""

from __future__ import annotations

from typing import Any, Optional
from datetime import datetime
import asyncio
import logging

from magenta.core.models import Mission, AgentConfig, AutomationActivity, ActionStatus
from magenta.core.agent import agent_registry
from magenta.core.playbook import playbook_manager
from magenta.core.registry import registry_writer
from magenta.exceptions import AgentError, IntegrationError
from magenta.integration.soar import SOARConnector

logger = logging.getLogger(__name__)


class Dispatcher:
    """Dispatches tasks to agents based on role, load, and availability."""

    async def dispatch(self, task: dict, mission: Mission) -> Optional[str]:
        """Dispatch a task to an available agent. Returns agent_id or None."""
        role = task.get("role")
        if not role:
            raise AgentError(f"Task {task.get('task_id')} has no role")

        agents = agent_registry.get_available(role)
        if not agents:
            return None

        # Pick least-loaded agent
        agent = min(agents, key=lambda a: a.turn_count)
        task["agent_id"] = agent.agent_id
        task["status"] = "assigned"
        agent.current_mission = mission
        agent.status = "ready"

        return agent.agent_id

    async def dispatch_all(self, tasks: list[dict], mission: Mission) -> list[dict]:
        """Dispatch all pending tasks."""
        results = []
        for task in tasks:
            if task.get("status") == "pending":
                agent_id = await self.dispatch(task, mission)
                results.append({
                    "task_id": task["task_id"],
                    "agent_id": agent_id or "unassigned",
                    "status": "assigned" if agent_id else "unassigned",
                })
        return results

    async def retry_failed(self, task: dict, mission: Mission) -> Optional[str]:
        """Retry a failed task with a different agent."""
        return await self.dispatch(task, mission)


class SOARDispatcher:
    """
    SOAR Outreach Gate — dispatches missions to Splunk SOAR.

    Lifecycle:
        1. Resolve playbook name from routing rules
        2. Create SOAR container with enriched alert context
        3. Post agent reasoning as a SOAR note
        4. Trigger the mapped playbook
        5. Poll action run status asynchronously
        6. Register each state transition as automation.activity
    """

    def __init__(self, soar_connector: Optional[SOARConnector] = None):
        self.soar = soar_connector or SOARConnector()
        self._active_polls: dict[str, asyncio.Task] = {}

    async def dispatch(
        self,
        mission: Mission,
        alert_type: str = "",
    ) -> dict[str, Any]:
        """Dispatch a mission to SOAR and track its lifecycle.

        Args:
            mission: The mission to dispatch (must have correlation_id, alert_id, etc.)
            alert_type: Alert type string for routing rule resolution
                (e.g., "IdentityCompromise", "Phishing", "Malware")

        Returns:
            Dict with container_id, playbook_name, run_id
        """
        # Step 1: Resolve playbook from routing rules
        rule = await playbook_manager.resolve(
            alert_type=alert_type or "default",
            severity=mission.severity.value,
            risk_score=mission.risk_score,
        )
        playbook_name = rule["playbook_name"]
        logger.info(
            "SOARDispatcher[%s]: resolved playbook '%s' for alert %s",
            mission.correlation_id[:8],
            playbook_name,
            mission.alert_id,
        )

        # Step 2: Create SOAR container
        container = await self.soar.create_container({
            "correlation_id": mission.correlation_id,
            "alert_id": mission.alert_id,
            "source_system": mission.source_system.value,
            "severity": mission.severity.value,
            "risk_score": mission.risk_score,
            "description": mission.description,
            "playbook_id": playbook_name,
            "tags": [
                f"correlation_id:{mission.correlation_id}",
                f"severity:{mission.severity.name}",
                f"source:{mission.source_system.value}",
            ],
        })
        container_id = container.get("id", "")
        logger.info(
            "SOARDispatcher[%s]: created container %s",
            mission.correlation_id[:8],
            container_id,
        )

        # Step 3: Register container creation in registry
        await registry_writer.write_activity(
            AutomationActivity(
                source_system=mission.source_system,
                source_alert_id=mission.alert_id,
                action="soar_container_created",
                status=ActionStatus.queued,
                correlation_id=mission.correlation_id,
                executor={"type": "agent", "id": "soar_dispatcher"},
                target={"type": "host", "id": container_id},
            )
        )

        # Step 4: Trigger playbook
        playbook_run = await self.soar.trigger_playbook(
            container_id, playbook_name
        )
        run_id = playbook_run.get("run_id", "")

        # Register playbook trigger
        await registry_writer.write_activity(
            AutomationActivity(
                source_system=mission.source_system,
                source_alert_id=mission.alert_id,
                action="soar_playbook_triggered",
                status=ActionStatus.executing,
                correlation_id=mission.correlation_id,
                executor={"type": "agent", "id": "soar_dispatcher"},
                target={"type": "host", "id": container_id},
            )
        )

        # Step 5: Post agent reasoning as SOAR note
        await self.soar.post_note(
            container_id,
            (
                f"[Magenta] Dispatched playbook '{playbook_name}' "
                f"(run_id: {run_id}) for alert {mission.alert_id}. "
                f"Risk score: {mission.risk_score}. "
                f"Severity: {mission.severity.name}."
            ),
        )
        logger.info(
            "SOARDispatcher[%s]: triggered playbook %s (run %s)",
            mission.correlation_id[:8],
            playbook_name,
            run_id,
        )

        # Step 6: Start async polling for run status
        poll_key = f"{container_id}:{run_id}"
        poll_task = asyncio.create_task(
            self._poll_run_status(container_id, run_id, mission)
        )
        self._active_polls[poll_key] = poll_task

        return {
            "container_id": container_id,
            "playbook_name": playbook_name,
            "run_id": run_id,
        }

    async def _poll_run_status(
        self,
        container_id: str,
        run_id: str,
        mission: Mission,
    ) -> None:
        """Poll playbook run status and update registry on state transitions.

        Polls every 10 seconds for up to 5 minutes (30 attempts).
        """
        max_polls = 30
        poll_interval = 10  # seconds

        for attempt in range(max_polls):
            await asyncio.sleep(poll_interval)
            try:
                runs = await self.soar.get_playbook_runs(container_id)
                for run in runs:
                    if run.get("id") == run_id:
                        status = run.get("status", "unknown")

                        # Map SOAR status to ActionStatus
                        status_map = {
                            "running": ActionStatus.executing,
                            "succeeded": ActionStatus.succeeded,
                            "completed": ActionStatus.succeeded,
                            "failed": ActionStatus.failed,
                            "cancelled": ActionStatus.rejected,
                        }
                        action_status = status_map.get(
                            status, ActionStatus.executing
                        )

                        await registry_writer.write_activity(
                            AutomationActivity(
                                source_system=mission.source_system,
                                source_alert_id=mission.alert_id,
                                action=f"soar_playbook_{status}",
                                status=action_status,
                                correlation_id=mission.correlation_id,
                                executor={
                                    "type": "agent",
                                    "id": "soar_dispatcher",
                                },
                                target={"type": "host", "id": container_id},
                            )
                        )

                        if status in ("succeeded", "completed", "failed", "cancelled"):
                            logger.info(
                                "SOARDispatcher[%s]: playbook run %s → %s "
                                "(after %d polls)",
                                mission.correlation_id[:8],
                                run_id,
                                status,
                                attempt + 1,
                            )
                            return

            except (IntegrationError, Exception) as e:
                logger.warning(
                    "SOARDispatcher[%s]: poll attempt %d failed: %s",
                    mission.correlation_id[:8],
                    attempt + 1,
                    e,
                )
                continue

        logger.warning(
            "SOARDispatcher[%s]: playbook run %s polling exhausted after %d attempts",
            mission.correlation_id[:8],
            run_id,
            max_polls,
        )


dispatcher = Dispatcher()
soar_dispatcher = SOARDispatcher()
