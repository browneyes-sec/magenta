"""Tests for CACAO v2 ↔ Magenta PlaybookV2 translator."""
from __future__ import annotations

import pytest

from magenta.core.models import PlaybookV2
from magenta.workflows.cacao.translator import CACAOTranslator


@pytest.fixture
def translator():
    return CACAOTranslator()


@pytest.fixture
def sample_cacao_bundle():
    return {
        "type": "playbook",
        "spec_version": "CACAO-2.0",
        "id": "playbook--test-456",
        "name": "Phishing Response",
        "description": "Phishing incident playbook",
        "playbook_version": "1.0.0",
        "created": "2025-01-01T00:00:00Z",
        "modified": "2025-01-01T00:00:00Z",
        "created_by": "identity--test",
        "workflow": {
            "type": "parallel",
            "steps": {
                "step--1": {
                    "type": "step",
                    "name": "Ingest Alert",
                    "actions": [
                        {"type": "action", "run": "ingest", "inputs": {"source": "sentinel"}}
                    ],
                    "on_completion": "step--2",
                },
                "step--2": {
                    "type": "step",
                    "name": "Analyze",
                    "actions": [
                        {"type": "action", "run": "analyze", "inputs": {"agent": "triage"}}
                    ],
                },
            },
        },
        "trigger": {"type": "alert", "name": "Alert Trigger"},
    }


class TestCACAOTranslator:
    def test_cacao_to_magenta(self, translator, sample_cacao_bundle):
        playbook = translator.cacao_to_magenta(sample_cacao_bundle)
        assert isinstance(playbook, PlaybookV2)
        assert playbook.metadata["name"] == "Phishing Response"
        assert playbook.apiVersion == "magenta.soar/v1"
        workflow = playbook.spec.get("workflow", {})
        nodes = workflow.get("nodes", [])
        assert len(nodes) == 2

    def test_magenta_to_cacao(self, translator, sample_cacao_bundle):
        playbook = translator.cacao_to_magenta(sample_cacao_bundle)
        bundle = translator.magenta_to_cacao(playbook)
        assert bundle["type"] == "playbook"
        assert "workflow" in bundle
        assert "steps" in bundle["workflow"]

    def test_roundtrip_preserves_nodes(self, translator, sample_cacao_bundle):
        playbook1 = translator.cacao_to_magenta(sample_cacao_bundle)
        bundle = translator.magenta_to_cacao(playbook1)
        playbook2 = translator.cacao_to_magenta(bundle)
        nodes1 = playbook1.spec.get("workflow", {}).get("nodes", [])
        nodes2 = playbook2.spec.get("workflow", {}).get("nodes", [])
        assert len(nodes1) == len(nodes2)
        ids1 = {n["id"] for n in nodes1}
        ids2 = {n["id"] for n in nodes2}
        assert ids1 == ids2

    def test_node_types_preserved(self, translator, sample_cacao_bundle):
        playbook = translator.cacao_to_magenta(sample_cacao_bundle)
        nodes = playbook.spec.get("workflow", {}).get("nodes", [])
        types = {n.get("type") for n in nodes}
        assert "ingest" in types or "agentic" in types

    def test_triggers_translated(self, translator, sample_cacao_bundle):
        playbook = translator.cacao_to_magenta(sample_cacao_bundle)
        trigger = playbook.spec.get("trigger", {})
        assert trigger.get("type") == "alert" or "trigger" in playbook.spec

    def test_empty_cacao_bundle(self, translator):
        bundle = {
            "type": "playbook",
            "spec_version": "CACAO-2.0",
            "id": "playbook--empty",
            "name": "Empty",
            "workflow": {"type": "parallel", "steps": {}},
        }
        playbook = translator.cacao_to_magenta(bundle)
        nodes = playbook.spec.get("workflow", {}).get("nodes", [])
        assert len(nodes) == 0

    def test_no_workflow_steps(self, translator):
        bundle = {
            "type": "playbook",
            "spec_version": "CACAO-2.0",
            "id": "playbook--no-steps",
            "name": "No Steps",
            "workflow": {"type": "parallel"},
        }
        playbook = translator.cacao_to_magenta(bundle)
        nodes = playbook.spec.get("workflow", {}).get("nodes", [])
        assert len(nodes) == 0

    def test_metadata_translated(self, translator, sample_cacao_bundle):
        playbook = translator.cacao_to_magenta(sample_cacao_bundle)
        assert playbook.metadata["name"] == "Phishing Response"
        assert playbook.metadata["description"] == "Phishing incident playbook"
        assert playbook.metadata.get("cacao_id") == "playbook--test-456"
