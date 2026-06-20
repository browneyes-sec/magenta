"""Science Paper Publisher — generates LaTeX and Markdown papers from mission results.

Zero new dependencies. Uses only stdlib + existing deps:
  - json, datetime, uuid (stdlib)
  - pydantic (already in pyproject.toml)

Templates are inline (not Jinja2) to avoid adding jinja2 as a dependency.
If jinja2 is installed, template rendering can be enhanced later.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class PaperConfig:
    """Configuration for paper generation."""
    template: str = "incident-report"
    title: str = ""
    authors: list[str] = field(default_factory=lambda: ["Magenta ASOAR", "SOC Team"])
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    format: str = "markdown"  # latex | markdown | both


@dataclass
class PaperResult:
    """Result of paper generation."""
    paper_id: str
    title: str
    markdown: str = ""
    latex: str = ""
    targets: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


class PaperPublisher:
    """Generates publication-ready papers from completed missions."""

    TEMPLATES = {
        "incident-report": {
            "description": "Incident analysis and response report",
            "sections": ["Executive Summary", "Timeline", "Root Cause Analysis",
                         "IOCs", "Containment Actions", "Lessons Learned", "Recommendations"],
        },
        "threat-analysis": {
            "description": "Threat intelligence analysis paper",
            "sections": ["Abstract", "Threat Overview", "Attack Vectors",
                         "Indicators of Compromise", "MITRE Mapping", "Defensive Recommendations"],
        },
        "post-mortem": {
            "description": "Post-incident review document",
            "sections": ["Incident Summary", "Timeline of Events", "Root Cause",
                         "Impact Assessment", "Response Actions", "Action Items", "Appendix"],
        },
        "detection-engineering": {
            "description": "Detection rule engineering paper",
            "sections": ["Detection Goal", "Logic", "False Positives",
                         "Tuning Recommendations", "Deployment Notes"],
        },
    }

    def get_available_templates(self) -> list[dict]:
        return [
            {"name": name, "description": t["description"], "sections": t["sections"]}
            for name, t in self.TEMPLATES.items()
        ]

    async def publish_from_mission(
        self,
        mission_data: dict,
        artifacts: dict,
        config: PaperConfig,
    ) -> PaperResult:
        """Generate paper from completed mission data.

        Args:
            mission_data: Mission details (id, alert, timeline, findings).
            artifacts: Mission artifacts (audit_entry, reports, iocs).
            config: Paper configuration.

        Returns:
            PaperResult with markdown and/or latex content.
        """
        context = self._build_context(mission_data, artifacts, config)

        paper_id = f"paper-{uuid4().hex[:8]}"
        title = config.title or context.get("title", "Security Incident Analysis")

        markdown = self._render_markdown(title, context, config)
        latex = ""
        if config.format in ("latex", "both"):
            latex = self._render_latex(title, context, config)

        return PaperResult(
            paper_id=paper_id,
            title=title,
            markdown=markdown,
            latex=latex,
            metadata={
                "template": config.template,
                "mission_id": mission_data.get("mission_id", ""),
                "generated_at": datetime.utcnow().isoformat(),
                "authors": config.authors,
                "keywords": config.keywords or context.get("keywords", []),
            },
        )

    def _build_context(
        self, mission_data: dict, artifacts: dict, config: PaperConfig
    ) -> dict:
        alert = mission_data.get("alert", {})
        timeline = artifacts.get("timeline", {})
        iocs = artifacts.get("iocs", {})
        root_cause = artifacts.get("root_cause", {})
        scope = artifacts.get("scope", {})
        compliance = artifacts.get("compliance", {})
        mitre = artifacts.get("mitre", {})

        mission_id = mission_data.get('mission_id', 'unknown')
        title = config.title or (
            f"Security Incident Analysis: {alert.get('id', mission_id)}"
        )

        keywords = config.keywords or []
        if not keywords:
            keywords = self._extract_keywords(alert, iocs, mitre)

        return {
            "title": title,
            "mission_id": mission_data.get("mission_id", ""),
            "alert": alert,
            "timeline": timeline,
            "iocs": iocs,
            "root_cause": root_cause,
            "scope": scope,
            "compliance": compliance,
            "mitre": mitre,
            "artifacts": artifacts,
            "keywords": keywords,
            "authors": config.authors,
            "generated_at": datetime.utcnow().isoformat(),
        }

    def _extract_keywords(
        self, alert: dict, iocs: dict, mitre: dict
    ) -> list[str]:
        keywords = ["security-incident", "asoar", "magenta"]
        source = alert.get("source", "")
        if source:
            keywords.append(source)
        techniques = mitre.get("techniques", []) if isinstance(mitre, dict) else []
        for t in techniques[:3]:
            if isinstance(t, dict) and t.get("id"):
                keywords.append(t["id"])
        return keywords

    # ── Markdown renderer ───────────────────────────────────────────────

    def _render_markdown(self, title: str, ctx: dict, config: PaperConfig) -> str:
        sections = []

        sections.append(f"# {title}\n")
        sections.append(self._md_metadata_block(ctx))
        sections.append(self._md_executive_summary(ctx))
        sections.append(self._md_timeline(ctx))
        sections.append(self._md_root_cause(ctx))
        sections.append(self._md_iocs(ctx))
        sections.append(self._md_mitre_mapping(ctx))
        sections.append(self._md_scope(ctx))
        sections.append(self._md_containment(ctx))
        sections.append(self._md_compliance(ctx))
        sections.append(self._md_lessons_learned(ctx))
        sections.append(self._md_references(ctx))

        return "\n\n".join(s for s in sections if s)

    def _md_metadata_block(self, ctx: dict) -> str:
        authors = ", ".join(ctx.get("authors", []))
        keywords = ", ".join(ctx.get("keywords", []))
        return (
            f"**Authors:** {authors}\n\n"
            f"**Date:** {ctx.get('generated_at', '')}\n\n"
            f"**Keywords:** {keywords}\n\n"
            f"**Mission ID:** `{ctx.get('mission_id', '')}`"
        )

    def _md_executive_summary(self, ctx: dict) -> str:
        alert = ctx.get("alert", {})
        root_cause = ctx.get("root_cause", {})
        scope = ctx.get("scope", {})

        summary = "## Executive Summary\n\n"
        summary += (
            f"This report documents a security incident "
            f"(Alert ID: {alert.get('id', 'N/A')}) "
            f"detected by {alert.get('source', 'N/A')}. "
        )
        if isinstance(root_cause, dict) and root_cause.get("root_cause"):
            summary += f"The root cause was identified as: {root_cause['root_cause']}. "
        if isinstance(scope, dict):
            blast = scope.get("blast_radius", "unknown")
            summary += f"The blast radius was assessed as {blast}. "
        return summary

    def _md_timeline(self, ctx: dict) -> str:
        timeline = ctx.get("timeline", {})
        if not timeline or not isinstance(timeline, dict):
            return "## Timeline\n\nNo timeline data available."

        events = timeline.get("timeline", [])
        if not events:
            return "## Timeline\n\nNo timeline events recorded."

        md = "## Timeline\n\n"
        md += "| Timestamp | Event | Source | Significance |\n"
        md += "|-----------|-------|--------|-------------|\n"
        for ev in events:
            if isinstance(ev, dict):
                ts = ev.get("timestamp", "")
                event = ev.get("event", "")
                source = ev.get("source", "")
                sig = ev.get("significance", "")
                md += f"| {ts} | {event} | {source} | {sig} |\n"
        return md

    def _md_root_cause(self, ctx: dict) -> str:
        rc = ctx.get("root_cause", {})
        if not rc or not isinstance(rc, dict):
            return "## Root Cause Analysis\n\nNo root cause analysis available."

        md = "## Root Cause Analysis\n\n"
        if rc.get("root_cause"):
            md += f"**Root Cause:** {rc['root_cause']}\n\n"
        if rc.get("initial_access"):
            md += f"**Initial Access:** {rc['initial_access']}\n\n"
        if rc.get("attack_path"):
            md += "**Attack Path:**\n\n"
            for i, step in enumerate(rc["attack_path"], 1):
                md += f"{i}. {step}\n"
        return md

    def _md_iocs(self, ctx: dict) -> str:
        iocs = ctx.get("iocs", {})
        if not iocs or not isinstance(iocs, dict):
            return "## Indicators of Compromise\n\nNo IOCs identified."

        ioc_list = iocs.get("iocs", [])
        if not ioc_list:
            return "## Indicators of Compromise\n\nNo IOCs identified."

        md = "## Indicators of Compromise\n\n"
        md += "| Type | Value | Confidence |\n"
        md += "|------|-------|------------|\n"
        for ioc in ioc_list:
            if isinstance(ioc, dict):
                ioc_type = ioc.get("type", "")
                value = ioc.get("value", "")
                conf = ioc.get("confidence", "")
                md += f"| {ioc_type} | `{value}` | {conf} |\n"
        return md

    def _md_mitre_mapping(self, ctx: dict) -> str:
        mitre = ctx.get("mitre", {})
        if not mitre or not isinstance(mitre, dict):
            return "## MITRE ATT&CK Mapping\n\nNo MITRE techniques identified."

        techniques = mitre.get("techniques", [])
        if not techniques:
            return "## MITRE ATT&CK Mapping\n\nNo MITRE techniques identified."

        md = "## MITRE ATT&CK Mapping\n\n"
        md += "| Technique ID | Name | Tactic | Confidence |\n"
        md += "|-------------|------|--------|------------|\n"
        for t in techniques:
            if isinstance(t, dict):
                tid = t.get("id", "")
                name = t.get("name", "")
                tactic = t.get("tactic", "")
                conf = t.get("confidence", "")
                md += f"| {tid} | {name} | {tactic} | {conf} |\n"
        return md

    def _md_scope(self, ctx: dict) -> str:
        scope = ctx.get("scope", {})
        if not scope or not isinstance(scope, dict):
            return "## Scope Assessment\n\nNo scope data available."

        md = "## Scope Assessment\n\n"
        if scope.get("blast_radius"):
            md += f"**Blast Radius:** {scope['blast_radius']}\n\n"
        if scope.get("data_exfiltration_risk"):
            md += f"**Data Exfiltration Risk:** {scope['data_exfiltration_risk']}\n\n"
        affected = scope.get("affected_hosts", [])
        if affected:
            md += "**Affected Hosts:**\n\n"
            for h in affected:
                md += f"- `{h}`\n"
        users = scope.get("affected_users", [])
        if users:
            md += "\n**Affected Users:**\n\n"
            for u in users:
                md += f"- `{u}`\n"
        return md

    def _md_containment(self, ctx: dict) -> str:
        return (
            "## Containment Actions\n\n"
            "See workflow execution logs for detailed containment actions."
        )

    def _md_compliance(self, ctx: dict) -> str:
        compliance = ctx.get("compliance", {})
        if not compliance or not isinstance(compliance, dict):
            return "## Compliance\n\nNo compliance data available."

        md = "## Compliance\n\n"
        frameworks = compliance.get("frameworks", {})
        for fw_name, fw_data in frameworks.items():
            if isinstance(fw_data, dict):
                applicable = fw_data.get("applicable", False)
                findings = fw_data.get("findings", [])
                status = "Applicable" if applicable else "Not Applicable"
                md += f"### {fw_name} — {status}\n\n"
                if findings:
                    for f in findings:
                        md += f"- {f}\n"
                md += "\n"
        return md

    def _md_lessons_learned(self, ctx: dict) -> str:
        return (
            "## Lessons Learned\n\n"
            "1. Detection time should be reduced through enhanced alerting rules.\n"
            "2. Automated containment should be enabled for high-confidence IOCs.\n"
            "3. Regular phishing simulation exercises recommended."
        )

    def _md_references(self, ctx: str) -> str:
        return (
            "## References\n\n"
            "- MITRE ATT&CK Framework: https://attack.mitre.org/\n"
            "- Magenta ASOAR Documentation: https://magenta-asoar.dev\n"
            "- NIST Cybersecurity Framework: https://www.nist.gov/cyberframework"
        )

    # ── LaTeX renderer ──────────────────────────────────────────────────

    def _render_latex(self, title: str, ctx: dict, config: PaperConfig) -> str:
        authors = " \\and ".join(ctx.get("authors", ["Magenta ASOAR"]))
        keywords = ", ".join(ctx.get("keywords", []))

        sections = []
        sections.append(self._latex_preamble(title, authors, keywords))
        summary = self._latex_executive_summary(ctx)
        sections.append(self._latex_section("Executive Summary", summary))
        sections.append(self._latex_section("Timeline", self._latex_timeline(ctx)))
        sections.append(self._latex_section("Root Cause Analysis", self._latex_root_cause(ctx)))
        sections.append(self._latex_section("Indicators of Compromise", self._latex_iocs(ctx)))
        sections.append(self._latex_section("MITRE ATT\\&CK Mapping", self._latex_mitre(ctx)))
        sections.append(self._latex_section("Scope Assessment", self._latex_scope(ctx)))
        sections.append(self._latex_section("Lessons Learned", self._latex_lessons(ctx)))
        sections.append("\\end{document}")

        return "\n\n".join(s for s in sections if s)

    def _latex_preamble(self, title: str, authors: str, keywords: str) -> str:
        return (
            "\\documentclass[11pt,a4paper]{article}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage[T1]{fontenc}\n"
            "\\usepackage{hyperref}\n"
            "\\usepackage{booktabs}\n"
            "\\usepackage{longtable}\n"
            "\\usepackage{geometry}\n"
            "\\geometry{margin=1in}\n"
            f"\\title{{{title}}}\n"
            f"\\author{{{authors}}}\n"
            f"\\date{{{datetime.utcnow().strftime('%B %d, %Y')}}}\n"
            "\\begin{document}\n"
            "\\maketitle\n"
            f"\\begin{{abstract}}\n"
            f"This report documents a security incident analyzed by the Magenta ASOAR framework. "
            f"Keywords: {keywords}.\n"
            f"\\end{{abstract}}\n"
            "\\tableofcontents\n"
            "\\newpage"
        )

    def _latex_section(self, title: str, content: str) -> str:
        return f"\\section{{{title}}}\n\n{content}"

    def _latex_executive_summary(self, ctx: dict) -> str:
        alert = ctx.get("alert", {})
        root_cause = ctx.get("root_cause", {})
        scope = ctx.get("scope", {})

        text = (
            f"This report analyzes security incident "
            f"\\texttt{{{alert.get('id', 'N/A')}}} detected by {alert.get('source', 'N/A')}. "
        )
        if isinstance(root_cause, dict) and root_cause.get("root_cause"):
            text += f"The root cause was: {root_cause['root_cause']}. "
        if isinstance(scope, dict):
            text += f"The blast radius was assessed as {scope.get('blast_radius', 'unknown')}. "
        return text

    def _latex_timeline(self, ctx: dict) -> str:
        timeline = ctx.get("timeline", {})
        events = timeline.get("timeline", []) if isinstance(timeline, dict) else []
        if not events:
            return "No timeline data available."

        tex = "\\begin{longtable}{llll}\n"
        tex += "\\toprule\n"
        tex += "Timestamp & Event & Source & Significance \\\\\n"
        tex += "\\midrule\n"
        for ev in events:
            if isinstance(ev, dict):
                ts = ev.get("timestamp", "").replace("&", "\\&")
                event = ev.get("event", "").replace("&", "\\&")
                source = ev.get("source", "").replace("&", "\\&")
                sig = ev.get("significance", "").replace("&", "\\&")
                tex += f"{ts} & {event} & {source} & {sig} \\\\\n"
        tex += "\\bottomrule\n"
        tex += "\\end{longtable}"
        return tex

    def _latex_root_cause(self, ctx: dict) -> str:
        rc = ctx.get("root_cause", {})
        if not rc or not isinstance(rc, dict):
            return "No root cause analysis available."

        text = ""
        if rc.get("root_cause"):
            text += f"\\textbf{{Root Cause:}} {rc['root_cause']}\n\n"
        if rc.get("initial_access"):
            text += f"\\textbf{{Initial Access:}} {rc['initial_access']}\n\n"
        if rc.get("attack_path"):
            text += "\\textbf{Attack Path:}\n\\begin{enumerate}\n"
            for step in rc["attack_path"]:
                text += f"\\item {step}\n"
            text += "\\end{enumerate}\n"
        return text

    def _latex_iocs(self, ctx: dict) -> str:
        iocs = ctx.get("iocs", {})
        ioc_list = iocs.get("iocs", []) if isinstance(iocs, dict) else []
        if not ioc_list:
            return "No IOCs identified."

        tex = "\\begin{longtable}{lll}\n"
        tex += "\\toprule\n"
        tex += "Type & Value & Confidence \\\\\n"
        tex += "\\midrule\n"
        for ioc in ioc_list:
            if isinstance(ioc, dict):
                ioc_type = ioc.get("type", "")
                value = ioc.get("value", "").replace("_", "\\_")
                conf = ioc.get("confidence", "")
                tex += f"{ioc_type} & \\texttt{{{value}}} & {conf} \\\\\n"
        tex += "\\bottomrule\n"
        tex += "\\end{longtable}"
        return tex

    def _latex_mitre(self, ctx: dict) -> str:
        mitre = ctx.get("mitre", {})
        techniques = mitre.get("techniques", []) if isinstance(mitre, dict) else []
        if not techniques:
            return "No MITRE techniques identified."

        tex = "\\begin{longtable}{llll}\n"
        tex += "\\toprule\n"
        tex += "Technique ID & Name & Tactic & Confidence \\\\\n"
        tex += "\\midrule\n"
        for t in techniques:
            if isinstance(t, dict):
                tid = t.get("id", "")
                name = t.get("name", "")
                tactic = t.get("tactic", "")
                conf = t.get("confidence", "")
                tex += f"{tid} & {name} & {tactic} & {conf} \\\\\n"
        tex += "\\bottomrule\n"
        tex += "\\end{longtable}"
        return tex

    def _latex_scope(self, ctx: dict) -> str:
        scope = ctx.get("scope", {})
        if not scope or not isinstance(scope, dict):
            return "No scope data available."

        text = ""
        if scope.get("blast_radius"):
            text += f"\\textbf{{Blast Radius:}} {scope['blast_radius']}\n\n"
        if scope.get("data_exfiltration_risk"):
            text += f"\\textbf{{Data Exfiltration Risk:}} {scope['data_exfiltration_risk']}\n\n"
        hosts = scope.get("affected_hosts", [])
        if hosts:
            text += "\\textbf{Affected Hosts:}\n\\begin{itemize}\n"
            for h in hosts:
                text += f"\\item \\texttt{{{h}}}\n"
            text += "\\end{itemize}\n"
        return text

    def _latex_lessons(self, ctx: dict) -> str:
        return (
            "\\begin{enumerate}\n"
            "\\item Detection time should be reduced through enhanced alerting rules.\n"
            "\\item Automated containment should be enabled for high-confidence IOCs.\n"
            "\\item Regular phishing simulation exercises recommended.\n"
            "\\end{enumerate}"
        )
