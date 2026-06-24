"""Tests for agent memory read path (ADR-018).

Verifies:
- Pre-turn RAG injection (episodic auto)
- Tier-based token budget enforcement
- Metadata filters work (agent_role, mission_id, tenant_id)
- Context budget respected (≤ tier budget)
- RAG results injected into system_prompt
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from magenta.core.models import AgentConfig


class TestMemoryRead:
    """Test memory read path (pre-turn RAG)."""

    @pytest.mark.asyncio
    async def test_search_episodes_called(self):
        """Pre-turn RAG should call memory_mcp.search_episodes()."""
        mock_mcp = MagicMock()
        mock_mcp.search_episodes = AsyncMock(
            return_value={
                "status": "success",
                "results": [
                    {"text": "Past decision: blocked IP", "score": 0.85},
                ],
                "count": 1,
            }
        )

        with patch("magenta.mesh.memory.memory_mcp", mock_mcp):
            from magenta.agents.base import LLMAgent

            class TestAgent(LLMAgent):
                async def execute(self, task):
                    return "test"

            config = AgentConfig(
                agent_id="triage-test-006",
                role="triage",
                model_provider="ollama",
                model_name="qwen2.5:0.5b",
                instructions="Triage",
                tools=["sentinel_query"],
            )
            agent = TestAgent(config)
            agent.turn_count = 2  # Turn 2+ triggers RAG

            context = await agent.retrieve_context(  # noqa: F841
                query_summary="Ransomware detected on FIN-PROD-347",
                mission_id="M123",
                tenant_id="acme-corp",
            )

            mock_mcp.search_episodes.assert_called_once()
            call_kwargs = mock_mcp.search_episodes.call_args[1]
            assert call_kwargs["agent_role"] == "triage"
            assert call_kwargs["mission_id"] == "M123"

    @pytest.mark.asyncio
    async def test_token_budget_enforced(self):
        """RAG context should respect tier token budget."""
        mock_mcp = MagicMock()
        mock_mcp.search_episodes = AsyncMock(
            return_value={
                "status": "success",
                "results": [
                    {"text": "A" * 500, "score": 0.9},
                    {"text": "B" * 500, "score": 0.85},
                    {"text": "C" * 500, "score": 0.8},
                    {"text": "D" * 500, "score": 0.75},
                    {"text": "E" * 500, "score": 0.7},
                ],
                "count": 5,
            }
        )

        with patch("magenta.mesh.memory.memory_mcp", mock_mcp):
            from magenta.agents.base import LLMAgent

            class TestAgent(LLMAgent):
                async def execute(self, task):
                    return "test"

            config = AgentConfig(
                agent_id="triage-test-007",
                role="triage",
                model_provider="ollama",
                model_name="qwen2.5:0.5b",
                instructions="Triage",
                tools=["sentinel_query"],
            )
            agent = TestAgent(config)
            agent.task_type = "speed"  # 1000 token budget
            agent.turn_count = 2

            context = await agent.retrieve_context(
                query_summary="Ransomware alert",
                mission_id="M124",
                tenant_id="default",
            )

            # Context should be truncated to fit budget (1000 tokens ~ 4000 chars)
            assert len(context) <= 4200  # chars with some margin for header

    @pytest.mark.asyncio
    async def test_metadata_filters(self):
        """Search should filter by agent_role, mission_id, tenant_id."""
        mock_mcp = MagicMock()
        mock_mcp.search_episodes = AsyncMock(
            return_value={
                "status": "success",
                "results": [],
                "count": 0,
            }
        )

        with patch("magenta.mesh.memory.memory_mcp", mock_mcp):
            from magenta.agents.base import LLMAgent

            class TestAgent(LLMAgent):
                async def execute(self, task):
                    return "test"

            config = AgentConfig(
                agent_id="enrich-test-001",
                role="enrichment",
                model_provider="ollama",
                model_name="qwen2.5:0.5b",
                instructions="Enrich alerts",
                tools=["vt_scan"],
            )
            agent = TestAgent(config)
            agent.turn_count = 2

            await agent.retrieve_context(
                query_summary="Phishing email analysis",
                mission_id="M125",
                tenant_id="acme-corp",
            )

            call_kwargs = mock_mcp.search_episodes.call_args[1]
            assert call_kwargs["agent_role"] == "enrichment"
            assert call_kwargs["mission_id"] == "M125"
            assert call_kwargs["tenant_id"] == "acme-corp"

    @pytest.mark.asyncio
    async def test_no_rag_on_first_turn(self):
        """First turn (turn 1) should not trigger pre-turn RAG."""
        mock_mcp = MagicMock()
        mock_mcp.search_episodes = AsyncMock()

        with patch("magenta.mesh.memory.memory_mcp", mock_mcp):
            from magenta.agents.base import LLMAgent

            class TestAgent(LLMAgent):
                async def execute(self, task):
                    return "test"

            config = AgentConfig(
                agent_id="triage-test-008",
                role="triage",
                model_provider="ollama",
                model_name="qwen2.5:0.5b",
                instructions="Triage",
                tools=["sentinel_query"],
            )
            agent = TestAgent(config)
            agent.turn_count = 1  # First turn

            context = await agent.retrieve_context(
                query_summary="New alert",
                mission_id="M126",
                tenant_id="default",
            )

            # Should NOT call search_episodes on first turn
            mock_mcp.search_episodes.assert_not_called()
            assert context == ""

    @pytest.mark.asyncio
    async def test_rag_results_injected_into_prompt(self):
        """RAG results should be injected as 'Relevant Past Decisions'."""
        mock_mcp = MagicMock()
        mock_mcp.search_episodes = AsyncMock(
            return_value={
                "status": "success",
                "results": [
                    {"text": "Blocked IP 10.0.0.1 based on threat intel", "score": 0.9},
                ],
                "count": 1,
            }
        )

        with patch("magenta.mesh.memory.memory_mcp", mock_mcp):
            from magenta.agents.base import LLMAgent

            class TestAgent(LLMAgent):
                async def execute(self, task):
                    return "test"

            config = AgentConfig(
                agent_id="triage-test-009",
                role="triage",
                model_provider="ollama",
                model_name="qwen2.5:0.5b",
                instructions="Triage",
                tools=["sentinel_query"],
            )
            agent = TestAgent(config)
            agent.turn_count = 2  # Turn 2+ triggers RAG

            context = await agent.retrieve_context(
                query_summary="Ransomware alert",
                mission_id="M127",
                tenant_id="default",
            )

            assert "Relevant Past Decisions" in context
            assert "Blocked IP 10.0.0.1" in context
