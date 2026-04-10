"""Base event class for OttoSoftwareEngineer.

All events flowing through the system inherit from Event, which provides
common metadata: unique ID, timestamp, source attribution, and causality.
This mirrors the Devin.ai event stream architecture where every agent action
and environment observation is tracked as an immutable event.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventSource(str, Enum):
    """Origin of an event in the system.

    Tracks whether an event was initiated by a human user, the AI agent,
    the system infrastructure, or the execution environment.
    """

    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    ENVIRONMENT = "environment"


@dataclass
class Event:
    """Base class for all events in the OttoSoftwareEngineer system.

    Every action taken by the agent and every observation returned by the
    environment is represented as an Event. Events are immutable once added
    to the EventStream and form a complete audit trail of the session.

    Attributes:
        id: Unique monotonically increasing identifier assigned by EventStream.
        timestamp: ISO-8601 timestamp of when the event was created.
        source: Origin of the event (user, agent, system, environment).
        cause: ID of the event that caused this event (for linking
            actions to their resulting observations).
        hidden: Whether this event should be hidden from the frontend.
        tool_call_metadata: Optional metadata for tool call tracking.
    """

    INVALID_ID: int = -1

    _id: int = field(default=INVALID_ID, init=False, repr=False)
    _timestamp: str = field(default="", init=False, repr=False)
    _source: EventSource | None = field(default=None, init=False, repr=False)
    _cause: int | None = field(default=None, init=False, repr=False)
    hidden: bool = field(default=False)
    tool_call_metadata: dict[str, Any] | None = field(default=None)

    @property
    def id(self) -> int:
        """Unique event identifier, assigned by the EventStream."""
        return self._id

    @property
    def timestamp(self) -> str:
        """ISO-8601 timestamp of event creation."""
        return self._timestamp

    @property
    def source(self) -> EventSource | None:
        """Origin of this event."""
        return self._source

    @property
    def cause(self) -> int | None:
        """ID of the causing event, if any."""
        return self._cause

    def set_timestamp(self) -> None:
        """Set the timestamp to the current time."""
        self._timestamp = datetime.now().isoformat()
