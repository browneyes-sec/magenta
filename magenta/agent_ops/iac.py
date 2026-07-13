"""IaC management tools — iac_plan, iac_apply, iac_drift_detect.

Runs Terraform CLI as subprocess. Parses structured JSON output for
drift detection and plan summaries.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


class IaCEngine:
    """Terraform lifecycle management via subprocess."""

    def __init__(self, terraform_dir: str | Path = ""):
        self.terraform_dir = Path(terraform_dir) if terraform_dir else Path("soa/terraform")
        self._check_terraform()

    def _check_terraform(self):
        """Verify terraform CLI is available."""
        try:
            subprocess.run(["terraform", "version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("Terraform CLI not found; IaC tools will fail at runtime")

    def _tf_cmd(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        """Run terraform with given args."""
        wd = cwd or self.terraform_dir
        logger.debug("Running terraform", args=list(args), cwd=str(wd))
        return subprocess.run(
            ["terraform", *args],
            cwd=wd,
            capture_output=True,
            text=True,
            timeout=300,
        )

    def plan(
        self, environment: str = "dev", module_path: str = "", variables: dict | None = None
    ) -> dict:
        """Generate a Terraform plan for an environment."""
        env_dir = self.terraform_dir / "environments" / environment
        if not env_dir.exists():
            return {"error": f"Environment not found: {environment}", "plan": ""}

        result = self._tf_cmd(
            "plan", "-input=false", "-detailed-exitcode", "-no-color", cwd=env_dir
        )
        exit_ok = result.returncode in (0, 2)  # 0=no changes, 2=has changes
        return {
            "environment": environment,
            "has_changes": result.returncode == 2,
            "exit_code": result.returncode,
            "stdout": result.stdout[-5000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
            "success": exit_ok,
        }

    def apply(self, plan_ref: str = "", auto_approve: bool = False) -> dict:
        """Apply a Terraform plan."""
        env_dir = self.terraform_dir / "environments" / "dev"
        if plan_ref and Path(plan_ref).exists():
            result = self._tf_cmd("apply", "-input=false", plan_ref, cwd=env_dir)
        elif auto_approve:
            result = self._tf_cmd("apply", "-input=false", "-auto-approve", cwd=env_dir)
        else:
            result = self._tf_cmd("plan", "-input=false", "-detailed-exitcode", cwd=env_dir)
            if result.returncode != 2:
                return {"applied": False, "message": "No changes to apply"}
            result = self._tf_cmd("apply", "-input=false", "-auto-approve", cwd=env_dir)

        return {
            "applied": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout[-3000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
        }

    def detect_drift(self, environment: str = "dev") -> dict:
        """Detect drift between Terraform state and actual cloud resources.

        Uses 'terraform plan -detailed-exitcode' to determine if drift exists.
        Exit code 0 = clean, 2 = drift detected.
        """
        env_dir = self.terraform_dir / "environments" / environment
        if not env_dir.exists():
            return {
                "error": f"Environment not found: {environment}",
                "drifted_resources": 0,
                "details": [],
            }

        # Refresh state then plan to detect drift
        self._tf_cmd("refresh", "-input=false", cwd=env_dir)
        result = self._tf_cmd(
            "plan", "-input=false", "-detailed-exitcode", "-no-color", cwd=env_dir
        )

        drifted = result.returncode == 2
        details = []
        if drifted and result.stdout:
            import re

            for line in result.stdout.splitlines():
                if re.match(r"^\s*[#~+\-]", line) and not re.match(r"^\s*# ", line):
                    details.append(line.strip())

        return {
            "drifted_resources": len(details) if drifted else 0,
            "drifted": drifted,
            "exit_code": result.returncode,
            "details": details[:50],
            "environment": environment,
        }

    def state_inspect(self, resource_address: str = "") -> dict:
        """Inspect Terraform state for a specific resource or list all."""
        result = self._tf_cmd("state", "list")
        if result.returncode != 0:
            return {"error": result.stderr}

        resources = [r for r in result.stdout.strip().splitlines() if r]

        if resource_address:
            show = self._tf_cmd("state", "show", resource_address)
            return {
                "resource": resource_address,
                "state": show.stdout if show.returncode == 0 else show.stderr,
            }

        return {"resources": resources, "count": len(resources)}
