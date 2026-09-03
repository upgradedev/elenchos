"""Nebius Token Factory Sandboxes adapter for SandboxPort.

Executes canary validation and model-generated checks in isolated on-demand
environments via the contree-sdk.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


class SandboxError(RuntimeError):
    """Execution inside or connection to the sandbox failed."""


class ContreeSandboxAdapter:
    """Adapter for Nebius Token Factory Sandboxes using ContreeSync."""

    provider_name = "nebius_token_factory_sandboxes"

    def __init__(
        self,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        default_image: str = "python:3.12-slim",
    ) -> None:
        self.api_key = api_key or os.environ.get("NEBIUS_API_KEY", "")
        self.project_id = project_id or os.environ.get("NEBIUS_PROJECT_ID", "")
        self.default_image = default_image

    def run_command(
        self,
        image: Optional[str] = None,
        command: str = "python",
        args: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Execute a command inside an isolated Nebius Sandbox container."""
        img_name = image or self.default_image
        args = args or []

        try:
            from contree_sdk import ContreeSync
        except ImportError:
            # Fallback simulator when contree-sdk is not locally installed
            return self._simulate_run(img_name, command, args)

        if not self.api_key or not self.project_id:
            return self._simulate_run(img_name, command, args)

        try:
            client = ContreeSync(api_key=self.api_key, project_id=self.project_id)
            sandbox = client.images.use(img_name)
            result = sandbox.run(command, args=args).wait()
            return {
                "stdout": getattr(result, "stdout", ""),
                "stderr": getattr(result, "stderr", ""),
                "exit_code": getattr(result, "exit_code", 0),
                "image": img_name,
                "provider": self.provider_name,
            }
        except Exception as exc:
            raise SandboxError("Sandbox execution failed: %s" % exc) from exc

    def _simulate_run(self, image: str, command: str, args: List[str]) -> Dict[str, Any]:
        """Deterministic simulation for offline testing."""
        return {
            "stdout": "[sandbox simulation] ran %s with %r" % (command, args),
            "stderr": "",
            "exit_code": 0,
            "image": image,
            "provider": "%s_simulated" % self.provider_name,
        }
