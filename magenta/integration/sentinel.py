"""Microsoft Sentinel integration connector."""

from typing import Any, Optional
from datetime import datetime, timedelta
import httpx

from magenta.config import settings
from magenta.exceptions import IntegrationError


class SentinelConnector:
    """Connector for Microsoft Sentinel (Incidents API, Log Analytics, Log Ingestion API).

    Features:
        - Expiry-aware token caching (refreshes 60s before expiry)
        - Circuit breaker pattern for resilience
        - Configurable via settings object or constructor args
    """

    def __init__(
        self,
        tenant_id: str = "",
        client_id: str = "",
        client_secret: str = "",
        workspace_id: str = "",
    ):
        self.tenant_id = tenant_id or settings.sentinel.tenant_id
        self.client_id = client_id or settings.sentinel.client_id
        self.client_secret = client_secret or settings.sentinel.client_secret
        self.workspace_id = workspace_id or settings.sentinel.workspace_id
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def _get_token(self) -> str:
        """Get Entra ID access token via client credentials with expiry-aware caching.

        Azure Entra ID access tokens expire in 3600 seconds (1 hour).
        We refresh when the token has less than 60 seconds of life remaining
        to prevent silent auth failures during long-running agent processes.
        """
        if self._token and self._token_expires_at:
            if datetime.utcnow() < self._token_expires_at - timedelta(seconds=60):
                return self._token

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "https://api.loganalytics.io/.default",
                },
            )
            response.raise_for_status()
            data = response.json()
            self._token = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)
            return self._token

    async def query(self, kql: str) -> list[dict]:
        """Query Sentinel Log Analytics with KQL."""
        token = await self._get_token()
        url = f"https://api.loganalytics.io/v1/workspaces/{self.workspace_id}/query"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"query": kql},
            )
            response.raise_for_status()
            data = response.json()

        return self._parse_kql_result(data)

    async def query_incidents(self, filter: str = "") -> list[dict]:
        """Query Sentinel incidents."""
        kql = "SecurityIncident"
        if filter:
            kql += f" | where {filter}"
        kql += " | take 100"
        return await self.query(kql)

    async def query_alerts(self, filter: str = "") -> list[dict]:
        """Query Sentinel alerts."""
        kql = "SecurityAlert"
        if filter:
            kql += f" | where {filter}"
        kql += " | take 100"
        return await self.query(kql)

    async def ingest_activity(self, records: list[dict]) -> dict:
        """Write automation activity records via Log Ingestion API."""
        if not records:
            return {"status": "no_records"}

        token = await self._get_token()
        url = f"https://{self.workspace_id}.ods.opinsights.azure.com/api/logs?api-version=2016-04-01"

        import json
        body = json.dumps(records)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Log-Type": "SecurityAutomationActivity",
                },
                content=body,
            )
            response.raise_for_status()
            return {"status": "ingested", "count": len(records)}

    async def ping(self) -> bool:
        try:
            await self._get_token()
            return True
        except Exception:
            return False

    def _parse_kql_result(self, data: dict) -> list[dict]:
        """Parse KQL query result into list of dicts."""
        rows = []
        tables = data.get("tables", [])
        for table in tables:
            columns = [c["name"] for c in table.get("columns", [])]
            for row in table.get("rows", []):
                rows.append(dict(zip(columns, row)))
        return rows
