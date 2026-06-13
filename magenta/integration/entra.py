"""Entra ID (Azure AD) connector via Microsoft Graph API."""

from typing import Any, Optional
import httpx

from magenta.exceptions import IntegrationError


class EntraIDConnector:
    """Connector for Microsoft Entra ID via Graph API."""

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
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            response.raise_for_status()
            data = response.json()
            self._token = data["access_token"]
            return self._token

    async def _graph_get(self, path: str, params: dict = None) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://graph.microsoft.com/v1.0/{path.lstrip('/')}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                params=params or {},
            )
            response.raise_for_status()
            return response.json()

    async def _graph_post(self, path: str, body: dict) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://graph.microsoft.com/v1.0/{path.lstrip('/')}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            response.raise_for_status()
            return response.json()

    async def get_user(self, user_principal_name: str) -> dict:
        """Get user by UPN."""
        return await self._graph_get(f"users/{user_principal_name}")

    async def disable_account(self, user_principal_name: str) -> dict:
        """Disable a user account."""
        return await self._graph_patch(
            f"users/{user_principal_name}",
            {"accountEnabled": False},
        )

    async def enable_account(self, user_principal_name: str) -> dict:
        """Enable a user account."""
        return await self._graph_patch(
            f"users/{user_principal_name}",
            {"accountEnabled": True},
        )

    async def _graph_patch(self, path: str, body: dict) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.patch(
                f"https://graph.microsoft.com/v1.0/{path.lstrip('/')}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            response.raise_for_status()
            return {"status": "success"}

    async def get_signin_logs(self, user_id: str, hours: int = 24) -> list[dict]:
        """Get sign-in logs for a user."""
        from datetime import datetime, timedelta
        since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        data = await self._graph_get(
            f"auditLogs/signIns",
            params={"$filter": f"userId eq '{user_id}' and createdDateTime ge {since}"},
        )
        return data.get("value", [])

    async def ping(self) -> bool:
        try:
            await self._get_token()
            return True
        except Exception:
            return False
