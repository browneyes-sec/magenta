"""Microsoft Defender ATP connector."""

from typing import Any, Optional
import logging

import httpx

from magenta.exceptions import IntegrationError
from magenta.config import settings

logger = logging.getLogger(__name__)


class DefenderConnector:
    """Connector for Microsoft Defender ATP via Graph Security API.

    Uses DefaultAzureCredential for managed identity when no explicit
    credentials are provided. Falls back to client_credentials flow
    for local development with explicit tenant/client/secret.
    """

    def __init__(
        self,
        tenant_id: str = "",
        client_id: str = "",
        client_secret: str = "",
    ):
        self.tenant_id = tenant_id or settings.azure_auth.tenant_id
        self.client_id = client_id or settings.azure_auth.client_id
        self.client_secret = client_secret or settings.azure_auth.client_secret
        self._token: Optional[str] = None
        self._credential = None
        self._use_default = (
            settings.azure_auth.use_default_credential
            and not (self.client_id and self.client_secret)
        )

    async def _get_token(self) -> str:
        if self._token:
            return self._token

        if self._use_default:
            return await self._acquire_via_default_credential()

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

    async def _acquire_via_default_credential(self) -> str:
        try:
            from azure.identity.aio import DefaultAzureCredential

            if self._credential is None:
                self._credential = DefaultAzureCredential()
            token = await self._credential.get_token(
                "https://api.security.microsoft.com/.default"
            )
            self._token = token.token
            return self._token
        except Exception as exc:
            logger.warning("DefaultAzureCredential failed: %s", exc)
            raise IntegrationError("Unable to authenticate with DefaultAzureCredential")

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
