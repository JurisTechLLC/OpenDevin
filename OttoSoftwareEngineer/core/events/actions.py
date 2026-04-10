"""Action classes for OttoSoftwareEngineer.

Actions represent commands issued by the user or agent that produce
side effects in the execution environment. Each action type maps to a
specific tool in the Devin.ai-style sandbox: shell, editor, browser, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from OttoSoftwareEngineer.core.events.event import Event
from OttoSoftwareEngineer.core.schema.action import ActionType


class ActionConfirmationStatus(str, Enum):
    """Whether a user has confirmed or rejected a pending action."""

    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    PENDING = "pending"


class ActionSecurityRisk(str, Enum):
    """Security risk level assessed for an action."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


@dataclass
class Action(Event):
    """Base class for all agent/user actions.

    Attributes:
        action_type: Discriminator for the specific action kind.
        timeout: Maximum seconds to wait for execution.
        confirmation_status: Whether the user has approved this action.
        security_risk: Assessed risk level of the action.
    """

    action_type: ActionType = field(default=ActionType.NULL)
    timeout: int | None = field(default=None)
    confirmation_status: ActionConfirmationStatus = field(
        default=ActionConfirmationStatus.CONFIRMED
    )
    security_risk: ActionSecurityRisk | None = field(default=None)

    def set_hard_timeout(self, timeout: int, blocking: bool = True) -> None:
        """Set the timeout for this action."""
        self.timeout = timeout


# ---------------------------------------------------------------------------
# Communication Actions
# ---------------------------------------------------------------------------


@dataclass
class MessageAction(Action):
    """A text message from the user or agent.

    This is the primary communication channel between the human user
    and the Otto agent, similar to the Devin.ai chat interface.
    """

    content: str = ""
    image_urls: list[str] = field(default_factory=list)
    action_type: ActionType = field(default=ActionType.MESSAGE, init=False)
    wait_for_response: bool = field(default=False)


@dataclass
class SystemMessageAction(Action):
    """A system-level message injected into the conversation."""

    content: str = ""
    action_type: ActionType = field(default=ActionType.SYSTEM_MESSAGE, init=False)


# ---------------------------------------------------------------------------
# Shell / Terminal Actions
# ---------------------------------------------------------------------------


@dataclass
class CmdRunAction(Action):
    """Execute a shell command in the sandbox terminal.

    Mirrors Devin.ai's shell tool - the primary way the agent interacts
    with the development environment (running builds, tests, git, etc.).
    """

    command: str = ""
    background: bool = False
    keep_prompt: bool = True
    action_type: ActionType = field(default=ActionType.CMD_RUN, init=False)


@dataclass
class IPythonRunCellAction(Action):
    """Execute Python code in an IPython/Jupyter kernel."""

    code: str = ""
    action_type: ActionType = field(default=ActionType.IPYTHON_RUN_CELL, init=False)


# ---------------------------------------------------------------------------
# File Operations (Code Editor)
# ---------------------------------------------------------------------------


@dataclass
class FileReadAction(Action):
    """Read the contents of a file in the workspace.

    Part of the code editor tool, allowing the agent to inspect files.
    """

    path: str = ""
    start: int = 0
    end: int = -1
    action_type: ActionType = field(default=ActionType.FILE_READ, init=False)


@dataclass
class FileWriteAction(Action):
    """Write content to a file, creating it if necessary."""

    path: str = ""
    content: str = ""
    action_type: ActionType = field(default=ActionType.FILE_WRITE, init=False)


@dataclass
class FileEditAction(Action):
    """Apply a targeted edit to an existing file.

    Supports find-and-replace style edits, similar to the Devin.ai
    code editor's inline editing capability.
    """

    path: str = ""
    old_text: str = ""
    new_text: str = ""
    action_type: ActionType = field(default=ActionType.FILE_EDIT, init=False)


# ---------------------------------------------------------------------------
# Browser Actions
# ---------------------------------------------------------------------------


@dataclass
class BrowseURLAction(Action):
    """Navigate to a URL in the sandbox browser.

    Mirrors Devin.ai's built-in browser tool for web research,
    documentation lookup, and testing web applications.
    """

    url: str = ""
    action_type: ActionType = field(default=ActionType.BROWSE_URL, init=False)


@dataclass
class BrowseInteractiveAction(Action):
    """Perform an interactive browser action (click, type, scroll, etc.).

    Enables the agent to interact with web pages through CDP,
    similar to Devin.ai's browser automation capabilities.
    """

    browser_actions: str = ""
    action_type: ActionType = field(
        default=ActionType.BROWSE_INTERACTIVE, init=False
    )


# ---------------------------------------------------------------------------
# Agent Lifecycle Actions
# ---------------------------------------------------------------------------


@dataclass
class AgentFinishAction(Action):
    """Signal that the agent has completed its task."""

    thought: str = ""
    outputs: dict[str, Any] = field(default_factory=dict)
    action_type: ActionType = field(default=ActionType.AGENT_FINISH, init=False)


@dataclass
class AgentRejectAction(Action):
    """Signal that the agent is rejecting the task."""

    thought: str = ""
    action_type: ActionType = field(default=ActionType.AGENT_REJECT, init=False)


@dataclass
class AgentDelegateAction(Action):
    """Delegate a sub-task to another agent instance.

    Mirrors Devin.ai's managed Devins feature - the ability to spawn
    child sessions that work on scoped sub-tasks in parallel.
    """

    agent: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    action_type: ActionType = field(default=ActionType.AGENT_DELEGATE, init=False)


@dataclass
class AgentThinkAction(Action):
    """Record the agent's reasoning/thought process."""

    thought: str = ""
    action_type: ActionType = field(default=ActionType.AGENT_THINK, init=False)


# ---------------------------------------------------------------------------
# Planning Actions (Devin 2.0 Interactive Planning)
# ---------------------------------------------------------------------------


@dataclass
class PlanCreateAction(Action):
    """Create an execution plan for the current task.

    Part of the Devin 2.0 interactive planning system where the agent
    proactively researches the codebase and develops a detailed plan
    that the user can review and modify before execution.
    """

    plan: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    action_type: ActionType = field(default=ActionType.PLAN_CREATE, init=False)


@dataclass
class PlanUpdateAction(Action):
    """Update an existing execution plan (mark steps complete, etc.)."""

    plan_updates: list[dict[str, Any]] = field(default_factory=list)
    action_type: ActionType = field(default=ActionType.PLAN_UPDATE, init=False)


# ---------------------------------------------------------------------------
# MCP Actions
# ---------------------------------------------------------------------------


@dataclass
class MCPAction(Action):
    """Call a tool on an MCP (Model Context Protocol) server.

    Mirrors Devin.ai's MCP integration for external tool servers
    like Slack, Linear, Datadog, etc.
    """

    server_name: str = ""
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    action_type: ActionType = field(default=ActionType.MCP_CALL, init=False)


# ---------------------------------------------------------------------------
# Control Actions
# ---------------------------------------------------------------------------


@dataclass
class NullAction(Action):
    """A no-op action used for internal signaling."""

    action_type: ActionType = field(default=ActionType.NULL, init=False)


@dataclass
class ChangeAgentStateAction(Action):
    """Request a change in the agent's lifecycle state."""

    target_state: str = ""
    action_type: ActionType = field(
        default=ActionType.CHANGE_AGENT_STATE, init=False
    )
