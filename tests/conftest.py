"""Shared test fixtures for memory tests (ADR-018)."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_memory_mcp():
    """Mock MemoryMCPServer for testing."""
    mock = MagicMock()
    mock.write_episode = AsyncMock(
        return_value={
            "status": "success",
            "memory_type": "episodic",
            "chunks_ingested": 1,
            "errors": [],
        }
    )
    mock.search_episodes = AsyncMock(
        return_value={
            "status": "success",
            "memory_type": "episodic",
            "results": [],
            "count": 0,
        }
    )
    mock.write_semantic = AsyncMock(
        return_value={
            "status": "success",
            "memory_type": "semantic",
            "chunks_ingested": 1,
            "errors": [],
        }
    )
    mock.search_semantic = AsyncMock(
        return_value={
            "status": "success",
            "memory_type": "semantic",
            "results": [],
            "count": 0,
        }
    )
    mock.write_procedure = AsyncMock(
        return_value={
            "status": "success",
            "memory_type": "procedural",
            "chunks_ingested": 1,
            "errors": [],
        }
    )
    mock.search_procedures = AsyncMock(
        return_value={
            "status": "success",
            "memory_type": "procedural",
            "results": [],
            "count": 0,
        }
    )
    return mock


@pytest.fixture
def mock_mission():
    """Mock mission for testing."""
    mission = MagicMock()
    mission.mission_id = "test-mission-001"
    mission.source_system.value = "sentinel"
    mission.alert_id = "sentinel-alert-001"
    mission.playbook_id = "phishing-v1"
    mission.correlation_id = "corr-001"
    return mission


@pytest.fixture
def mock_agent_config():
    """Mock agent config for testing."""
    return MagicMock(
        agent_id="triage-test-001",
        role="triage",
        model_provider="ollama",
        model_name="qwen2.5:0.5b",
        instructions="Triage incoming alerts",
        tools=["sentinel_query", "registry_write"],
    )
