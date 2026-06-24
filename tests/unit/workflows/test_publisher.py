"""Tests for PaperPublisher — LaTeX and Markdown report generation."""

from __future__ import annotations

import asyncio

import pytest

from magenta.workflows.publisher.paper_publisher import PaperConfig, PaperPublisher, PaperResult


@pytest.fixture
def publisher():
    return PaperPublisher()


@pytest.fixture
def sample_mission():
    return {
        "mission_id": "mission-test-001",
        "alert": {
            "id": "alert-123",
            "source": "Microsoft Sentinel",
            "severity": "high",
        },
    }


@pytest.fixture
def sample_artifacts():
    return {
        "timeline": {
            "timeline": [
                {
                    "timestamp": "2025-01-01T10:00:00Z",
                    "event": "Alert triggered",
                    "source": "Sentinel",
                    "significance": "Initial detection",
                },
                {
                    "timestamp": "2025-01-01T10:05:00Z",
                    "event": "IOCs enriched",
                    "source": "Magenta AI",
                    "significance": "Threat context added",
                },
            ]
        },
        "iocs": {
            "iocs": [
                {"type": "ip", "value": "192.168.1.100", "confidence": 0.85},
                {"type": "domain", "value": "evil.example.com", "confidence": 0.9},
            ]
        },
        "root_cause": {
            "root_cause": "Phishing email with malicious attachment",
            "initial_access": "User opened malicious PDF",
            "attack_path": [
                "Phishing email received",
                "User opened attachment",
                "Macro executed",
                "C2 beacon established",
            ],
        },
        "scope": {
            "blast_radius": "medium",
            "data_exfiltration_risk": "low",
            "affected_hosts": [" workstation-01", "workstation-02"],
            "affected_users": ["jsmith@corp.local"],
        },
        "mitre": {
            "techniques": [
                {
                    "id": "T1566.001",
                    "name": "Spearphishing Attachment",
                    "tactic": "initial-access",
                    "confidence": 0.9,
                },
                {
                    "id": "T1059.001",
                    "name": "PowerShell",
                    "tactic": "execution",
                    "confidence": 0.8,
                },
            ]
        },
        "compliance": {
            "frameworks": {
                "NIST CSF": {
                    "applicable": True,
                    "findings": ["Detection delay exceeded 1-hour SLA"],
                }
            }
        },
    }


class TestPaperPublisher:
    def test_get_available_templates(self, publisher):
        templates = publisher.get_available_templates()
        assert len(templates) >= 4
        names = [t["name"] for t in templates]
        assert "incident-report" in names
        assert "threat-analysis" in names

    def test_publish_markdown(self, publisher, sample_mission, sample_artifacts):
        config = PaperConfig(template="incident-report", format="markdown")
        result = asyncio.run(
            publisher.publish_from_mission(sample_mission, sample_artifacts, config)
        )
        assert isinstance(result, PaperResult)
        assert result.paper_id.startswith("paper-")
        assert len(result.markdown) > 0
        assert "# Security Incident Analysis" in result.markdown
        assert "## Timeline" in result.markdown
        assert "## Indicators of Compromise" in result.markdown

    def test_publish_latex(self, publisher, sample_mission, sample_artifacts):
        config = PaperConfig(template="incident-report", format="latex")
        result = asyncio.run(
            publisher.publish_from_mission(sample_mission, sample_artifacts, config)
        )
        assert len(result.latex) > 0
        assert "\\documentclass" in result.latex
        assert "\\begin{document}" in result.latex
        assert "\\end{document}" in result.latex

    def test_publish_both(self, publisher, sample_mission, sample_artifacts):
        config = PaperConfig(format="both")
        result = asyncio.run(
            publisher.publish_from_mission(sample_mission, sample_artifacts, config)
        )
        assert len(result.markdown) > 0
        assert len(result.latex) > 0

    def test_metadata_populated(self, publisher, sample_mission, sample_artifacts):
        config = PaperConfig(keywords=["phishing", "test"])
        result = asyncio.run(
            publisher.publish_from_mission(sample_mission, sample_artifacts, config)
        )
        assert result.metadata["template"] == "incident-report"
        assert result.metadata["mission_id"] == "mission-test-001"
        assert "phishing" in result.metadata["keywords"]

    def test_custom_title(self, publisher, sample_mission, sample_artifacts):
        config = PaperConfig(title="Custom Report Title")
        result = asyncio.run(
            publisher.publish_from_mission(sample_mission, sample_artifacts, config)
        )
        assert result.title == "Custom Report Title"
        assert "Custom Report Title" in result.markdown

    def test_empty_artifacts(self, publisher, sample_mission):
        config = PaperConfig()
        result = asyncio.run(publisher.publish_from_mission(sample_mission, {}, config))
        assert len(result.markdown) > 0
        assert "No timeline data" in result.markdown

    def test_mitre_section(self, publisher, sample_mission, sample_artifacts):
        config = PaperConfig(format="markdown")
        result = asyncio.run(
            publisher.publish_from_mission(sample_mission, sample_artifacts, config)
        )
        assert "T1566.001" in result.markdown
        assert "Spearphishing Attachment" in result.markdown

    def test_scope_section(self, publisher, sample_mission, sample_artifacts):
        config = PaperConfig(format="markdown")
        result = asyncio.run(
            publisher.publish_from_mission(sample_mission, sample_artifacts, config)
        )
        assert "Blast Radius" in result.markdown
        assert "medium" in result.markdown

    def test_compliance_section(self, publisher, sample_mission, sample_artifacts):
        config = PaperConfig(format="markdown")
        result = asyncio.run(
            publisher.publish_from_mission(sample_mission, sample_artifacts, config)
        )
        assert "NIST CSF" in result.markdown
