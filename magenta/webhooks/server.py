"""Webhook receiver server."""

from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Request

from magenta.webhooks import generic, sentinel, splunk


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
