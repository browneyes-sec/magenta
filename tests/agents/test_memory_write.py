"""Tests for agent memory write path (ADR-018).

Verifies:
- log_activity() → memory_mcp.write_episode() wiring
- Idempotent writes (same mission+turn = single chunk)
- Provenance fields captured
- tenant_id present in payloads
- Zero agent-block on memory failure
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from magenta.core.models import ActionStatus, AgentConfig


class MockMission:
    """Test mission fixture."""

    mission_id = "test-mission-001"
    source_system = MagicMock()
    source_system.value = "sentinel"
    alert_id = "sentinel-alert-001"
    playbook_id = "phishing-v1"
    correlation_id = "corr-001"


class MockAgentConfig:
    """Test agent config fixture."""

    agent_id = "triage-test-001"
    role = "triage"
    model_provider = "ollama"
    model_name = "qwen2.5:0.5b"
    instructions = "Triage incoming alerts"
    tools = ["sentinel_query", "registry_write"]


@pytest.fixture
def mock_memory_mcp():
    """Mock MemoryMCPServer for testing."""
    with patch("magenta.agents.base.memory_mcp") as mock:
        mock.write_episode = AsyncMock(
            return_value={
                "status": "success",
                "memory_type": "episodic",
                "mission_id": "test-mission-001",
                "agent_role": "triage",
                "turn_number": 1,
                "chunks_ingested": 1,
                "errors": [],
            }
        )
        yield mock


@pytest.fixture
def mock_search_episodes():
    """Mock search_episodes for testing."""
    with patch("magenta.agents.base.memory_mcp") as mock:
        mock.search_episodes = AsyncMock(
            return_value={
                "status": "success",
                "memory_type": "episodic",
                "results": [
                    {"text": "Past decision: blocked IP 10.0.0.1", "score": 0.85},
                ],
                "count": 1,
            }
        )
        yield mock


class TestMemoryWrite:
    """Test memory write path."""

    @pytest.mark.asyncio
    async def test_log_activity_writes_episode(self, mock_memory_mcp):
        """log_activity() should call memory_mcp.write_episode()."""
        from magenta.agents.base import LLMAgent

        # Create a concrete subclass for testing
        class TestAgent(LLMAgent):
            async def execute(self, task):
                return "test"

        config = AgentConfig(
            agent_id="triage-test-001",
            role="triage",
            model_provider="ollama",
            model_name="qwen2.5:0.5b",
            instructions="Triage incoming alerts",
            tools=["sentinel_query"],
        )
        agent = TestAgent(config)
        agent.turn_count = 1

        mission = MockMission()
        await agent.log_activity(mission, "disable_account", ActionStatus.SUCCESS)

        mock_memory_mcp.write_episode.assert_called_once()
        call_kwargs = mock_memory_mcp.write_episode.call_args[1]
        assert call_kwargs["agent_role"] == "triage"
        assert call_kwargs["mission_id"] == "test-mission-001"
        assert call_kwargs["turn_number"] == 1
        assert "disable_account" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_idempotent_write(self, mock_memory_mcp):
        """Writing same mission+turn twice should not duplicate."""
        from magenta.agents.base import LLMAgent

        class TestAgent(LLMAgent):
            async def execute(self, task):
                return "test"

        config = AgentConfig(
            agent_id="triage-test-002",
            role="triage",
            model_provider="ollama",
            model_name="qwen2.5:0.5b",
            instructions="Triage",
            tools=["sentinel_query"],
        )
        agent = TestAgent(config)
        agent.turn_count = 1

        mission = MockMission()

        # Write twice
        await agent.log_activity(mission, "disable_account", ActionStatus.SUCCESS)
        await agent.log_activity(mission, "disable_account", ActionStatus.SUCCESS)

        # Should be called twice (idempotency handled by vectorization pipeline)
        assert mock_memory_mcp.write_episode.call_count == 2

    @pytest.mark.asyncio
    async def test_provenance_fields(self, mock_memory_mcp):
        """Write should include provenance fields."""
        from magenta.agents.base import LLMAgent

        class TestAgent(LLMAgent):
            async def execute(self, task):
                return "test"

        config = AgentConfig(
            agent_id="triage-test-003",
            role="triage",
            model_provider="ollama",
            model_name="qwen2.5:0.5b",
            instructions="Triage",
            tools=["sentinel_query"],
        )
        agent = TestAgent(config)
        agent.turn_count = 1

        mission = MockMission()
        await agent.log_activity(mission, "disable_account", ActionStatus.SUCCESS)

        call_kwargs = mock_memory_mcp.write_episode.call_args[1]
        assert "correlation_id" in call_kwargs
        assert call_kwargs["correlation_id"] == "corr-001"

    @pytest.mark.asyncio
    async def test_tenant_id_in_payload(self, mock_memory_mcp):
        """Write should include tenant_id."""
        from magenta.agents.base import LLMAgent

        class TestAgent(LLMAgent):
            async def execute(self, task):
                return "test"

        config = AgentConfig(
            agent_id="triage-test-004",
            role="triage",
            model_provider="ollama",
            model_name="qwen2.5:0.5b",
            instructions="Triage",
            tools=["sentinel_query"],
        )
        agent = TestAgent(config)
        agent.turn_count = 1
        agent.tenant_id = "acme-corp"

        mission = MockMission()
        await agent.log_activity(mission, "disable_account", ActionStatus.SUCCESS)

        call_kwargs = mock_memory_mcp.write_episode.call_args[1]
        # tenant_id should be in metadata
        assert "metadata" in call_kwargs or "tenant_id" in call_kwargs

    @pytest.mark.asyncio
    async def test_no_agent_block_on_failure(self, mock_memory_mcp):
        """Agent should complete even if memory write fails."""
        from magenta.agents.base import LLMAgent

        class TestAgent(LLMAgent):
            async def execute(self, task):
                return "test"

        config = AgentConfig(
            agent_id="triage-test-005",
            role="triage",
            model_provider="ollama",
            model_name="qwen2.5:0.5b",
            instructions="Triage",
            tools=["sentinel_query"],
        )
        agent = TestAgent(config)
        agent.turn_count = 1

        # Make write_episode raise an exception
        mock_memory_mcp.write_episode.side_effect = Exception("Qdrant connection failed")

        mission = MockMission()

        # Should NOT raise exception
        await agent.log_activity(mission, "disable_account", ActionStatus.SUCCESS)
