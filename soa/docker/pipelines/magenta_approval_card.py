"""
Magenta Approval Card — Interactive HTML approval gate for Open WebUI (HTTP client).

Generates an HTML artifact with Approve/Deny/Approve Alternative buttons
that POST to the Magenta API approvals endpoint.

Installation: place in Open WebUI pipelines directory, enable in Valves.
"""

import logging
from datetime import datetime
from typing import Optional

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

API_BASE = "http://magenta-api:8000"
TIMEOUT = 30.0


class Valves(BaseModel):
    enabled: bool = True
    priority: int = 5
    name: str = "Magenta Approval Card"
    description: str = "Interactive approval card for high-risk actions"
    pipelines: list = []


class Pipeline:
    """Approval Card pipeline — renders interactive approval HTML."""

    def __init__(self):
        self.id = "magenta_approval_card"
        self.name = "Magenta Approval Card"
        self.pipeline = "magenta_approval_card"
        self.valves = Valves()

    async def on_startup(self) -> None:
        logger.info("Magenta Approval Card pipeline started")

    async def on_shutdown(self) -> None:
        logger.info("Magenta Approval Card pipeline stopped")

    def pipe(self, body: dict, **kwargs) -> str:
        messages = body.get("messages", [])
        last_content = ""
        if messages:
            last = messages[-1]
            last_content = last.get("content", "") if isinstance(last, dict) else str(last)

        if "approval_card" in last_content.lower() or "approval" in last_content.lower():
            import asyncio
            return asyncio.run(self._generate_approval_card())

        return """Use `approval_card` to generate an interactive approval card.

Example:
```
approval_card
```"""

    async def _get(self, path: str):
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"{API_BASE}{path}")
            r.raise_for_status()
            return r.json()

    async def _post(self, path: str, params: dict = None):
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(f"{API_BASE}{path}", params=params)
            r.raise_for_status()
            return r.json()

    async def _generate_approval_card(self) -> str:
        """Generate an interactive HTML approval card."""
        try:
            response = await self._get("/api/v1/approvals/pending")
            pending = response.get("approvals", []) if isinstance(response, dict) else []
        except Exception as exc:
            pending = []
            logger.warning("Could not load pending approvals: %s", exc)

        if not pending:
            return self._card_html_empty()

        return self._card_html_pending(pending)

    def _card_html_empty(self) -> str:
        return """<div style="font-family:system-ui,-apple-system,sans-serif;max-width:600px;margin:0 auto">
    <div style="background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.1);padding:24px;text-align:center">
        <div style="font-size:48px;margin-bottom:12px">\u2705</div>
        <h2 style="margin:0 0 8px 0;font-size:20px;color:#333">No Pending Approvals</h2>
        <p style="margin:0;font-size:14px;color:#666">All actions have been reviewed. The queue is empty.</p>
        <div style="margin-top:16px;padding:12px;background:#f0fdf4;border-radius:8px;font-size:13px;color:#166534">
            Shadow mode: approvals are logged but not enforced
        </div>
    </div>
</div>"""

    def _card_html_pending(self, approvals: list[dict]) -> str:
        cards_html = ""
        for a in approvals:
            aid = a.get("id", "")
            action = a.get("action", "")
            target = a.get("target", "")
            risk = a.get("risk_score", 0)
            expires = a.get("expires_at", "")

            risk_color = "green" if risk < 40 else ("orange" if risk < 70 else "red")

            cards_html += f"""
            <div style="background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.1);padding:16px;margin-bottom:12px;border-left:4px solid {risk_color}">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                    <h3 style="margin:0;font-size:15px;color:#333">{action}</h3>
                    <span style="font-size:12px;padding:2px 8px;border-radius:4px;background:{risk_color};color:#fff;font-weight:600">Risk: {risk}</span>
                </div>
                <p style="margin:0 0 4px 0;font-size:13px;color:#666">Target: <strong>{target}</strong></p>
                <p style="margin:0 0 12px 0;font-size:12px;color:#999">ID: {aid[:8]}... | Expires: {expires[:19]}</p>
                <div style="display:flex;gap:8px">
                    <button onclick="fetch('/api/v1/approvals/{aid}/respond?decision=approved&approver_id=operator', {{method:'POST'}}).then(r=>r.json()).then(d=>alert('Approved: '+JSON.stringify(d)))"
                            style="padding:8px 20px;background:#166534;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600">\u2705 Approve</button>
                    <button onclick="fetch('/api/v1/approvals/{aid}/respond?decision=denied&approver_id=operator', {{method:'POST'}}).then(r=>r.json()).then(d=>alert('Denied: '+JSON.stringify(d)))"
                            style="padding:8px 20px;background:#991b1b;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600">\u274c Deny</button>
                    <button onclick="const r=prompt('Alternative action:');if(r)fetch('/api/v1/approvals/{aid}/respond?decision=denied&approver_id=operator&reason='+encodeURIComponent('Alternative: '+r),{{method:'POST'}}).then(d=>alert('Alternative logged: '+r))"
                            style="padding:8px 20px;background:#6b7280;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600">\u270f Alternative</button>
                </div>
            </div>"""

        return f"""<div style="font-family:system-ui,-apple-system,sans-serif;max-width:600px;margin:0 auto">
    <div style="background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.1);padding:24px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
            <h2 style="margin:0;font-size:18px;color:#333">Approval Gate</h2>
            <span style="font-size:12px;padding:4px 10px;border-radius:12px;background:#fef3c7;color:#92400e;font-weight:600">{len(approvals)} pending</span>
        </div>
        <p style="font-size:13px;color:#666;margin:0 0 16px 0">Review and respond to pending high-risk actions.</p>
        {cards_html}
        <div style="margin-top:16px;padding:12px;background:#f0fdf4;border-radius:8px;font-size:12px;color:#166534;text-align:center">
            Shadow mode: approval is logged, action proceeds regardless
        </div>
    </div>
</div>"""