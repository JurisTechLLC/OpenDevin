"""Sandbox configuration for OttoSoftwareEngineer.

Defines settings for the sandboxed execution environment where
the agent runs code, browses the web, and edits files.

Mirrors Devin.ai's isolated VM architecture where each session
gets its own container with shell, browser, and editor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SandboxConfig:
    """Configuration for the sandbox execution environment.

    Each Otto session runs in an isolated sandbox (Docker container
    or Kubernetes pod) with its own filesystem, network, and tools.

    Attributes:
        runtime_type: Type of sandbox ('docker', 'kubernetes', 'local').
        container_image: Docker image for the sandbox container.
        workspace_dir: Directory mounted as the agent's workspace.
        timeout: Default command execution timeout in seconds.
        enable_auto_lint: Auto-lint files after edits.
        use_host_network: Whether the container shares host networking.
        max_memory: Maximum memory for the container (e.g., '4g').
        max_cpus: Maximum CPUs for the container.
        browsing_enabled: Whether the browser tool is available.
        jupyter_enabled: Whether the IPython/Jupyter tool is available.
        vscode_enabled: Whether VS Code server is available.
        port_range_start: Start of the port range for services.
        port_range_end: End of the port range for services.
        runtime_startup_env_vars: Env vars to set at container start.
    """

    runtime_type: str = "docker"
    container_image: str = "otto-sandbox:latest"
    workspace_dir: str = "/workspace"
    timeout: int = 120
    enable_auto_lint: bool = True
    use_host_network: bool = False
    max_memory: str = "4g"
    max_cpus: float = 2.0
    browsing_enabled: bool = True
    jupyter_enabled: bool = True
    vscode_enabled: bool = False
    port_range_start: int = 30000
    port_range_end: int = 39999
    runtime_startup_env_vars: dict[str, str] = field(default_factory=dict)

    @property
    def workspace_path(self) -> Path:
        """Return the workspace directory as a Path object."""
        return Path(self.workspace_dir)
