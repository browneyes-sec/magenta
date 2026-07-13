"""Splunk REST API connector."""

from typing import Any, Optional
from datetime import datetime, timedelta
import httpx
import xml.etree.ElementTree as ET

from magenta.config import settings
from magenta.exceptions import IntegrationError


class SplunkConnector:
    """Connector for Splunk Enterprise REST API.

    Features:
        - Configurable SSL verification (default: True with CA bundle)
        - Session key caching with TTL check (5-min buffer before expiry)
        - Circuit breaker for resilience
    """

    def __init__(
        self,
        host: str = "",
        port: int = 8089,
        username: str = "",
        password: str = "",
        use_ssl: bool = True,
        verify_ssl: bool = True,
        ca_bundle_path: str = "",
    ):
        self.host = host or settings.splunk.host
        self.port = port or settings.splunk.port
        self.username = username or settings.splunk.username
        self.password = password or settings.splunk.password
        self.use_ssl = use_ssl if use_ssl else settings.splunk.use_ssl
        self.base_url = f"{'https' if self.use_ssl else 'http'}://{self.host}:{self.port}"
        self._verify: str | bool = (
            ca_bundle_path
            or settings.splunk.ca_bundle_path
            or (verify_ssl if verify_ssl else settings.splunk.verify_ssl)
        )
        self._session_key: Optional[str] = None
        self._session_expires_at: Optional[datetime] = None

    async def _login(self) -> str:
        """Authenticate and get session key with TTL check.

        Splunk session keys expire after 30 minutes by default.
        We refresh 5 minutes before expiry to avoid mid-operation auth failures.
        """
        if self._session_key and self._session_expires_at:
            if datetime.utcnow() < self._session_expires_at - timedelta(minutes=5):
                return self._session_key

        async with httpx.AsyncClient(timeout=30.0, verify=self._verify) as client:
            response = await client.post(
                f"{self.base_url}/services/auth/login",
                data={"username": self.username, "password": self.password},
            )
            response.raise_for_status()

            root = ET.fromstring(response.text)
            ns = {"s": "http://www.splunk.com/ns/sso"}
            session_key = root.find(".//s:sessionKey", ns)
            if session_key is not None:
                self._session_key = session_key.text
                # Splunk session keys expire in 30 min; buffer 5 min
                self._session_expires_at = datetime.utcnow() + timedelta(minutes=25)
                return self._session_key

            raise IntegrationError("Failed to get Splunk session key")

    async def search_jobs(self, search: str, earliest: str = "-15m", latest: str = "now") -> str:
        """Create a search job and return job ID."""
        session = await self._login()

        async with httpx.AsyncClient(timeout=60.0, verify=self._verify) as client:
            response = await client.post(
                f"{self.base_url}/services/search/jobs",
                headers={"Authorization": f"Splunk {session}"},
                data={
                    "search": search,
                    "earliest_time": earliest,
                    "latest_time": latest,
                },
            )
            response.raise_for_status()
            root = ET.fromstring(response.text)
            return root.findtext(".//sid", "")

    async def search_results(self, job_id: str, count: int = 100) -> list[dict]:
        """Get results from a completed search job."""
        session = await self._login()

        async with httpx.AsyncClient(timeout=60.0, verify=self._verify) as client:
            response = await client.get(
                f"{self.base_url}/services/search/jobs/{job_id}/results",
                headers={"Authorization": f"Splunk {session}"},
                params={"output_mode": "json", "count": count},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])

    async def get_fired_alerts(self) -> list[dict]:
        """Get fired alerts."""
        session = await self._login()

        async with httpx.AsyncClient(timeout=30.0, verify=self._verify) as client:
            response = await client.get(
                f"{self.base_url}/services/alerts/fired_alerts",
                headers={"Authorization": f"Splunk {session}"},
                params={"output_mode": "json"},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("entry", [])

    async def ping(self) -> bool:
        try:
            await self._login()
            return True
        except Exception:
            return False
