"""Directive injector — fault injection for Dictator directive queue flooding."""

from __future__ import annotations

import logging
from typing import Any

from chaos_engineering.attestation.preparing import ComponentMap

logger = logging.getLogger(__name__)


class DirectiveInjector:
    """Injects faults into the Dictator directive system."""

    def flood_directives(
        self, components: ComponentMap, count: int = 100, interval_ms: int = 100
    ) -> dict[str, Any]:
        """Issue rapid-fire directives to overwhelm the Dictator."""
        import time

        from magenta.dictator.directives import DirectivePriority, DirectiveType, issue_directive
        from magenta.dictator.state import dictator_state

        issued = 0
        errors = 0
        start = time.monotonic()

        for i in range(count):
            try:
                issue_directive(
                    dtype=DirectiveType.system_command,
                    target="chaos_test",
                    mission_id=None,
                    payload={"chaos_flood_index": i, "interval_ms": interval_ms},
                    reason=f"Chaos flood directive #{i}",
                    priority=DirectivePriority.low,
                )
                issued += 1
                if interval_ms > 0:
                    time.sleep(interval_ms / 1000.0)
            except Exception as exc:
                errors += 1
                logger.warning("Directive flood error at index %d: %s", i, exc)

        elapsed = time.monotonic() - start

        return {
            "issued": issued,
            "errors": errors,
            "elapsed_seconds": round(elapsed, 2),
            "directives_in_log": len(dictator_state.directive_log),
        }

    def inject_malformed(self, components: ComponentMap, count: int = 3) -> dict[str, Any]:
        """Inject malformed directives into the log."""
        from magenta.dictator.state import dictator_state

        injected = 0
        for i in range(count):
            dictator_state.log_directive(
                {
                    "type": None,
                    "target": "",
                    "mission_id": None,
                    "payload": {"malformed": True, "chaos_index": i},
                    "reason": "",
                }
            )
            injected += 1

        return {"injected": injected}
