"""Agent state definitions for OttoSoftwareEngineer.

Mirrors the Devin.ai agent lifecycle states, from initialization through
planning, execution, and terminal states.
"""

from enum import Enum


class AgentState(str, Enum):
    """Represents the current state of an Otto agent session.

    States follow the Devin.ai lifecycle:
    INIT -> PLANNING -> RUNNING -> FINISHED/ERROR/STOPPED

    The agent can also transition to AWAITING_USER_INPUT at any point
    when human intervention is needed, or PAUSED when explicitly paused.
    """

    INIT = "init"
    PLANNING = "planning"
    RUNNING = "running"
    AWAITING_USER_INPUT = "awaiting_user_input"
    AWAITING_USER_CONFIRMATION = "awaiting_user_confirmation"
    PAUSED = "paused"
    RATE_LIMITED = "rate_limited"
    FINISHED = "finished"
    REJECTED = "rejected"
    ERROR = "error"
    STOPPED = "stopped"

    @classmethod
    def terminal_states(cls) -> set["AgentState"]:
        """Return the set of states from which no further transitions occur."""
        return {cls.FINISHED, cls.ERROR, cls.STOPPED, cls.REJECTED}

    @classmethod
    def running_states(cls) -> set["AgentState"]:
        """Return states where the agent is actively executing."""
        return {cls.PLANNING, cls.RUNNING}
