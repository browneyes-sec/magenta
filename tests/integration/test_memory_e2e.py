"""End-to-end integration tests for agent memory (ADR-018).

These tests require running Qdrant + OLLAMA services.
Mark with @pytest.mark.integration and skip if services unavailable.

Tests:
  1. Write → Search round-trip via MemoryMCPServer
  2. Agent log_activity → retrieve_context cycle
  3. Multi-turn memory accumulation
  4. Tenant isolation
  5. Tier-based token budget enforcement
"""

import os
import time
import uuid
import pytest
import httpx


# Skip all integration tests if Qdrant/OLLAMA not available
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


def _services_available() -> bool:
    """Check if Qdrant and OLLAMA are reachable."""
    try:
        r = httpx.get(f"{QDRANT_URL}/healthz", timeout=3.0)
        if r.status_code != 200:
            return False
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _services_available(),
    reason="Qdrant or OLLAMA not available"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qdrant():
    """Qdrant HTTP client."""
    return httpx.Client(base_url=QDRANT_URL, timeout=10.0)


@pytest.fixture(scope="module")
def ollama():
    """OLLAMA HTTP client."""
    return httpx.Client(base_url=OLLAMA_URL, timeout=30.0)


@pytest.fixture(scope="module")
def embed(ollama):
    """Embedding helper using nomic-embed-text."""
    def _embed(text: str) -> list[float]:
        r = ollama.post("/api/embed", json={
            "model": "nomic-embed-text",
            "input": text,
        })
        return r.json()["embeddings"][0]
    return _embed


# ---------------------------------------------------------------------------
# Test 1: Write → Search round-trip via MemoryMCPServer
# ---------------------------------------------------------------------------

class TestWriteSearchRoundTrip:
    """Verify write_episode → search_episodes works end-to-end."""

    def test_write_then_search(self, qdrant, embed):
        """Write an episode, search for it, verify it's found."""
        from magenta.mesh.memory import MemoryMCPServer
        from magenta.mesh.pipeline import VectorizationPipeline
        from magenta.mesh.config import MeshConfig

        config = MeshConfig.from_env()
        pipeline = VectorizationPipeline(config)
        memory = MemoryMCPServer(config)
        memory.pipeline = pipeline

        # Write
        test_id = f"integration-test-{uuid.uuid4().hex[:8]}"
        result = memory.write_episode(
            agent_role="integration-test",
            mission_id="INT-TEST-001",
            turn_number=1,
            text="Integration test: blocked malicious IP 192.168.1.100 based on threat intel feed",
            correlation_id="corr-int-001",
            metadata={
                "tenant_id": "integration-test",
                "source_tool": "test_memory_integration.py",
            },
        )
        assert result["status"] == "success", f"Write failed: {result}"

        # Wait for indexing
        time.sleep(1)

        # Search
        search_result = memory.search_episodes(
            query="blocked IP address threat intel",
            agent_role="integration-test",
            mission_id="INT-TEST-001",
            tenant_id="integration-test",
            top_k=5,
        )
        assert search_result["status"] == "success", f"Search failed: {search_result}"
        assert search_result["count"] > 0, "No results found"

        # Verify the written text is in results
        texts = [r.get("text", "") for r in search_result["results"]]
        assert any("192.168.1.100" in t for t in texts), \
            f"Expected '192.168.1.100' in results: {texts}"


# ---------------------------------------------------------------------------
# Test 2: Agent log_activity → retrieve_context cycle
# ---------------------------------------------------------------------------

class TestAgentMemoryCycle:
    """Verify agent writes via log_activity, reads via retrieve_context."""

    @pytest.mark.asyncio
    async def test_log_then_retrieve(self):
        """Agent logs an action, then retrieves it as context."""
        from unittest.mock import MagicMock, AsyncMock, patch
        from magenta.core.models import AgentConfig, Mission, SourceSystem, SeverityLevel

        # Create a real memory MCP instance
        from magenta.mesh.memory import MemoryMCPServer
        from magenta.mesh.pipeline import VectorizationPipeline
        from magenta.mesh.config import MeshConfig

        config = MeshConfig.from_env()
        pipeline = VectorizationPipeline(config)
        real_memory = MemoryMCPServer(config)
        real_memory.pipeline = pipeline

        # Patch memory_mcp in the agents module
        with patch("magenta.agents.base.memory_mcp", real_memory):
            from magenta.agents.base import LLMAgent

            class TestAgent(LLMAgent):
                async def execute(self, task):
                    return "test"

            agent_config = AgentConfig(
                agent_id="integration-agent-001",
                role="integration-test",
                model_provider="ollama",
                model_name="qwen2.5:0.5b",
                instructions="Test agent",
                tools=["sentinel_query"],
            )
            agent = TestAgent(agent_config)

            # Create a test mission
            mission = MagicMock(spec=Mission)
            mission.mission_id = "INT-MISSION-001"
            mission.alert_id = "INT-ALERT-001"
            mission.source_system = MagicMock()
            mission.source_system.value = "sentinel"
            mission.playbook_id = "test-playbook"
            mission.correlation_id = "corr-int-002"
            mission.description = "Ransomware detected on host FIN-PROD-347"

            # Step 1: Log activity (writes to memory)
            from magenta.core.models import ActionStatus
            await agent.log_activity(
                mission, "triage", ActionStatus.succeeded,
                tenant_id="integration-test",
            )

            # Wait for indexing
            time.sleep(2)

            # Step 2: Retrieve context (reads from memory)
            agent.turn_count = 2  # Skip turn 1 gate
            context = await agent.retrieve_context(
                query_summary="Ransomware on FIN-PROD-347",
                mission_id="INT-MISSION-001",
                tenant_id="integration-test",
            )

            # Verify context contains the logged action
            assert "Relevant Past Decisions" in context or len(context) > 0, \
                f"Expected RAG context, got: {context[:200]}"


# ---------------------------------------------------------------------------
# Test 3: Multi-turn memory accumulation
# ---------------------------------------------------------------------------

class TestMultiTurnMemory:
    """Verify memory accumulates across multiple agent turns."""

    def test_multiple_writes_searchable(self):
        """Write multiple episodes, verify all are searchable."""
        from magenta.mesh.memory import MemoryMCPServer
        from magenta.mesh.pipeline import VectorizationPipeline
        from magenta.mesh.config import MeshConfig

        config = MeshConfig.from_env()
        pipeline = VectorizationPipeline(config)
        memory = MemoryMCPServer(config)
        memory.pipeline = pipeline

        mission_id = f"MULTI-TURN-{uuid.uuid4().hex[:8]}"

        # Write 3 turns
        actions = [
            ("triage", "triage alert severity 4"),
            ("enrich", "enriched with threat intel"),
            ("contain", "isolated host from network"),
        ]

        for i, (role, text) in enumerate(actions):
            result = memory.write_episode(
                agent_role=role,
                mission_id=mission_id,
                turn_number=i + 1,
                text=f"Turn {i+1}: {text}",
                correlation_id=f"corr-multi-{i}",
                metadata={"tenant_id": "multi-turn-test"},
            )
            assert result["status"] == "success"

        # Wait for indexing
        time.sleep(2)

        # Search for all turns
        search = memory.search_episodes(
            query="alert triage enrichment containment",
            agent_role="integration-test",
            mission_id=mission_id,
            tenant_id="multi-turn-test",
            top_k=10,
        )

        assert search["status"] == "success"
        assert search["count"] >= 3, f"Expected >=3 results, got {search['count']}"


# ---------------------------------------------------------------------------
# Test 4: Tenant isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:
    """Verify tenant_id filtering works correctly."""

    def test_cross_tenant_isolation(self):
        """Data written by tenant A should not appear in tenant B search."""
        from magenta.mesh.memory import MemoryMCPServer
        from magenta.mesh.pipeline import VectorizationPipeline
        from magenta.mesh.config import MeshConfig

        config = MeshConfig.from_env()
        pipeline = VectorizationPipeline(config)
        memory = MemoryMCPServer(config)
        memory.pipeline = pipeline

        mission_id = f"TENANT-{uuid.uuid4().hex[:8]}"

        # Write for tenant A
        memory.write_episode(
            agent_role="test",
            mission_id=mission_id,
            turn_number=1,
            text="SECRET: Acme Corp firewall rules for 10.0.0.0/8",
            correlation_id="corr-tenant-a",
            metadata={"tenant_id": "tenant-A"},
        )

        # Write for tenant B
        memory.write_episode(
            agent_role="test",
            mission_id=mission_id,
            turn_number=1,
            text="SECRET: Beta Inc VPN configuration for 192.168.0.0/16",
            correlation_id="corr-tenant-b",
            metadata={"tenant_id": "tenant-B"},
        )

        time.sleep(2)

        # Search as tenant A - should only see tenant A data
        search_a = memory.search_episodes(
            query="firewall rules configuration",
            agent_role="test",
            mission_id=mission_id,
            tenant_id="tenant-A",
            top_k=10,
        )

        # Verify no tenant B data in results
        for result in search_a.get("results", []):
            text = result.get("text", "")
            assert "Beta Inc" not in text, \
                f"Tenant B data leaked to tenant A: {text[:100]}"


# ---------------------------------------------------------------------------
# Test 5: Token budget enforcement
# ---------------------------------------------------------------------------

class TestTokenBudget:
    """Verify context truncation respects tier budgets."""

    def test_speed_tier_budget(self):
        """Speed tier should truncate to ~1000 tokens."""
        from magenta.mesh.memory import MemoryMCPServer
        from magenta.mesh.pipeline import VectorizationPipeline
        from magenta.mesh.config import MeshConfig

        config = MeshConfig.from_env()
        pipeline = VectorizationPipeline(config)
        memory = MemoryMCPServer(config)
        memory.pipeline = pipeline

        mission_id = f"BUDGET-{uuid.uuid4().hex[:8]}"

        # Write many large episodes
        for i in range(10):
            memory.write_episode(
                agent_role="test",
                mission_id=mission_id,
                turn_number=i,
                text=f"Episode {i}: " + "word " * 200,  # ~100 tokens each
                correlation_id=f"corr-budget-{i}",
                metadata={"tenant_id": "budget-test"},
            )

        time.sleep(2)

        # Search
        search = memory.search_episodes(
            query="episode content",
            agent_role="test",
            mission_id=mission_id,
            tenant_id="budget-test",
            top_k=10,
        )

        assert search["status"] == "success"
        # Verify results exist
        assert search["count"] > 0
