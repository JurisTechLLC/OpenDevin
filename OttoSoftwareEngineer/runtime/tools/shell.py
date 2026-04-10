"""Shell tool for OttoSoftwareEngineer.

Provides bash shell access within the sandbox, the primary tool
through which the agent interacts with the development environment.

Mirrors Devin.ai's terminal/shell tool that enables running
builds, tests, git commands, package installations, and more.
"""

from __future__ import annotations

import subprocess
from typing import Any

from OttoSoftwareEngineer.runtime.tools.base import Tool, ToolResult


class ShellTool(Tool):
    """Bash shell execution tool.

    The shell is the most frequently used tool, enabling the agent to:
    - Run build and test commands
    - Execute git operations
    - Install packages
    - Navigate the filesystem
    - Run arbitrary scripts

    Attributes:
        working_dir: Current working directory for commands.
        timeout: Default command timeout in seconds.
    """

    name = "shell"
    description = "Execute bash commands in the sandbox terminal"

    def __init__(
        self,
        working_dir: str = "/workspace",
        timeout: int = 120,
    ) -> None:
        """Initialize the ShellTool.

        Args:
            working_dir: Default working directory.
            timeout: Default command timeout.
        """
        self.working_dir = working_dir
        self.timeout = timeout
        self._env: dict[str, str] = {}

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a shell command.

        Args:
            **kwargs: Shell command parameters including:
                command: The bash command to execute.
                timeout: Optional override for command timeout.
                background: Whether to run in background.

        Returns:
            Command output and exit code.
        """
        command = kwargs.get("command", "")
        timeout = kwargs.get("timeout", self.timeout)
        if not command:
            return ToolResult(success=False, error="No command provided")

        try:
            result = subprocess.run(
                ["bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.working_dir,
                env=self._env if self._env else None,
            )
            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout + result.stderr,
                metadata={
                    "exit_code": result.returncode,
                    "command": command,
                },
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"Command timed out after {timeout}s",
                metadata={"command": command, "exit_code": 124},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"command": command},
            )

    def set_env(self, key: str, value: str) -> None:
        """Set an environment variable for future commands."""
        self._env[key] = value

    def get_schema(self) -> dict[str, Any]:
        """Get the JSON schema for shell tool parameters."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Command timeout in seconds",
                    },
                    "background": {
                        "type": "boolean",
                        "description": "Run command in background",
                    },
                },
                "required": ["command"],
            },
        }
