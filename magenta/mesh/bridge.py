"""Memory bridge for pipeline tools.

Provides HTTP client helpers for pipelines to read/write memory
via the Magenta API mesh endpoints.

Usage in pipelines:
    from magenta.mesh.bridge import MemoryBridge
    
    bridge = MemoryBridge(api_url="http://magenta-api:8000")
    
    # Write episodic memory
    await bridge.write_episode(
        agent_role="operator",
        mission_id="M123",
        turn_number=0,
        text="Approved firewall rule change for 10.0.0.0/8",
    )
    
    # Search episodic memory
    results = await bridge.search_episodes(
        query="firewall rule changes",
        top_k=5,
    )
"""

import hashlib
import time
from typing import Any, Optional

import httpx


class MemoryBridge:
    """HTTP client for pipeline ↔ memory integration."""

    def __init__(self, api_url: str = "http://magenta-api:8000", timeout: float = 10.0):
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                timeout=self.timeout,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Episodic Memory ─────────────────────────────────────────────

    async def write_episode(
        self,
        agent_role: str,
        mission_id: str,
        turn_number: int,
        text: str,
        correlation_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Write to episodic memory."""
        client = await self._get_client()
        payload = {
            "agent_role": agent_role,
            "mission_id": mission_id,
            "turn_number": turn_number,
            "text": text,
            "correlation_id": correlation_id,
            "metadata": metadata or {},
        }
        r = await client.post("/api/v1/mesh/memory/write-episode", json=payload)
        return r.json()

    async def search_episodes(
        self,
        query: str,
        agent_role: str = "",
        mission_id: str = "",
        tenant_id: str = "",
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search episodic memory."""
        client = await self._get_client()
        payload = {
            "query": query,
            "top_k": top_k,
        }
        if agent_role:
            payload["agent_role"] = agent_role
        if mission_id:
            payload["mission_id"] = mission_id
        if tenant_id:
            payload["tenant_id"] = tenant_id
        r = await client.post("/api/v1/mesh/memory/search-episodic", json=payload)
        result = r.json()
        return result.get("results", [])

    # ── Semantic Memory ─────────────────────────────────────────────

    async def write_semantic(
        self,
        text: str,
        product: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Write to semantic memory."""
        client = await self._get_client()
        payload = {
            "text": text,
            "product": product,
            "tags": tags or [],
            "metadata": metadata or {},
        }
        r = await client.post("/api/v1/mesh/memory/write-semantic", json=payload)
        return r.json()

    async def search_semantic(
        self,
        query: str,
        product: str = "",
        tags: list[str] | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search semantic memory."""
        client = await self._get_client()
        payload = {
            "query": query,
            "top_k": top_k,
        }
        if product:
            payload["product"] = product
        if tags:
            payload["tags"] = tags
        r = await client.post("/api/v1/mesh/memory/search-semantic", json=payload)
        result = r.json()
        return result.get("results", [])

    # ── Procedural Memory ───────────────────────────────────────────

    async def write_procedure(
        self,
        tool_name: str,
        text: str,
        parameters: dict[str, Any] | None = None,
        mission_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Write to procedural memory."""
        client = await self._get_client()
        payload = {
            "tool_name": tool_name,
            "text": text,
            "parameters": parameters or {},
            "mission_id": mission_id,
            "metadata": metadata or {},
        }
        r = await client.post("/api/v1/mesh/memory/write-procedure", json=payload)
        return r.json()

    async def search_procedures(
        self,
        query: str,
        tool_name: str = "",
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search procedural memory."""
        client = await self._get_client()
        payload = {
            "query": query,
            "top_k": top_k,
        }
        if tool_name:
            payload["tool_name"] = tool_name
        r = await client.post("/api/v1/mesh/memory/search-procedures", json=payload)
        result = r.json()
        return result.get("results", [])

    # ── Convenience Methods ─────────────────────────────────────────

    async def log_decision(
        self,
        agent_role: str,
        mission_id: str,
        decision: str,
        outcome: str,
        tenant_id: str = "default",
    ) -> dict[str, Any]:
        """Log a human or agent decision to episodic memory."""
        text = f"Decision: {decision} | Outcome: {outcome}"
        return await self.write_episode(
            agent_role=agent_role,
            mission_id=mission_id,
            turn_number=0,
            text=text,
            metadata={"tenant_id": tenant_id, "decision_type": "human"},
        )

    async def log_approval(
        self,
        mission_id: str,
        action: str,
        decision: str,
        approver: str,
        tenant_id: str = "default",
    ) -> dict[str, Any]:
        """Log an approval decision to episodic memory."""
        text = f"Approval: {decision} | Action: {action} | Approver: {approver}"
        return await self.write_episode(
            agent_role="operator",
            mission_id=mission_id,
            turn_number=0,
            text=text,
            metadata={"tenant_id": tenant_id, "decision_type": "approval"},
        )

    async def get_similar_incidents(
        self,
        alert_description: str,
        top_k: int = 5,
        tenant_id: str = "default",
    ) -> list[dict[str, Any]]:
        """Find similar past incidents for context."""
        return await self.search_episodes(
            query=alert_description,
            top_k=top_k,
            tenant_id=tenant_id,
        )

    async def get_playbook(
        self,
        incident_type: str,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """Find relevant playbooks/procedures."""
        return await self.search_semantic(
            query=incident_type,
            product="playbook",
            top_k=top_k,
        )
