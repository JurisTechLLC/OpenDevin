"""Observation type definitions for OttoSoftwareEngineer.

Observations represent feedback from the execution environment in response
to actions, providing the agent with information about the world.
"""

from enum import Enum


class ObservationType(str, Enum):
    """Types of observations returned from the execution environment.

    Each observation type corresponds to feedback from a specific tool
    or subsystem within the sandboxed environment.
    """

    # Shell output
    CMD_OUTPUT = "cmd_output"
    IPYTHON_OUTPUT = "ipython_output"

    # File observations
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_EDIT = "file_edit"

    # Browser observations
    BROWSER = "browser"

    # Agent lifecycle
    AGENT_STATE_CHANGED = "agent_state_changed"
    AGENT_DELEGATE = "agent_delegate"
    AGENT_THINK = "agent_think"

    # Planning observations
    PLAN = "plan"

    # Task tracking
    TASK_TRACKING = "task_tracking"

    # MCP
    MCP_RESPONSE = "mcp_response"

    # Errors
    ERROR = "error"

    # Null/no-op
    NULL = "null"

    # User rejection
    USER_REJECT = "user_reject"

    # Loop detection
    LOOP_DETECTION = "loop_detection"
