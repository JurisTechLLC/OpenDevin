"""Event system for OttoSoftwareEngineer.

Provides the core event-driven communication infrastructure:
- Event base class with metadata tracking
- Action classes for agent/user commands
- Observation classes for environment feedback
- EventStream pub/sub bus for component communication
"""

from OttoSoftwareEngineer.core.events.event import Event, EventSource
from OttoSoftwareEngineer.core.events.stream import EventStream, EventStreamSubscriber
from OttoSoftwareEngineer.core.events.actions import (
    Action,
    MessageAction,
    CmdRunAction,
    FileReadAction,
    FileWriteAction,
    FileEditAction,
    BrowseURLAction,
    BrowseInteractiveAction,
    IPythonRunCellAction,
    AgentFinishAction,
    AgentRejectAction,
    AgentDelegateAction,
    AgentThinkAction,
    PlanCreateAction,
    PlanUpdateAction,
    NullAction,
    ChangeAgentStateAction,
    MCPAction,
)
from OttoSoftwareEngineer.core.events.observations import (
    Observation,
    CmdOutputObservation,
    FileReadObservation,
    FileWriteObservation,
    FileEditObservation,
    BrowserObservation,
    ErrorObservation,
    AgentStateChangedObservation,
    AgentDelegateObservation,
    AgentThinkObservation,
    PlanObservation,
    NullObservation,
    UserRejectObservation,
    MCPResponseObservation,
)

__all__ = [
    "Event",
    "EventSource",
    "EventStream",
    "EventStreamSubscriber",
    "Action",
    "MessageAction",
    "CmdRunAction",
    "FileReadAction",
    "FileWriteAction",
    "FileEditAction",
    "BrowseURLAction",
    "BrowseInteractiveAction",
    "IPythonRunCellAction",
    "AgentFinishAction",
    "AgentRejectAction",
    "AgentDelegateAction",
    "AgentThinkAction",
    "PlanCreateAction",
    "PlanUpdateAction",
    "NullAction",
    "ChangeAgentStateAction",
    "MCPAction",
    "Observation",
    "CmdOutputObservation",
    "FileReadObservation",
    "FileWriteObservation",
    "FileEditObservation",
    "BrowserObservation",
    "ErrorObservation",
    "AgentStateChangedObservation",
    "AgentDelegateObservation",
    "AgentThinkObservation",
    "PlanObservation",
    "NullObservation",
    "UserRejectObservation",
    "MCPResponseObservation",
]
