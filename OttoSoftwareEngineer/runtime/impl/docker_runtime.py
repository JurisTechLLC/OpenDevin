"""Docker-based runtime for OttoSoftwareEngineer.

Provides a fully isolated sandbox using Docker containers, mirroring
the Devin.ai architecture where each session runs in its own VM/container
with shell, browser, and code editor.

The DockerRuntime:
- Creates and manages Docker containers for agent execution
- Exposes shell, browser, and file system tools
- Handles port allocation for services (VS Code, browser, etc.)
- Manages container lifecycle (create, start, stop, destroy)
"""

from __future__ import annotations

import logging
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
    ErrorObservation,
    FileEditObservation,
    FileReadObservation,
    FileWriteObservation,
    Observation,
)
from OttoSoftwareEngineer.core.events.stream import EventStream
from OttoSoftwareEngineer.runtime.base import Runtime, RuntimeStatus

logger = logging.getLogger(__name__)


class DockerRuntime(Runtime):
    """Docker container-based sandboxed runtime.

    Each session gets its own Docker container providing:
    - Isolated filesystem with mounted workspace
    - Bash shell for command execution
    - Network access for package installation and web browsing
    - Port forwarding for web services
    - Resource limits (CPU, memory)

    This mirrors the Devin.ai production architecture where each
    session runs in an isolated virtual machine.

    Attributes:
        container_id: Docker container ID once started.
        container_image: Docker image to use for the sandbox.
    """

    container_id: str | None
    container_image: str

    def __init__(
        self,
        config: OttoConfig,
        event_stream: EventStream,
        sid: str = "default",
        status_callback: Callable[..., Any] | None = None,
    ) -> None:
        """Initialize the DockerRuntime.

        Args:
            config: System configuration.
            event_stream: Event bus for communication.
            sid: Session identifier.
            status_callback: Optional callback for status changes.
        """
        super().__init__(config, event_stream, sid, status_callback)
        self.container_id = None
        self.container_image = config.sandbox.container_image
        self._port_mappings: dict[int, int] = {}

    def connect(self) -> None:
        """Create and start the Docker container.

        Sets up the container with:
        - Workspace volume mount
        - Resource limits
        - Port mappings for services
        - Network configuration
        """
        logger.info(
            "[DockerRuntime %s] Creating container from image: %s",
            self.sid,
            self.container_image,
        )

        # Build docker run command
        cmd = [
            "docker",
            "create",
            "--name",
            f"otto-sandbox-{self.sid}",
            "-v",
            f"{self.config.workspace_base}:{self.config.sandbox.workspace_dir}",
            "--memory",
            self.config.sandbox.max_memory,
            "--cpus",
            str(self.config.sandbox.max_cpus),
        ]

        if self.config.sandbox.use_host_network:
            cmd.extend(["--network", "host"])

        cmd.append(self.container_image)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                self.container_id = result.stdout.strip()
                logger.info(
                    "[DockerRuntime %s] Container created: %s",
                    self.sid,
                    self.container_id[:12],
                )
            else:
                logger.error(
                    "[DockerRuntime %s] Failed to create container: %s",
                    self.sid,
                    result.stderr,
                )
                self.set_status(RuntimeStatus.ERROR, result.stderr)
                return

            # Start the container
            subprocess.run(
                ["docker", "start", self.container_id],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.set_status(RuntimeStatus.READY)

        except subprocess.TimeoutExpired:
            logger.error(
                "[DockerRuntime %s] Timeout creating container", self.sid
            )
            self.set_status(RuntimeStatus.ERROR, "Container creation timed out")
        except FileNotFoundError:
            logger.error(
                "[DockerRuntime %s] Docker not found on system", self.sid
            )
            self.set_status(RuntimeStatus.ERROR, "Docker not installed")

    def close(self) -> None:
        """Stop and remove the Docker container."""
        if self.container_id:
            logger.info(
                "[DockerRuntime %s] Stopping container: %s",
                self.sid,
                self.container_id[:12],
            )
            try:
                subprocess.run(
                    ["docker", "stop", self.container_id],
                    capture_output=True,
                    timeout=30,
                )
                subprocess.run(
                    ["docker", "rm", self.container_id],
                    capture_output=True,
                    timeout=30,
                )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                logger.warning(
                    "[DockerRuntime %s] Error cleaning up container",
                    self.sid,
                )
        super().close()

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def run(self, action: CmdRunAction) -> CmdOutputObservation:
        """Execute a shell command inside the Docker container.

        Args:
            action: The command to run.

        Returns:
            Command output and exit code.
        """
        if not self.container_id:
            return CmdOutputObservation(
                content="Error: Container not running",
                command=action.command,
                exit_code=1,
            )

        try:
            timeout = action.timeout or self.config.sandbox.timeout
            result = subprocess.run(
                ["docker", "exec", self.container_id, "bash", "-c", action.command],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return CmdOutputObservation(
                content=result.stdout + result.stderr,
                command=action.command,
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return CmdOutputObservation(
                content=f"Command timed out after {action.timeout}s",
                command=action.command,
                exit_code=124,
            )

    def read(self, action: FileReadAction) -> FileReadObservation:
        """Read a file from the container's filesystem.

        Args:
            action: The file read request.

        Returns:
            The file contents.
        """
        cmd = CmdRunAction(command=f"cat {action.path!r}")
        result = self.run(cmd)
        if result.exit_code != 0:
            return FileReadObservation(
                content=f"Error reading file: {result.content}",
                path=action.path,
            )
        return FileReadObservation(content=result.content, path=action.path)

    def write(self, action: FileWriteAction) -> FileWriteObservation:
        """Write content to a file in the container.

        Args:
            action: The file write request.

        Returns:
            Confirmation of the write.
        """
        # Use heredoc for writing content
        escaped_content = action.content.replace("'", "'\\''")
        cmd = CmdRunAction(
            command=f"mkdir -p $(dirname {action.path!r}) && "
            f"printf '%s' '{escaped_content}' > {action.path!r}"
        )
        result = self.run(cmd)
        if result.exit_code != 0:
            return FileWriteObservation(
                content=f"Error writing file: {result.content}",
                path=action.path,
            )
        return FileWriteObservation(
            content=f"File written: {action.path}", path=action.path
        )

    def edit(self, action: FileEditAction) -> FileEditObservation:
        """Apply an edit to a file in the container.

        Args:
            action: The file edit request.

        Returns:
            Result of the edit operation.
        """
        # Read current file
        read_result = self.read(FileReadAction(path=action.path))
        if "Error" in read_result.content:
            return FileEditObservation(
                content=read_result.content, path=action.path
            )

        # Apply edit
        new_content = read_result.content.replace(
            action.old_text, action.new_text
        )
        write_result = self.write(
            FileWriteAction(path=action.path, content=new_content)
        )
        return FileEditObservation(
            content=write_result.content, path=action.path
        )

    def browse(self, action: BrowseURLAction) -> BrowserObservation:
        """Navigate to a URL (placeholder - requires browser setup).

        Args:
            action: The browse request.

        Returns:
            Page content and metadata.
        """
        return BrowserObservation(
            content="Browser navigation requires Playwright setup",
            url=action.url,
        )

    def browse_interactive(
        self, action: BrowseInteractiveAction
    ) -> BrowserObservation:
        """Perform interactive browser action (placeholder).

        Args:
            action: The interactive action request.

        Returns:
            Updated page content.
        """
        return BrowserObservation(
            content="Interactive browsing requires Playwright setup",
        )

    def run_ipython(self, action: IPythonRunCellAction) -> Observation:
        """Execute Python code via IPython in the container.

        Args:
            action: The code to execute.

        Returns:
            Execution output.
        """
        cmd = CmdRunAction(command=f"python3 -c {action.code!r}")
        return self.run(cmd)
