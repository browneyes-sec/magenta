"""Cloud log collectors — Azure Monitor, Entra ID, AWS CloudTrail, GCP Cloud Logging."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx
from azure.identity.aio import DefaultAzureCredential

from magenta.integration.collectors.base import BaseCollector, CollectorConfig

logger = logging.getLogger(__name__)


class AzureMonitorCollector(BaseCollector):
    """Collects Azure Monitor / Log Analytics logs via LA query API.

    Queries configured log tables (SecurityEvent, AzureActivity, Syslog,
    etc.) on a polling interval and publishes raw records.
    """

    def __init__(self, config: CollectorConfig):
        super().__init__(config)
        self._workspace_id = config.options.get("workspace_id", "")
        self._tables = config.options.get(
            "tables",
            [
                "AzureActivity",
                "SecurityEvent",
                "SigninLogs",
            ],
        )
        self._lookback_hours = config.options.get("lookback_hours", 1)
        self._credential: DefaultAzureCredential | None = None
        self._token: str | None = None

    async def _ensure_token(self) -> str:
        if self._token:
            return self._token
        self._credential = DefaultAzureCredential()
        token = await self._credential.get_token("https://api.loganalytics.io/.default")
        self._token = token.token
        return self._token

    async def collect(self) -> list[dict]:
        if not self._running:
            return []
        token = await self._ensure_token()
        since = (datetime.now(UTC) - timedelta(hours=self._lookback_hours)).isoformat()
        events: list[dict] = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            for table in self._tables:
                query = f"{table} | where TimeGenerated >= datetime({since}) | order by TimeGenerated asc | take 5000"
                try:
                    resp = await client.post(
                        f"https://api.loganalytics.io/v1/workspaces/{self._workspace_id}/query",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                        },
                        json={"query": query},
                    )
                    resp.raise_for_status()
                    rows = self._parse_kql_result(resp.json())
                    for row in rows:
                        row["_collector"] = self.config.name
                        row["_table"] = table
                    events.extend(rows)
                    logger.info("Fetched %d rows from table=%s", len(rows), table)
                except httpx.HTTPStatusError as e:
                    logger.warning("LA query failed for table=%s: %s", table, e.response.text[:200])

        return events

    @staticmethod
    def _parse_kql_result(data: dict) -> list[dict]:
        rows = []
        for table in data.get("tables", []):
            columns = [c["name"] for c in table.get("columns", [])]
            for row in table.get("rows", []):
                rows.append(dict(zip(columns, row)))
        return rows

    async def health(self) -> dict:
        return {
            "collector": self.config.name,
            "source_type": self.config.source_type,
            "workspace_id": self._workspace_id[-8:],
            "tables": self._tables,
            "running": self._running,
            "credential": "DefaultAzureCredential",
        }


class EntraIDLogCollector(BaseCollector):
    """Collects Entra ID audit and sign-in logs via Microsoft Graph API."""

    def __init__(self, config: CollectorConfig):
        super().__init__(config)
        self._tenant_id = config.options.get("tenant_id", "")
        self._client_id = config.options.get("client_id", "")
        self._client_secret = config.options.get("client_secret", "")
        self._lookback_hours = config.options.get("lookback_hours", 1)
        self._token: str | None = None

    async def _ensure_token(self) -> str:
        if self._token:
            return self._token
        if self._client_id and self._client_secret:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "scope": "https://graph.microsoft.com/.default",
                    },
                )
                resp.raise_for_status()
                self._token = resp.json()["access_token"]
        else:
            cred = DefaultAzureCredential()
            token = await cred.get_token("https://graph.microsoft.com/.default")
            self._token = token.token
        return self._token

    async def collect(self) -> list[dict]:
        if not self._running:
            return []
        token = await self._ensure_token()
        since = (datetime.now(UTC) - timedelta(hours=self._lookback_hours)).isoformat()
        events: list[dict] = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            for log_type in ["auditLogs/signIns", "auditLogs/directoryAudits"]:
                try:
                    url = f"https://graph.microsoft.com/v1.0/{log_type}"
                    params = {"$filter": f"createdDateTime ge {since}", "$top": 1000}
                    while url:
                        resp = await client.get(
                            url, headers=headers, params=params if "?" not in url else {}
                        )
                        resp.raise_for_status()
                        data = resp.json()
                        for record in data.get("value", []):
                            record["_log_type"] = log_type.split("/")[-1]
                            events.append(record)
                        url = data.get("@odata.nextLink", "")
                        params = {}
                except httpx.HTTPStatusError as e:
                    logger.warning("Graph API error for %s: %s", log_type, e.response.text[:200])

        return events

    async def health(self) -> dict:
        return {
            "collector": self.config.name,
            "source_type": self.config.source_type,
            "tenant_id": self._tenant_id[-8:],
            "running": self._running,
        }


class AWSCloudTrailCollector(BaseCollector):
    """Collects AWS CloudTrail logs via S3 bucket polling.

    Lists and downloads CloudTrail JSON files from the configured
    S3 bucket path, parsing them into log events.
    """

    def __init__(self, config: CollectorConfig):
        super().__init__(config)
        self._bucket = config.options.get("s3_bucket", "")
        self._prefix = config.options.get("s3_prefix", "AWSLogs/")
        self._region = config.options.get("region", "us-east-1")

    async def collect(self) -> list[dict]:
        if not self._running or not self._bucket:
            return []
        try:
            import aioboto3

            session = aioboto3.Session()
            events: list[dict] = []
            async with session.client("s3", region_name=self._region) as s3:
                paginator = s3.get_paginator("list_objects_v2")
                async for page in paginator.paginate(Bucket=self._bucket, Prefix=self._prefix):
                    for obj in page.get("Contents", []):
                        if obj["Key"].endswith(".json"):
                            resp = await s3.get_object(Bucket=self._bucket, Key=obj["Key"])
                            body = await resp["Body"].read()
                            import json

                            records = json.loads(body).get("Records", [])
                            for r in records:
                                r["_s3_key"] = obj["Key"]
                            events.extend(records)
            return events
        except ImportError:
            logger.error("aioboto3 not installed — run 'uv sync --group aws'")
            return []
        except Exception as e:
            logger.exception("CloudTrail poll failed: %s", e)
            return []

    async def health(self) -> dict:
        return {
            "collector": self.config.name,
            "source_type": self.config.source_type,
            "bucket": self._bucket,
            "running": self._running,
        }


class GCPLoggingCollector(BaseCollector):
    """Collects GCP Cloud Logging via Pub/Sub subscription pull."""

    def __init__(self, config: CollectorConfig):
        super().__init__(config)
        self._project = config.options.get("gcp_project", "")
        self._subscription = config.options.get("pubsub_subscription", "")
        self._credentials_path = config.options.get("credentials_path", "")

    async def collect(self) -> list[dict]:
        if not self._running or not self._subscription:
            return []
        try:
            from google.cloud import pubsub_v1

            subscriber = (
                pubsub_v1.SubscriberClient.from_service_account_json(self._credentials_path)
                if self._credentials_path
                else pubsub_v1.SubscriberClient()
            )

            subscription_path = subscriber.subscription_path(self._project, self._subscription)
            events: list[dict] = []

            response = subscriber.pull(
                request={
                    "subscription": subscription_path,
                    "max_messages": 100,
                    "return_immediately": True,
                },
            )
            for msg in response.received_messages:
                import json

                events.append(json.loads(msg.message.data))
                subscriber.acknowledge(
                    request={"subscription": subscription_path, "ack_ids": [msg.ack_id]},
                )
            return events
        except ImportError:
            logger.error("google-cloud-pubsub not installed — run 'uv sync --group gcp'")
            return []
        except Exception as e:
            logger.exception("GCP Pub/Sub pull failed: %s", e)
            return []

    async def health(self) -> dict:
        return {
            "collector": self.config.name,
            "source_type": self.config.source_type,
            "project": self._project,
            "subscription": self._subscription,
            "running": self._running,
        }
