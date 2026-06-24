"""Splunk REST API connector."""

import xml.etree.ElementTree as ET

import httpx

from magenta.exceptions import IntegrationError


class SplunkConnector:
    """Connector for Splunk Enterprise REST API."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8089,
        username: str = "",
        password: str = "",
        use_ssl: bool = True,
    ):
        self.base_url = f"{'https' if use_ssl else 'http'}://{host}:{port}"
        self.username = username
        self.password = password
        self._session_key: str | None = None

    async def _login(self) -> str:
        """Authenticate and get session key."""
        if self._session_key:
            return self._session_key

        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
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
                return self._session_key

            raise IntegrationError("Failed to get Splunk session key")

    async def search_jobs(self, search: str, earliest: str = "-15m", latest: str = "now") -> str:
        """Create a search job and return job ID."""
        session = await self._login()

        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
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

        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
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

        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
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
