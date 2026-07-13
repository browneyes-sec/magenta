"""Agent Ops MCP Server — gRPC service entrypoint.

Loads tool definitions from agent-ops-service.toml, registers all 14 handlers,
and exposes them via the MCP protocol on port 50060 (configurable).
"""

from __future__ import annotations

import json
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
import tomli
from pydantic import BaseModel, Field

from magenta.agent_ops.cloud import CloudOrchestrator
from magenta.agent_ops.config import ConfigAnalyzer
from magenta.agent_ops.finops import FinOpsEngine
from magenta.agent_ops.iac import IaCEngine

logger = structlog.get_logger(__name__)

CONFIG_DIR = Path(os.getenv("AGENT_OPS__CONFIG_DIR", "soa/config"))
TERRAFORM_DIR = Path(os.getenv("AGENT_OPS__TERRAFORM_DIR", "soa/terraform"))
SCHEMA_DIR = CONFIG_DIR / "schemas"


class ToolRequest(BaseModel):
    id: str = ""
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool: str
    success: bool
    output: Any = None
    error: str = ""
    duration_ms: float = 0.0


class AgentOpsServer:
    """MCP server for agent-ops service. Registers all 14 tools."""

    def __init__(self, config_path: str | Path = ""):
        self.config_path = Path(config_path) if config_path else CONFIG_DIR / "agents.toml"
        self.config = self._load_config()
        self.config_analyzer = ConfigAnalyzer(schema_dir=SCHEMA_DIR)
        self.iac_engine = IaCEngine(terraform_dir=TERRAFORM_DIR)
        self.cloud_orch = CloudOrchestrator(providers_path=CONFIG_DIR / "providers.toml")
        self.finops_engine = FinOpsEngine(config_dir=CONFIG_DIR)
        self.tools: dict[str, callable] = {}
        self._register_tools()

    def _load_config(self) -> dict:
        if self.config_path.exists():
            with open(self.config_path, "rb") as f:
                return tomli.load(f)
        return {}

    def _register_tools(self):
        """Map each tool name to its handler method."""
        self.tools = {
            # ── Configuration Analysis ──
            "config_analyze": self._handle_config_analyze,
            "config_validate": self._handle_config_validate,
            "config_diff": self._handle_config_diff,
            # ── IaC Management ──
            "iac_plan": self._handle_iac_plan,
            "iac_apply": self._handle_iac_apply,
            "iac_drift_detect": self._handle_iac_drift_detect,
            # ── Multi-Cloud Orchestration ──
            "cloud_provision": self._handle_cloud_provision,
            "cloud_discover_resources": self._handle_cloud_discover,
            "cloud_migrate": self._handle_cloud_migrate,
            # ── FinOps ──
            "finops_cost_analysis": self._handle_finops_cost,
            "finops_recommend_rightsize": self._handle_finops_rightsize,
            "finops_forecast": self._handle_finops_forecast,
            "finops_enforce_budget": self._handle_finops_budget,
            "finops_tag_compliance": self._handle_finops_tags,
        }

    def call_tool(self, tool: str, arguments: dict) -> ToolResult:
        start = datetime.utcnow()
        handler = self.tools.get(tool)
        if not handler:
            return ToolResult(tool=tool, success=False, error=f"Unknown tool: {tool}")
        try:
            result = handler(arguments)
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000
            return ToolResult(tool=tool, success=True, output=result, duration_ms=elapsed)
        except Exception as e:
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000
            logger.exception("Tool execution failed", tool=tool)
            return ToolResult(tool=tool, success=False, error=str(e), duration_ms=elapsed)

    def health(self) -> dict:
        return {
            "status": "healthy",
            "service": "mcp-agent-ops",
            "version": "1.0.0",
            "tools_available": len(self.tools),
            "tools": list(self.tools.keys()),
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ── Tool Handlers ──────────────────────────────────────────────────

    def _handle_config_analyze(self, args: dict) -> Any:
        return self.config_analyzer.analyze(
            path=args.get("path", "soa/config/"),
            fmt=args.get("format", "toml"),
            checks=args.get("checks", ["syntax", "schema"]),
        )

    def _handle_config_validate(self, args: dict) -> Any:
        return self.config_analyzer.validate(
            file_path=args.get("file", ""),
            schema_ref=args.get("schema_ref", ""),
        )

    def _handle_config_diff(self, args: dict) -> Any:
        return self.config_analyzer.diff(
            current=args.get("current_path", ""),
            target=args.get("target_path", ""),
            fmt=args.get("format", "unified"),
        )

    def _handle_iac_plan(self, args: dict) -> Any:
        return self.iac_engine.plan(
            environment=args.get("environment", "dev"),
            module_path=args.get("module_path", "terraform/"),
            variables=args.get("variables", {}),
        )

    def _handle_iac_apply(self, args: dict) -> Any:
        return self.iac_engine.apply(
            plan_ref=args.get("plan_ref", ""),
            auto_approve=args.get("auto_approve", False),
        )

    def _handle_iac_drift_detect(self, args: dict) -> Any:
        return self.iac_engine.detect_drift(
            environment=args.get("environment", "dev"),
        )

    def _handle_cloud_provision(self, args: dict) -> Any:
        return self.cloud_orch.provision(
            provider=args.get("provider", "azure"),
            resource_type=args.get("resource_type", "compute"),
            spec=args.get("spec", {}),
            region=args.get("region", "eastus2"),
        )

    def _handle_cloud_discover(self, args: dict) -> Any:
        return self.cloud_orch.discover(
            providers=args.get("providers", []),
            tags=args.get("tags", {}),
        )

    def _handle_cloud_migrate(self, args: dict) -> Any:
        return self.cloud_orch.plan_migration(
            source=args.get("source", {}),
            target=args.get("target", {}),
        )

    def _handle_finops_cost(self, args: dict) -> Any:
        return self.finops_engine.analyze_costs(
            period=args.get("period", "30d"),
            group_by=args.get("group_by", ["provider", "service"]),
        )

    def _handle_finops_rightsize(self, args: dict) -> Any:
        return self.finops_engine.recommend_rightsize(
            providers=args.get("providers", []),
            threshold=args.get("threshold", 0.2),
        )

    def _handle_finops_forecast(self, args: dict) -> Any:
        return self.finops_engine.forecast(
            horizon_days=args.get("horizon_days", 90),
            model=args.get("model", "prophet"),
        )

    def _handle_finops_budget(self, args: dict) -> Any:
        return self.finops_engine.enforce_budget(
            budget_id=args.get("budget_id", ""),
            action=args.get("action", "alert"),
        )

    def _handle_finops_tags(self, args: dict) -> Any:
        return self.finops_engine.audit_tags(
            required_tags=args.get(
                "required_tags",
                [
                    "environment",
                    "cost-center",
                    "owner",
                    "project",
                ],
            ),
        )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Agent Ops MCP Server")
    parser.add_argument("--config", default="soa/config/agents.toml")
    parser.add_argument("--port", type=int, default=50060)
    args = parser.parse_args()

    server = AgentOpsServer(config_path=args.config)
    logger.info("Agent Ops server started", port=args.port, tools=list(server.tools.keys()))

    def shutdown(sig, frame):
        logger.info("Shutting down")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Run health check on startup
    print(json.dumps(server.health(), indent=2))
    print(f"Listening on port {args.port}")
    signal.pause()


if __name__ == "__main__":
    main()
