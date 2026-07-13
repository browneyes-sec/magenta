"""Dictator telemetry — OTel spans + Elasticsearch emit for directives.

Best-effort only: failures are logged, never raised.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def emit_directive_span(directive: dict) -> None:
    """Emit an OpenTelemetry span for a directive (best-effort)."""
    try:
        from opentelemetry import trace
        from opentelemetry.trace import Status, StatusCode

        tracer = trace.get_tracer("magenta.dictator")
        with tracer.start_as_current_span(
            f"directive.{directive.get('type', 'unknown')}",
            attributes={
                "directive.id": directive.get("directive_id", ""),
                "directive.type": directive.get("type", ""),
                "directive.priority": directive.get("priority", "normal"),
                "directive.target": directive.get("target", ""),
                "directive.mission_id": directive.get("mission_id", "") or "",
                "directive.reason": directive.get("reason", "")[:256],
            },
        ) as span:
            span.set_status(Status(StatusCode.OK))
    except ImportError:
        logger.debug("opentelemetry not available, skipping span")
    except Exception as exc:
        logger.warning("Failed to emit OTel span for directive: %s", exc)


async def write_directive_to_elastic(directive: dict) -> None:
    """Write directive record to Elasticsearch (best-effort).

    Uses the existing ElasticClient from magenta.data.elastic.
    Failures are logged, never raised.
    """
    try:
        from magenta.data.elastic.client import elastic_client

        doc = {
            **directive,
            "logged_at": datetime.utcnow().isoformat(),
            "doc_type": "directive",
        }
        await elastic_client.index("directives", doc, id=directive.get("directive_id"))
    except ImportError:
        logger.debug("elasticsearch client not available, skipping index")
    except Exception as exc:
        logger.warning("Failed to index directive to Elasticsearch: %s", exc)


def generate_directive_timeline_artifact(directives: list[dict]) -> str:
    """Generate an HTML artifact showing the directive timeline.

    Returns an HTML string suitable for rendering in Open WebUI.
    """
    rows = []
    for d in directives[-20:]:
        icon = _icon_for_type(d.get("type", ""))
        rows.append(f"""<tr>
            <td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:13px">{icon}</td>
            <td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:13px">{d.get("type", "")}</td>
            <td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:13px">{d.get("target", "")}</td>
            <td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:13px">{d.get("reason", "")[:48]}</td>
            <td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:13px">{d.get("priority", "normal")}</td>
            <td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:13px">{_time_ago(d.get("issued_at", ""))}</td>
        </tr>""")

    return f"""<div style="font-family:system-ui,-apple-system,sans-serif;max-width:100%">
    <h3 style="margin:0 0 8px 0;font-size:16px">Directive Timeline</h3>
    <table style="width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
        <thead><tr style="background:#f5f5f5">
            <th style="padding:8px;text-align:left;font-size:12px;text-transform:uppercase;color:#666">#</th>
            <th style="padding:8px;text-align:left;font-size:12px;text-transform:uppercase;color:#666">Type</th>
            <th style="padding:8px;text-align:left;font-size:12px;text-transform:uppercase;color:#666">Target</th>
            <th style="padding:8px;text-align:left;font-size:12px;text-transform:uppercase;color:#666">Reason</th>
            <th style="padding:8px;text-align:left;font-size:12px;text-transform:uppercase;color:#666">Priority</th>
            <th style="padding:8px;text-align:left;font-size:12px;text-transform:uppercase;color:#666">Time</th>
        </tr></thead>
        <tbody>{"".join(rows) if rows else '<tr><td colspan="6" style="padding:16px;text-align:center;color:#999;font-size:13px">No directives issued yet</td></tr>'}</tbody>
    </table></div>"""


def _icon_for_type(dtype: str) -> str:
    icons = {
        "deploy_agent": "",
        "recall_agent": "",
        "halt_mission": "",
        "resume_mission": "",
        "escalate": "",
        "override_teaming": "",
        "policy_override": "",
        "system_command": "",
        "promote_probe": "",
        "inject_probe": "",
        "reassign_task": "",
    }
    return icons.get(dtype, "")


def _time_ago(ts_str: str) -> str:
    try:
        from dateutil.parser import isoparse

        dt = isoparse(ts_str)
        delta = datetime.utcnow() - dt.replace(tzinfo=None)
        if delta.total_seconds() < 60:
            return "just now"
        if delta.total_seconds() < 3600:
            return f"{int(delta.total_seconds() // 60)}m ago"
        if delta.total_seconds() < 86400:
            return f"{int(delta.total_seconds() // 3600)}h ago"
        return f"{int(delta.total_seconds() // 86400)}d ago"
    except Exception:
        return ts_str[:16] if ts_str else ""
