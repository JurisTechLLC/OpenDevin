"""Abstract base class for runtime environments in OttoSoftwareEngineer.

Defines the interface that all sandboxed execution environments must
implement. The runtime provides the agent with:
- Shell access (bash commands)
- File system operations (read, write, edit)
- Browser interaction (URL navigation, interactive actions)
- IPython/Jupyter execution
- Environment variable management
- Git operations

This mirrors the Devin.ai sandbox architecture where each session
gets a fully-featured isolated development environment.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from OttoSoftwareEngineer.config.otto_config import OttoConfig
from OttoSoftwareEngineer.core.events.actions import (
    Action,
    BrowseInteractiveAction,
    BrowseURLAction,
    CmdRunAction,
    FileEditAction,
    FileReadAction,
    FileWriteAction,
    IPythonRunCellAction,
    MCPAction,
)
from OttoSoftwareEngineer.core.events.event import Event, EventSource
from OttoSoftwareEngineer.core.events.observations import (
    BrowserObservation,
    CmdOutputObservation,
    ErrorObservation,
    FileEditObservation,
    FileReadObservation,
    FileWriteObservation,
    NullObservation,
    Observation,
)
from OttoSoftwareEngineer.core.events.stream import EventStream, EventStreamSubscriber

logger = logging.getLogger(__name__)


class RuntimeStatus(str, Enum):
    """Status of the sandbox runtime environment."""

    STARTING = "starting"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    ERROR_RUNTIME_DISCONNECTED = "error_runtime_disconnected"
    ERROR_LLM_AUTHENTICATION = "error_llm_authentication"
    ERROR_LLM_SERVICE_UNAVAILABLE = "error_llm_service_unavailable"
    ERROR_LLM_INTERNAL_SERVER_ERROR = "error_llm_internal_server_error"
    ERROR_LLM_OUT_OF_CREDITS = "error_llm_out_of_credits"
    ERROR_LLM_CONTENT_POLICY_VIOLATION = "error_llm_content_policy_violation"
    SETTING_UP_WORKSPACE = "setting_up_workspace"


class Runtime(ABC):
    """Abstract base class for agent runtime environments.

    The runtime is the sandbox in which the agent's actions are executed.
    It provides an isolated environment with shell, browser, file system,
    and other development tools.

    In the Devin.ai architecture, each session gets its own VM with:
    - A full Linux shell (bash)
    - A web browser (via CDP/Playwright)
    - A code editor (VS Code Server)
    - Git and other development tools
    - Network access for package installation

    Concrete implementations:
    - DockerRuntime: Docker container-based sandbox
    - LocalRuntime: Local process-based sandbox (for development)

    Attributes:
        sid: Session ID for this runtime.
        config: System configuration.
        event_stream: Event bus for communication.
        status: Current runtime status.
    """

    sid: str
    config: OttoConfig
    event_stream: EventStream
    status: RuntimeStatus

    def __init__(
        self,
        config: OttoConfig,
        event_stream: EventStream,
        sid: str = "default",
        status_callback: Callable[..., Any] | None = None,
    ) -> None:
        """Initialize the Runtime.

        Args:
            config: System configuration.
            event_stream: Event bus for communication.
            sid: Session identifier.
            status_callback: Optional callback for status changes.
        """
        self.sid = sid
        self.config = config
        self.event_stream = event_stream
        self.status = RuntimeStatus.STARTING
        self.status_callback = status_callback
        self._workspace_root = Path(config.sandbox.workspace_dir)

        # Subscribe to the event stream
        self.event_stream.subscribe(
            EventStreamSubscriber.RUNTIME, self.on_event, self.sid
        )

    def on_event(self, event: Event) -> None:
        """Handle incoming events from the EventStream.

        Routes action events to the appropriate handler method.

        Args:
            event: The incoming event.
        """
        if isinstance(event, Action):
            asyncio.get_event_loop().run_until_complete(
                self._handle_action(event)
            )

    async def _handle_action(self, action: Action) -> None:
        """Dispatch an action to the appropriate runtime method.

        Executes the action and publishes the resulting observation
        back to the event stream.

        Args:
            action: The action to execute.
        """
        try:
            observation = self.run_action(action)
        except Exception as e:
            logger.error(
                "[Runtime %s] Error executing action: %s", self.sid, str(e)
            )
            observation = ErrorObservation(content=str(e))

        if isinstance(observation, NullObservation):
            return

        observation._cause = action.id
        source = action.source if action.source else EventSource.AGENT
        self.event_stream.add_event(observation, source)

    def run_action(self, action: Action) -> Observation:
        """Execute an action and return the observation.

        Routes to the specific handler based on action type.

        Args:
            action: The action to execute.

        Returns:
            The resulting observation.
        """
        if isinstance(action, CmdRunAction):
            return self.run(action)
        elif isinstance(action, FileReadAction):
            return self.read(action)
        elif isinstance(action, FileWriteAction):
            return self.write(action)
        elif isinstance(action, FileEditAction):
            return self.edit(action)
        elif isinstance(action, BrowseURLAction):
            return self.browse(action)
        elif isinstance(action, BrowseInteractiveAction):
            return self.browse_interactive(action)
        elif isinstance(action, IPythonRunCellAction):
            return self.run_ipython(action)
        else:
            return NullObservation()

    # ------------------------------------------------------------------
    # Abstract methods - must be implemented by concrete runtimes
    # ------------------------------------------------------------------

    @abstractmethod
    def run(self, action: CmdRunAction) -> CmdOutputObservation:
        """Execute a shell command.

        Args:
            action: The command to run.

        Returns:
            The command output and exit code.
        """

    @abstractmethod
    def read(self, action: FileReadAction) -> FileReadObservation:
        """Read a file from the workspace.

        Args:
            action: The file read request.

        Returns:
            The file contents.
        """

    @abstractmethod
    def write(self, action: FileWriteAction) -> FileWriteObservation:
        """Write content to a file.

        Args:
            action: The file write request.

        Returns:
            Confirmation of the write.
        """

    @abstractmethod
    def edit(self, action: FileEditAction) -> FileEditObservation:
        """Apply an edit to a file.

        Args:
            action: The file edit request.

        Returns:
            Result of the edit operation.
        """

    @abstractmethod
    def browse(self, action: BrowseURLAction) -> BrowserObservation:
        """Navigate to a URL in the browser.

        Args:
            action: The browse request.

        Returns:
            Page content and metadata.
        """

    @abstractmethod
    def browse_interactive(
        self, action: BrowseInteractiveAction
    ) -> BrowserObservation:
        """Perform an interactive browser action.

        Args:
            action: The interactive action request.

        Returns:
            Updated page content and metadata.
        """

    @abstractmethod
    def run_ipython(
        self, action: IPythonRunCellAction
    ) -> Observation:
        """Execute code in an IPython kernel.

        Args:
            action: The code to execute.

        Returns:
            The execution output.
        """

    # ------------------------------------------------------------------
    # Common methods
    # ------------------------------------------------------------------

    @property
    def workspace_root(self) -> Path:
        """Root directory of the agent's workspace."""
        return self._workspace_root

    def setup_initial_env(self) -> None:
        """Set up the initial environment variables and workspace."""
        logger.info("[Runtime %s] Setting up initial environment", self.sid)
        self.status = RuntimeStatus.SETTING_UP_WORKSPACE

    def add_env_vars(self, env_vars: dict[str, str]) -> None:
        """Add environment variables to the sandbox.

        Args:
            env_vars: Dictionary of environment variable key-value pairs.
        """
        for key, value in env_vars.items():
            cmd = f"export {key.upper()}={value!r}"
            self.run(CmdRunAction(command=cmd))

    def set_status(self, status: RuntimeStatus, msg: str = "") -> None:
        """Update the runtime status.

        Args:
            status: The new status.
            msg: Optional status message.
        """
        self.status = status
        if self.status_callback:
            self.status_callback("info", status, msg)

    @abstractmethod
    def connect(self) -> None:
        """Connect to or start the sandbox environment."""

    def close(self) -> None:
        """Shut down the sandbox and clean up resources."""
        self.event_stream.unsubscribe(
            EventStreamSubscriber.RUNTIME, self.sid
        )
        self.status = RuntimeStatus.STOPPED

    def __enter__(self) -> Runtime:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
