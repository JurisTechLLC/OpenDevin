"""Observation classes for OttoSoftwareEngineer.

Observations represent feedback from the execution environment in response
to actions. They provide the agent with information about the current state
of the world after an action is executed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from OttoSoftwareEngineer.core.events.event import Event
from OttoSoftwareEngineer.core.schema.observation import ObservationType


@dataclass
class Observation(Event):
    """Base class for all observations from the execution environment.

    Attributes:
        observation_type: Discriminator for the specific observation kind.
        content: The primary content/output of the observation.
    """

    observation_type: ObservationType = field(default=ObservationType.NULL)
    content: str = ""


# ---------------------------------------------------------------------------
# Shell / Terminal Observations
# ---------------------------------------------------------------------------


@dataclass
class CmdOutputObservation(Observation):
    """Output from a shell command execution.

    Attributes:
        command: The command that was executed.
        exit_code: The process exit code (0 = success).
        command_id: Unique identifier for the command execution.
    """

    command: str = ""
    exit_code: int = 0
    command_id: int = -1
    observation_type: ObservationType = field(
        default=ObservationType.CMD_OUTPUT, init=False
    )


@dataclass
class IPythonOutputObservation(Observation):
    """Output from an IPython/Jupyter cell execution."""

    observation_type: ObservationType = field(
        default=ObservationType.IPYTHON_OUTPUT, init=False
    )


# ---------------------------------------------------------------------------
# File Observations
# ---------------------------------------------------------------------------


@dataclass
class FileReadObservation(Observation):
    """Contents of a file that was read.

    Attributes:
        path: Path to the file that was read.
    """

    path: str = ""
    observation_type: ObservationType = field(
        default=ObservationType.FILE_READ, init=False
    )


@dataclass
class FileWriteObservation(Observation):
    """Confirmation that a file was written.

    Attributes:
        path: Path to the file that was written.
    """

    path: str = ""
    observation_type: ObservationType = field(
        default=ObservationType.FILE_WRITE, init=False
    )


@dataclass
class FileEditObservation(Observation):
    """Result of a file edit operation.

    Attributes:
        path: Path to the file that was edited.
    """

    path: str = ""
    observation_type: ObservationType = field(
        default=ObservationType.FILE_EDIT, init=False
    )


# ---------------------------------------------------------------------------
# Browser Observations
# ---------------------------------------------------------------------------


@dataclass
class BrowserObservation(Observation):
    """Output from a browser interaction.

    Includes page content, screenshots, and DOM information
    from the sandbox browser (similar to Devin.ai's browser tool).

    Attributes:
        url: Current URL of the browser.
        screenshot_base64: Base64-encoded screenshot of the page.
        dom_content: Simplified DOM representation for the agent.
        page_title: Title of the current page.
    """

    url: str = ""
    screenshot_base64: str = ""
    dom_content: str = ""
    page_title: str = ""
    observation_type: ObservationType = field(
        default=ObservationType.BROWSER, init=False
    )


# ---------------------------------------------------------------------------
# Agent Lifecycle Observations
# ---------------------------------------------------------------------------


@dataclass
class AgentStateChangedObservation(Observation):
    """Notification that the agent's state has changed.

    Attributes:
        new_state: The new agent state after the transition.
    """

    new_state: str = ""
    observation_type: ObservationType = field(
        default=ObservationType.AGENT_STATE_CHANGED, init=False
    )


@dataclass
class AgentDelegateObservation(Observation):
    """Result returned from a delegated sub-agent.

    Attributes:
        outputs: Dictionary of outputs from the delegate agent.
    """

    outputs: dict[str, Any] = field(default_factory=dict)
    observation_type: ObservationType = field(
        default=ObservationType.AGENT_DELEGATE, init=False
    )


@dataclass
class AgentThinkObservation(Observation):
    """Acknowledgement of the agent's reasoning step."""

    observation_type: ObservationType = field(
        default=ObservationType.AGENT_THINK, init=False
    )


# ---------------------------------------------------------------------------
# Planning Observations
# ---------------------------------------------------------------------------


@dataclass
class PlanObservation(Observation):
    """Result of a planning operation.

    Attributes:
        plan: The structured plan with steps.
    """

    plan: list[dict[str, Any]] = field(default_factory=list)
    observation_type: ObservationType = field(
        default=ObservationType.PLAN, init=False
    )


# ---------------------------------------------------------------------------
# MCP Observations
# ---------------------------------------------------------------------------


@dataclass
class MCPResponseObservation(Observation):
    """Response from an MCP tool server.

    Attributes:
        server_name: Name of the MCP server that responded.
        tool_name: Name of the tool that was called.
        result: The tool's response data.
    """

    server_name: str = ""
    tool_name: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    observation_type: ObservationType = field(
        default=ObservationType.MCP_RESPONSE, init=False
    )


# ---------------------------------------------------------------------------
# Error / Control Observations
# ---------------------------------------------------------------------------


@dataclass
class ErrorObservation(Observation):
    """An error that occurred during action execution.

    Attributes:
        error_id: Machine-readable error identifier.
    """

    error_id: str = ""
    observation_type: ObservationType = field(
        default=ObservationType.ERROR, init=False
    )


@dataclass
class NullObservation(Observation):
    """A no-op observation used for internal signaling."""

    observation_type: ObservationType = field(
        default=ObservationType.NULL, init=False
    )


@dataclass
class UserRejectObservation(Observation):
    """The user rejected a pending action."""

    observation_type: ObservationType = field(
        default=ObservationType.USER_REJECT, init=False
    )


@dataclass
class LoopDetectionObservation(Observation):
    """The system detected the agent is stuck in a loop."""

    observation_type: ObservationType = field(
        default=ObservationType.LOOP_DETECTION, init=False
    )
