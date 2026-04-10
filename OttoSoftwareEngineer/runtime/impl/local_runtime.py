"""Local runtime for OttoSoftwareEngineer.

Provides a non-containerized runtime for local development and testing.
Executes commands directly on the host machine in a designated workspace
directory. NOT suitable for production use.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from OttoSoftwareEngineer.config.otto_config import OttoConfig
from OttoSoftwareEngineer.core.events.actions import (
    BrowseInteractiveAction,
    BrowseURLAction,
    CmdRunAction,
    FileEditAction,
    FileReadAction,
    FileWriteAction,
    IPythonRunCellAction,
)
from OttoSoftwareEngineer.core.events.observations import (
    BrowserObservation,
    CmdOutputObservation,
    FileEditObservation,
    FileReadObservation,
    FileWriteObservation,
    Observation,
)
from OttoSoftwareEngineer.core.events.stream import EventStream
from OttoSoftwareEngineer.runtime.base import Runtime, RuntimeStatus

logger = logging.getLogger(__name__)


class LocalRuntime(Runtime):
    """Local process-based runtime for development and testing.

    Executes commands directly on the host machine without
    container isolation. Useful for development and debugging
    the Otto system itself.

    WARNING: This runtime has no sandboxing. Do not use with
    untrusted agents in production.

    Attributes:
        workspace_dir: Local directory used as the workspace.
    """

    workspace_dir: Path

    def __init__(
        self,
        config: OttoConfig,
        event_stream: EventStream,
        sid: str = "default",
        status_callback: Callable[..., Any] | None = None,
    ) -> None:
        """Initialize the LocalRuntime.

        Args:
            config: System configuration.
            event_stream: Event bus for communication.
            sid: Session identifier.
            status_callback: Optional callback for status changes.
        """
        super().__init__(config, event_stream, sid, status_callback)
        self.workspace_dir = Path(config.sandbox.workspace_dir)

    def connect(self) -> None:
        """Set up the local workspace directory."""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "[LocalRuntime %s] Workspace ready at: %s",
            self.sid,
            self.workspace_dir,
        )
        self.set_status(RuntimeStatus.READY)

    def run(self, action: CmdRunAction) -> CmdOutputObservation:
        """Execute a shell command locally.

        Args:
            action: The command to run.

        Returns:
            Command output and exit code.
        """
        try:
            timeout = action.timeout or self.config.sandbox.timeout
            result = subprocess.run(
                ["bash", "-c", action.command],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace_dir),
            )
            return CmdOutputObservation(
                content=result.stdout + result.stderr,
                command=action.command,
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return CmdOutputObservation(
                content=f"Command timed out after {timeout}s",
                command=action.command,
                exit_code=124,
            )
        except Exception as e:
            return CmdOutputObservation(
                content=f"Error executing command: {str(e)}",
                command=action.command,
                exit_code=1,
            )

    def read(self, action: FileReadAction) -> FileReadObservation:
        """Read a file from the local filesystem.

        Args:
            action: The file read request.

        Returns:
            The file contents.
        """
        try:
            file_path = self._resolve_path(action.path)
            content = file_path.read_text()

            # Apply line range if specified
            if action.start > 0 or action.end > 0:
                lines = content.splitlines(keepends=True)
                start = max(0, action.start)
                end = action.end if action.end > 0 else len(lines)
                content = "".join(lines[start:end])

            return FileReadObservation(content=content, path=action.path)
        except FileNotFoundError:
            return FileReadObservation(
                content=f"File not found: {action.path}", path=action.path
            )
        except Exception as e:
            return FileReadObservation(
                content=f"Error reading file: {str(e)}", path=action.path
            )

    def write(self, action: FileWriteAction) -> FileWriteObservation:
        """Write content to a local file.

        Args:
            action: The file write request.

        Returns:
            Confirmation of the write.
        """
        try:
            file_path = self._resolve_path(action.path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(action.content)
            return FileWriteObservation(
                content=f"File written: {action.path}", path=action.path
            )
        except Exception as e:
            return FileWriteObservation(
                content=f"Error writing file: {str(e)}", path=action.path
            )

    def edit(self, action: FileEditAction) -> FileEditObservation:
        """Apply an edit to a local file.

        Args:
            action: The file edit request.

        Returns:
            Result of the edit operation.
        """
        try:
            file_path = self._resolve_path(action.path)
            content = file_path.read_text()
            new_content = content.replace(action.old_text, action.new_text)
            file_path.write_text(new_content)
            return FileEditObservation(
                content=f"File edited: {action.path}", path=action.path
            )
        except FileNotFoundError:
            return FileEditObservation(
                content=f"File not found: {action.path}", path=action.path
            )
        except Exception as e:
            return FileEditObservation(
                content=f"Error editing file: {str(e)}", path=action.path
            )

    def browse(self, action: BrowseURLAction) -> BrowserObservation:
        """Navigate to a URL (stub for local runtime).

        Args:
            action: The browse request.

        Returns:
            Page content (placeholder).
        """
        return BrowserObservation(
            content="Local runtime browser not configured",
            url=action.url,
        )

    def browse_interactive(
        self, action: BrowseInteractiveAction
    ) -> BrowserObservation:
        """Perform interactive browser action (stub).

        Args:
            action: The interactive action request.

        Returns:
            Placeholder observation.
        """
        return BrowserObservation(
            content="Local runtime browser not configured",
        )

    def run_ipython(self, action: IPythonRunCellAction) -> Observation:
        """Execute Python code locally.

        Args:
            action: The code to execute.

        Returns:
            Execution output.
        """
        cmd = CmdRunAction(command=f"python3 -c {action.code!r}")
        return self.run(cmd)

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to the workspace.

        Args:
            path: The path to resolve.

        Returns:
            Absolute path within the workspace.
        """
        p = Path(path)
        if p.is_absolute():
            return p
        return self.workspace_dir / p
