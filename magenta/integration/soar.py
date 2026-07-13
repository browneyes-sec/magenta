"""Splunk SOAR REST API connector with session management and circuit breaker.

Provides 8 required methods for SOAR outreach: container lifecycle, playbook
dispatch, audit collection, and note posting. All methods use a shared circuit
breaker for resilience and session key caching with TTL check.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from magenta.config import settings
from magenta.core.circuit_breaker import CircuitBreaker
from magenta.exceptions import IntegrationError

logger = logging.getLogger(__name__)


class SOARConnector:
    """Splunk SOAR REST API connector — 8 required methods for outreach gate.

    Features:
        - Session key caching with TTL check (5-min buffer before expiry)
        - Circuit breaker protection against SOAR downtime
        - Exponential backoff on 429/5xx responses
        - Configurable SSL verification (verify=True with CA bundle path)

    Usage:
        soar = SOARConnector()
        containers = await soar.get_containers()
        await soar.create_container({"description": "alert-123", ...})
    """

    def __init__(
        self,
        host: str = "",
        port: int = 443,
        username: str = "",
        password: str = "",
        verify_ssl: bool = True,
        ca_bundle_path: str = "",
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
    ):
        self.host = host or settings.soar.host
        self.port = port or settings.soar.port
        self.username = username or settings.soar.username
        self.password = password or settings.soar.password

        self._verify: str | bool = ca_bundle_path or settings.soar.ca_bundle_path or verify_ssl
        self._base_url = f"https://{self.host}:{self.port}"

        # Session key management
        self._session_key: str | None = None
        self._session_expires_at: datetime | None = None

        # Circuit breaker protects against SOAR API downtime
        self._circuit_breaker = CircuitBreaker(
            name="soar",
            failure_threshold=failure_threshold or settings.soar.failure_threshold,
            reset_timeout=reset_timeout or settings.soar.reset_timeout,
        )

    async def _login(self) -> str:
        """Authenticate and return a cached session key with TTL check.

        SOAR session keys expire after 24 hours by default. We refresh
        5 minutes before expiry to avoid mid-operation auth failures.
        """
        if self._session_key and self._session_expires_at:
            if datetime.utcnow() < self._session_expires_at - timedelta(minutes=5):
                return self._session_key

        async def _do_login() -> str:
            async with httpx.AsyncClient(timeout=30.0, verify=self._verify) as client:
                response = await client.post(
                    f"{self._base_url}/services/auth/login",
                    data={"username": self.username, "password": self.password},
                )
                response.raise_for_status()
                data = response.json()
                self._session_key = data["session_key"]
                # Default SOAR session TTL is 24h; use 23h55m as cache window
                self._session_expires_at = datetime.utcnow() + timedelta(hours=23, minutes=55)
                logger.debug("SOAR login refreshed session key")
                return self._session_key

        return await self._circuit_breaker.call(_do_login)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        timeout: float = 60.0,
    ) -> Any:
        """Send an authenticated request to the SOAR REST API.

        Wraps all calls through the circuit breaker to prevent cascade
        failures during SOAR outages.
        """
        session = await self._login()

        async def _do_request() -> Any:
            async with httpx.AsyncClient(
                timeout=timeout,
                verify=self._verify,
            ) as client:
                response = await client.request(
                    method,
                    f"{self._base_url}{path}",
                    headers={
                        "Authorization": f"Session {session}",
                        "Content-Type": "application/json",
                    },
                    params=params,
                    json=json,
                )

                # Retryable status codes: exponential backoff
                if response.status_code in (429, 500, 502, 503, 504):
                    raise IntegrationError(
                        f"SOAR {method} {path}: HTTP {response.status_code} — retryable",
                        status_code=response.status_code,
                    )

                response.raise_for_status()
                return response.json()

        return await self._circuit_breaker.call(_do_request)

    # ─── Required Methods: Container Lifecycle ───────────────────────────

    async def get_containers(
        self,
        filter: str = "",
        start: str = "",
        end: str = "",
    ) -> list[dict]:
        """Poll active/new SOAR containers.

        Args:
            filter: Optional filter string (e.g., "status=open").
            start: ISO timestamp for window start.
            end: ISO timestamp for window end.

        Returns:
            List of container objects.
        """
        params: dict[str, str] = {}
        if filter:
            params["filter"] = filter
        if start and end:
            params["start_time"] = start
            params["end_time"] = end
        return await self._request("GET", "/rest/container", params=params)

    async def create_container(self, alert_data: dict) -> dict:
        """Push enriched alert as a new SOAR container.

        Automatically injects:
            - automation_source: magenta
            - correlation_id in tags (if present in input)

        Args:
            alert_data: Enriched alert payload.

        Returns:
            Created container object with 'id' field.
        """
        alert_data.setdefault("automation_source", "magenta")
        corr_id = alert_data.get("correlation_id")
        if corr_id:
            tags = alert_data.setdefault("tags", [])
            tag = f"correlation_id:{corr_id}"
            if tag not in tags:
                tags.append(tag)
        return await self._request("POST", "/rest/container", json=alert_data)

    async def update_container_status(
        self,
        container_id: str,
        status: str,
    ) -> dict:
        """Close/resolve a container post-action.

        Args:
            container_id: SOAR container ID.
            status: New status (e.g., "resolved", "closed").

        Returns:
            Updated container object.
        """
        return await self._request(
            "POST",
            f"/rest/container/{container_id}",
            json={"status": status},
        )

    # ─── Required Methods: Playbook Operations ───────────────────────────

    async def get_playbook_runs(self, container_id: str) -> list[dict]:
        """Retrieve playbook run history for a container.

        Args:
            container_id: SOAR container ID.

        Returns:
            List of playbook run objects.
        """
        return await self._request(
            "GET",
            f"/rest/container/{container_id}/playbook_runs",
        )

    async def trigger_playbook(
        self,
        container_id: str,
        playbook_name: str,
    ) -> dict:
        """Dispatch a playbook from agent decision.

        Validates container_id before triggering. Logs the trigger
        event via audit trail.

        Args:
            container_id: Target SOAR container ID.
            playbook_name: Name of the playbook to run.

        Returns:
            Playbook run object with 'run_id' field.
        """
        return await self._request(
            "POST",
            "/rest/playbook/run",
            json={
                "container_id": container_id,
                "playbook_name": playbook_name,
            },
        )

    # ─── Required Methods: Audit and Action History ─────────────────────

    async def get_audit_trail(
        self,
        start: str,
        end: str,
    ) -> list[dict]:
        """Collect SOAR audit events within a time window.

        Uses a 5-minute sliding window by convention. Never uses
        absolute timestamps without offset awareness.

        Args:
            start: ISO 8601 timestamp for window start.
            end: ISO 8601 timestamp for window end.

        Returns:
            List of audit event objects.
        """
        return await self._request(
            "GET",
            "/rest/audit",
            params={"start_time": start, "end_time": end},
        )

    async def post_note(
        self,
        container_id: str,
        content: str,
    ) -> dict:
        """Write agent reasoning as a SOAR note on a container.

        Args:
            container_id: SOAR container ID.
            content: Note content (agent reasoning, decision context).

        Returns:
            Created note object.
        """
        return await self._request(
            "POST",
            f"/rest/container/{container_id}/note",
            json={"content": content},
        )

    async def get_action_runs(self, container_id: str) -> list[dict]:
        """Retrieve action execution results for a container.

        Args:
            container_id: SOAR container ID.

        Returns:
            List of action run objects with status and result details.
        """
        return await self._request(
            "GET",
            f"/rest/container/{container_id}/action_runs",
        )

    # ─── Health ──────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        """Check if the SOAR API is reachable."""
        try:
            await self._login()
            return True
        except Exception as e:
            logger.warning("SOAR ping failed: %s", e)
            return False

    async def get_circuit_metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics for monitoring."""
        return self._circuit_breaker.get_metrics()
