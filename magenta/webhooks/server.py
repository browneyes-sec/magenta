"""Webhook receiver server."""

from typing import Any, Callable, Awaitable
import json
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from datetime import datetime
from uuid import uuid4

from magenta.webhooks import sentinel, splunk, generic


class WebhookServer:
    """Manages webhook receivers for external SIEM/SOAR integrations."""

    def __init__(self):
        self._handlers: dict[str, Callable] = {
            "sentinel": sentinel.handle_incident,
            "splunk": splunk.handle_alert,
            "generic": generic.handle_webhook,
        }

    def register_routes(self, app: FastAPI) -> None:
        @app.post("/webhooks/{source}")
        async def receive_webhook(source: str, request: Request):
            handler = self._handlers.get(source)
            if not handler:
                raise HTTPException(status_code=404, detail=f"Unknown webhook source: {source}")

            body = await request.json()
            result = await handler(body)
            return {"status": "received", "source": source, **result}

        @app.get("/webhooks/{source}/health")
        async def webhook_health(source: str):
            return {"source": source, "status": "healthy", "active": source in self._handlers}

    def register_handler(self, name: str, handler: Callable) -> None:
        self._handlers[name] = handler


webhook_server = WebhookServer()
