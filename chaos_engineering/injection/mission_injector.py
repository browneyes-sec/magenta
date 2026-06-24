"""Mission injector — fault injection for mission state manipulation."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from chaos_engineering.attestation.preparing import ComponentMap

logger = logging.getLogger(__name__)


class MissionInjector:
    """Injects faults into mission state for chaos testing."""

    def set_expired_deadline(self, components: ComponentMap, count: int = 1) -> dict[str, Any]:
        """Set mission deadlines to the past to trigger timeout."""
        from magenta.core.mission import mission_manager

        modified = []
        missions = list(mission_manager._missions.values())

        if not missions:
            return {"modified": [], "reason": "No missions in manager"}

        targets = missions[:count]
        for mission in targets:
            original = mission.completed_at
            mission.completed_at = datetime.utcnow() - timedelta(hours=1)
            modified.append(
                {
                    "mission_id": mission.mission_id[:12],
                    "original_deadline": str(original),
                    "new_deadline": str(mission.completed_at),
                }
            )
            logger.info("Set expired deadline for mission: %s", mission.mission_id[:12])

        return {"modified": modified, "count": len(modified)}

    def corrupt_status(self, components: ComponentMap, count: int = 1) -> dict[str, Any]:
        """Set missions to invalid status values."""
        from magenta.core.mission import mission_manager

        modified = []
        missions = list(mission_manager._missions.values())

        if not missions:
            return {"modified": [], "reason": "No missions in manager"}

        targets = missions[:count]
        for mission in targets:
            original_status = str(mission.status)
            mission.status = "CHAOS_INVALID_STATUS"
            modified.append(
                {
                    "mission_id": mission.mission_id[:12],
                    "original_status": original_status,
                }
            )
            logger.info("Corrupted mission status: %s", mission.mission_id[:12])

        return {"modified": modified, "count": len(modified)}
