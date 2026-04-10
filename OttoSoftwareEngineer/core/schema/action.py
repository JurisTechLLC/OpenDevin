"""Action type definitions for OttoSoftwareEngineer.

Actions represent commands issued by the user or agent that produce
side effects in the execution environment.
"""

from enum import Enum


class ActionType(str, Enum):
    """Types of actions that can be executed in the Otto system.

    Mirrors Devin.ai's tool capabilities:
    - Shell commands (terminal)
    - File operations (code editor)
    - Browser interactions (web browsing)
    - Agent lifecycle actions (finish, delegate, plan)
    - Communication (messages)
    """

    # User/Agent communication
    MESSAGE = "message"
    SYSTEM_MESSAGE = "system_message"

    # Shell / Terminal
    CMD_RUN = "cmd_run"
    IPYTHON_RUN_CELL = "ipython_run_cell"

    # File operations (Code Editor)
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_EDIT = "file_edit"

    # Browser
    BROWSE_URL = "browse_url"
    BROWSE_INTERACTIVE = "browse_interactive"

    # Agent lifecycle
    AGENT_FINISH = "agent_finish"
    AGENT_REJECT = "agent_reject"
    AGENT_DELEGATE = "agent_delegate"
    AGENT_THINK = "agent_think"

    # Planning (Devin 2.0 interactive planning)
    PLAN_CREATE = "plan_create"
    PLAN_UPDATE = "plan_update"

    # Task tracking
    TASK_TRACKING = "task_tracking"

    # MCP tool calls
    MCP_CALL = "mcp_call"

    # Null/no-op
    NULL = "null"
    CHANGE_AGENT_STATE = "change_agent_state"
