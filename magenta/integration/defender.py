"""Microsoft Defender ATP connector."""

from typing import Any, Optional
import httpx

from magenta.exceptions import IntegrationError


class DefenderConnector:
    """Connector for Microsoft Defender ATP via Graph Security API."""

    def __init__(
        self,
        tenant_id: str = "",
        client_id: str = "",
        client_secret: str = "",
    ):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: Optional[str] = None

    async def _get_token(self) -> str:
        if self._token:
            return self._token

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "https://api.security.microsoft.com/.default",
                },
            )
            response.raise_for_status()
            data = response.json()
            self._token = data["access_token"]
            return self._token

    async def _get(self, path: str) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"https://api.security.microsoft.com/api/{path.lstrip('/')}",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.json()

    async def _post(self, path: str, body: dict) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"https://api.security.microsoft.com/api/{path.lstrip('/')}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            response.raise_for_status()
            return response.json()

    async def get_alerts(self, filter: str = "") -> list[dict]:
        """Get Defender alerts."""
        params = f"?$filter={filter}" if filter else ""
        data = await self._get(f"alerts{params}")
        return data.get("value", [])

    async def isolate_device(self, device_id: str, isolation_type: str = "Full") -> dict:
        """Isolate a device from the network."""
        return await self._post(
            f"machines/{device_id}/isolate",
            {"isolationType": isolation_type},
        )

    async def release_device(self, device_id: str) -> dict:
        """Release an isolated device."""
        return await self._post(f"machines/{device_id}/unisolate", {})

    async def run_scan(self, device_id: str, scan_type: str = "Quick") -> dict:
        """Run antivirus scan on a device."""
        return await self._post(
            f"machines/{device_id}/runAntiVirusScan",
            {"ScanType": scan_type},
        )

    async def get_device(self, device_id: str) -> dict:
        """Get device details."""
        return await self._get(f"machines/{device_id}")

    async def ping(self) -> bool:
        try:
            await self._get_token()
            return True
        except Exception:
            return False
