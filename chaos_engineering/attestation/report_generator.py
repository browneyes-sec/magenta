"""Report generator — produces condensed certification reports in Markdown and JSON."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates chaos engineering certification reports."""

    def __init__(self, config: dict):
        self._config = config
        cert_config = config.get("certification", {})
        self._output_dir = Path(cert_config.get("output_dir", "docs/certifications"))
        self._prefix = cert_config.get("prefix", "magenta_chaos")
        self._format = cert_config.get("format", "markdown")

    def generate(self, result: Any, run_id: str) -> str:
        """Generate and deposit certification report. Returns file path."""
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Extract date from run_id (chaos-DD_MM_YY-NNN)
        parts = run_id.split("-")
        date_str = "-".join(parts[1:4]) if len(parts) >= 4 else datetime.utcnow().strftime("%d_%m_%y")

        filename = f"{self._prefix}-{date_str}"
        filepath = self._output_dir / f"{filename}.md"

        content = self._render_markdown(result)
        filepath.write_text(content)

        # Also deposit JSON if configured
        json_path = self._output_dir / f"{filename}.json"
        json_path.write_text(json.dumps(self._to_dict(result), indent=2, default=str))

        logger.info("Certification deposited: %s", filepath)
        return str(filepath)

    def _render_markdown(self, result: Any) -> str:
        """Render condensed Markdown certification report."""
        lines = []
        lines.append("# Magenta Chaos Engineering Certification\n")
        lines.append(f"**Run ID:** {result.run_id}")
        lines.append(f"**Date:** {result.started_at.strftime('%Y-%m-%d') if result.started_at else 'N/A'}")
        lines.append(f"**Duration:** {result.duration_seconds:.0f}s")
        lines.append(f"**Intensity:** {result.intensity} (stealth: {'on' if result.stealth else 'off'})")
        lines.append("")

        # Executive Summary
        lines.append("---\n")
        lines.append("## Executive Summary\n")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        lines.append(f"| Scenarios Run | {result.scenarios_run} |")
        lines.append(f"| Scenarios Passed | {result.scenarios_passed} |")
        lines.append(f"| Scenarios Failed | {result.scenarios_failed} |")
        lines.append(f"| Scenarios Skipped | {result.scenarios_skipped} |")

        pre_passed = sum(1 for p in result.baseline_probes if p.get("healthy"))
        post_passed = sum(1 for p in result.post_probes if p.get("healthy"))
        lines.append(f"| Probes (Pre) | {pre_passed}/{len(result.baseline_probes)} passed |")
        lines.append(f"| Probes (Post) | {post_passed}/{len(result.post_probes)} passed |")

        if result.regression:
            lines.append(f"| Regression | {result.regression.get('passed', 0)}/{result.regression.get('total', 0)} passed |")

        verdict_icon = {"pass": "✅", "fail": "❌", "skip": "⏭️", "dry_run": "🔍"}.get(result.verdict, "❓")
        lines.append(f"| Overall Verdict | {verdict_icon} **{result.verdict.upper()}** |")
        lines.append("")

        # Scenario Results
        lines.append("---\n")
        lines.append("## Scenario Results\n")

        for r in result.results:
            status_icon = {"passed": "✅", "failed": "❌", "skipped": "⏭️", "error": "⚠️"}.get(r.status, "❓")
            lines.append(f"### {r.scenario} ({status_icon} {r.status.upper()})\n")

            if r.reason:
                lines.append(f"**Reason:** {r.reason}\n")

            if r.injection_details:
                lines.append("| Detail | Value |")
                lines.append("|---|---|")
                for k, v in r.injection_details.items():
                    lines.append(f"| {k} | {v} |")
                lines.append("")

            if r.recovery_time_seconds > 0:
                lines.append(f"**Recovery Time:** {r.recovery_time_seconds:.1f}s\n")

            if r.recommendations:
                st = r.recommendations.get("short_term", [])
                lt = r.recommendations.get("long_term", [])
                if st:
                    lines.append("**Short-term Recommendations:**")
                    for rec in st:
                        lines.append(f"- {rec}")
                    lines.append("")
                if lt:
                    lines.append("**Long-term Recommendations:**")
                    for rec in lt:
                        lines.append(f"- {rec}")
                    lines.append("")

        # Probe Snapshot
        lines.append("---\n")
        lines.append("## Probe Snapshot\n")
        lines.append("| Probe | Pre-Chaos | Post-Chaos | Delta |")
        lines.append("|---|---|---|---|")
        pre_map = {p["probe"]: p.get("healthy", False) for p in result.baseline_probes}
        post_map = {p["probe"]: p.get("healthy", False) for p in result.post_probes}
        all_probes = set(list(pre_map.keys()) + list(post_map.keys()))
        for probe_name in sorted(all_probes):
            pre = "✅ healthy" if pre_map.get(probe_name) else "❌ unhealthy"
            post = "✅ healthy" if post_map.get(probe_name) else "❌ unhealthy"
            delta = "—" if pre_map.get(probe_name) == post_map.get(probe_name) else "⚠️ changed"
            lines.append(f"| {probe_name} | {pre} | {post} | {delta} |")
        lines.append("")

        # Regression Summary
        if result.regression and result.regression.get("status") != "skipped":
            lines.append("---\n")
            lines.append("## Regression Summary\n")
            lines.append(f"| Mode | Total | Passed | Failed |")
            lines.append(f"|---|---|---|---|")
            lines.append(f"| {result.regression.get('mode', 'unknown')} | "
                         f"{result.regression.get('total', 0)} | "
                         f"{result.regression.get('passed', 0)} | "
                         f"{result.regression.get('failed', 0)} |")
            lines.append("")

        # Aggregate Recommendations
        lines.append("---\n")
        lines.append("## Recommendations\n")
        all_short = []
        all_long = []
        for r in result.results:
            all_short.extend(r.recommendations.get("short_term", []))
            all_long.extend(r.recommendations.get("long_term", []))

        if all_short:
            lines.append("### Short-Term (Next Sprint)")
            for rec in all_short:
                lines.append(f"1. {rec}")
            lines.append("")

        if all_long:
            lines.append("### Long-Term (Next Quarter)")
            for rec in all_long:
                lines.append(f"1. {rec}")
            lines.append("")

        # Footer
        lines.append("---\n")
        lines.append(f"*Certification generated by Magenta Chaos Engineering Suite v0.1.0*")
        lines.append(f"*DTP-03 §5.3 Compliance: Chaos test plan executed*")

        return "\n".join(lines)

    def _to_dict(self, result: Any) -> dict:
        """Convert result to JSON-serializable dict."""
        return {
            "run_id": result.run_id,
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "duration_seconds": result.duration_seconds,
            "intensity": result.intensity,
            "stealth": result.stealth,
            "verdict": result.verdict,
            "scenarios_run": result.scenarios_run,
            "scenarios_passed": result.scenarios_passed,
            "scenarios_failed": result.scenarios_failed,
            "scenarios_skipped": result.scenarios_skipped,
            "baseline_probes": result.baseline_probes,
            "post_probes": result.post_probes,
            "regression": result.regression,
            "results": [
                {
                    "scenario": r.scenario,
                    "status": r.status,
                    "reason": r.reason,
                    "injection_details": r.injection_details,
                    "recovery_time_seconds": r.recovery_time_seconds,
                    "recommendations": r.recommendations,
                }
                for r in result.results
            ],
        }
