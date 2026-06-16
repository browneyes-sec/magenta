"""Memory MCP Server — episodic, semantic, procedural memory via mesh gateway."""

from __future__ import annotations

import logging
from uuid import uuid4

from magenta.mesh.config import MeshConfig
from magenta.mesh.pipeline import VectorizationPipeline

logger = logging.getLogger(__name__)


class MemoryMCPServer:
    """MCP tools for agent memory operations.

    Integrates with the mesh gateway pipeline (chunker -> embedder -> indexer).
    All memory writes go through the vectorization pipeline for consistency.
    """

    def __init__(self, config: MeshConfig | None = None):
        self.name = "memory"
        self.description = "Agent memory MCP tools (episodic, semantic, procedural)"
        self.config = config or MeshConfig.from_env()
        self.pipeline = VectorizationPipeline(self.config)

    # ── Episodic Memory ─────────────────────────────────────────────────

    async def write_episode(
        self,
        agent_role: str,
        mission_id: str,
        turn_number: int,
        text: str,
        correlation_id: str = "",
        metadata: dict | None = None,
    ) -> dict:
        """Write an episodic memory (mission transcript, agent decision).

        Args:
            agent_role: Role of the agent (triage, enrichment, orchestrator, etc.)
            mission_id: Mission this episode belongs to.
            turn_number: Turn number within the mission.
            text: The episode text (decision, finding, action taken).
            correlation_id: Optional correlation ID linking to source alert.
            metadata: Additional metadata to store with the episode.
        """
        try:
            payload = {
                "agent_role": agent_role,
                "mission_id": mission_id,
                "turn_number": turn_number,
                "correlation_id": correlation_id,
                "memory_type": "episodic",
                **(metadata or {}),
            }

            result = await self.pipeline.ingest(
                collection="mem_episodic",
                documents=[{
                    "id": f"{mission_id}:{agent_role}:t{turn_number}",
                    "text": text,
                    "metadata": payload,
                }],
            )

            return {
                "status": "success" if result["ingested"] > 0 else "error",
                "memory_type": "episodic",
                "mission_id": mission_id,
                "agent_role": agent_role,
                "turn_number": turn_number,
                "chunks_ingested": result["ingested"],
                "errors": result["errors"],
            }
        except Exception as exc:
            logger.exception("Failed to write episodic memory")
            return {"status": "error", "error": str(exc)}

    async def search_episodes(
        self,
        query: str,
        agent_role: str = "",
        mission_id: str = "",
        top_k: int = 5,
    ) -> dict:
        """Search episodic memory for past agent decisions.

        Args:
            query: Natural language query.
            agent_role: Optional filter by agent role.
            mission_id: Optional filter by mission.
            top_k: Number of results to return.
        """
        try:
            filters = {}
            if agent_role:
                filters["agent_role"] = agent_role
            if mission_id:
                filters["mission_id"] = mission_id

            results = await self.pipeline.search(
                collection="mem_episodic",
                query=query,
                filters=filters or None,
                top_k=top_k,
            )

            return {
                "status": "success",
                "memory_type": "episodic",
                "results": results,
                "count": len(results),
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    # ── Semantic Memory ─────────────────────────────────────────────────

    async def write_semantic(
        self,
        text: str,
        product: str = "agent.memory.semantic",
        source: str = "agent",
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Write semantic memory (playbook, runbook, policy, knowledge).

        Args:
            text: The knowledge text.
            product: Data product ID.
            source: Source of the knowledge.
            tags: Tags for categorization.
            metadata: Additional metadata.
        """
        try:
            payload = {
                "product": product,
                "source": source,
                "tags": tags or [],
                "memory_type": "semantic",
                **(metadata or {}),
            }

            result = await self.pipeline.ingest(
                collection="mem_semantic",
                documents=[{
                    "id": str(uuid4()),
                    "text": text,
                    "metadata": payload,
                }],
            )

            return {
                "status": "success" if result["ingested"] > 0 else "error",
                "memory_type": "semantic",
                "chunks_ingested": result["ingested"],
                "errors": result["errors"],
            }
        except Exception as exc:
            logger.exception("Failed to write semantic memory")
            return {"status": "error", "error": str(exc)}

    async def search_semantic(
        self,
        query: str,
        product: str = "",
        tags: list[str] | None = None,
        top_k: int = 5,
    ) -> dict:
        """Search semantic memory for reusable knowledge.

        Args:
            query: Natural language query.
            product: Optional filter by data product.
            tags: Optional filter by tags.
            top_k: Number of results to return.
        """
        try:
            filters = {}
            if product:
                filters["product"] = product
            if tags:
                filters["tags"] = tags

            results = await self.pipeline.search(
                collection="mem_semantic",
                query=query,
                filters=filters or None,
                top_k=top_k,
            )

            return {
                "status": "success",
                "memory_type": "semantic",
                "results": results,
                "count": len(results),
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    # ── Procedural Memory ───────────────────────────────────────────────

    async def write_procedure(
        self,
        tool_name: str,
        text: str,
        parameters: dict | None = None,
        mission_id: str = "",
        metadata: dict | None = None,
    ) -> dict:
        """Write procedural memory (tool invocation pattern).

        Args:
            tool_name: Name of the tool invoked.
            text: Description of the tool usage pattern.
            parameters: Parameters used in the invocation.
            mission_id: Mission where this pattern was observed.
            metadata: Additional metadata.
        """
        import hashlib
        import json

        try:
            params_hash = hashlib.sha256(
                json.dumps(parameters or {}, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]

            payload = {
                "tool_name": tool_name,
                "parameters_hash": params_hash,
                "mission_id": mission_id,
                "memory_type": "procedural",
                **(metadata or {}),
            }

            result = await self.pipeline.ingest(
                collection="mem_procedural",
                documents=[{
                    "id": f"{tool_name}:{params_hash}:{str(uuid4())[:8]}",
                    "text": text,
                    "metadata": payload,
                }],
            )

            return {
                "status": "success" if result["ingested"] > 0 else "error",
                "memory_type": "procedural",
                "tool_name": tool_name,
                "chunks_ingested": result["ingested"],
                "errors": result["errors"],
            }
        except Exception as exc:
            logger.exception("Failed to write procedural memory")
            return {"status": "error", "error": str(exc)}

    async def search_procedures(
        self,
        query: str,
        tool_name: str = "",
        top_k: int = 5,
    ) -> dict:
        """Search procedural memory for tool usage patterns.

        Args:
            query: Natural language query.
            tool_name: Optional filter by tool name.
            top_k: Number of results to return.
        """
        try:
            filters = {}
            if tool_name:
                filters["tool_name"] = tool_name

            results = await self.pipeline.search(
                collection="mem_procedural",
                query=query,
                filters=filters or None,
                top_k=top_k,
            )

            return {
                "status": "success",
                "memory_type": "procedural",
                "results": results,
                "count": len(results),
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    # ── MCP Tool Definitions ────────────────────────────────────────────

    async def get_tools(self) -> list[dict]:
        """Return MCP tool definitions for this server."""
        return [
            {
                "name": "memory.write_episode",
                "description": "Write episodic memory (mission transcript, agent decision)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_role": {"type": "string", "description": "Agent role"},
                        "mission_id": {"type": "string", "description": "Mission ID"},
                        "turn_number": {"type": "integer", "description": "Turn number"},
                        "text": {"type": "string", "description": "Episode text"},
                        "correlation_id": {"type": "string", "default": ""},
                    },
                    "required": ["agent_role", "mission_id", "turn_number", "text"],
                },
            },
            {
                "name": "memory.search_episodes",
                "description": "Search episodic memory for past agent decisions",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "agent_role": {"type": "string", "default": ""},
                        "mission_id": {"type": "string", "default": ""},
                        "top_k": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "memory.write_semantic",
                "description": "Write semantic memory (playbook, runbook, policy)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Knowledge text"},
                        "product": {"type": "string", "default": "agent.memory.semantic"},
                        "source": {"type": "string", "default": "agent"},
                        "tags": {"type": "array", "items": {"type": "string"}, "default": []},
                    },
                    "required": ["text"],
                },
            },
            {
                "name": "memory.search_semantic",
                "description": "Search semantic memory for reusable knowledge",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "product": {"type": "string", "default": ""},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "top_k": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "memory.write_procedure",
                "description": "Write procedural memory (tool invocation pattern)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tool_name": {"type": "string", "description": "Tool name"},
                        "text": {"type": "string", "description": "Usage pattern description"},
                        "parameters": {"type": "object", "default": {}},
                        "mission_id": {"type": "string", "default": ""},
                    },
                    "required": ["tool_name", "text"],
                },
            },
            {
                "name": "memory.search_procedures",
                "description": "Search procedural memory for tool usage patterns",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "tool_name": {"type": "string", "default": ""},
                        "top_k": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            },
        ]


memory_mcp = MemoryMCPServer()
