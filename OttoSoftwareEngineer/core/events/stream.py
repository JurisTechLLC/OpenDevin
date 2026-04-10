"""EventStream - the central communication bus for OttoSoftwareEngineer.

The EventStream is the backbone of the system, implementing a pub/sub
pattern that connects all components. Every action and observation flows
through the EventStream, providing a complete audit trail and enabling
loose coupling between the agent controller, runtime, and server.

This mirrors Devin.ai's event-driven architecture where all agent actions
and environment observations are streamed in real-time.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from datetime import datetime
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventStreamSubscriber(str, Enum):
    """Identifies the type of subscriber listening to the EventStream.

    Different components subscribe to the stream to react to events:
    - AGENT_CONTROLLER: The main agent loop
    - SERVER: The web server (for streaming to frontend)
    - RUNTIME: The sandboxed execution environment
    - MAIN: The CLI/main entry point
    """

    AGENT_CONTROLLER = "agent_controller"
    SERVER = "server"
    RUNTIME = "runtime"
    MAIN = "main"
    TEST = "test"


class EventStream:
    """Central pub/sub event bus for the OttoSoftwareEngineer system.

    All communication between components flows through this stream.
    Events are assigned monotonically increasing IDs and persisted
    for session replay and audit.

    Architecture (mirrors Devin.ai):
    - Agent actions are published by the controller
    - Runtime observations are published by the sandbox
    - Server subscribes for real-time streaming to the frontend
    - All events are persisted for session history

    Attributes:
        sid: Session ID that this stream belongs to.
        cur_id: The next event ID to assign.
        secrets: Dictionary of secrets to redact from event content.
    """

    def __init__(self, sid: str) -> None:
        """Initialize the EventStream.

        Args:
            sid: Session identifier for this event stream.
        """
        from OttoSoftwareEngineer.core.events.event import Event

        self.sid = sid
        self.cur_id: int = 0
        self.secrets: dict[str, str] = {}

        self._subscribers: dict[str, dict[str, Callable[..., Any]]] = {}
        self._lock = threading.Lock()
        self._queue: queue.Queue[Event] = queue.Queue()
        self._events: list[dict[str, Any]] = []
        self._stop_flag = threading.Event()

        self._queue_thread = threading.Thread(
            target=self._run_queue_loop, daemon=True
        )
        self._queue_thread.start()

    def close(self) -> None:
        """Shut down the event stream and clean up resources."""
        self._stop_flag.set()
        if self._queue_thread.is_alive():
            self._queue_thread.join(timeout=5)

        subscriber_ids = list(self._subscribers.keys())
        for subscriber_id in subscriber_ids:
            callback_ids = list(self._subscribers[subscriber_id].keys())
            for callback_id in callback_ids:
                self._clean_up_subscriber(subscriber_id, callback_id)

        while not self._queue.empty():
            self._queue.get()

    def subscribe(
        self,
        subscriber_id: EventStreamSubscriber,
        callback: Callable[..., Any],
        callback_id: str,
    ) -> None:
        """Register a callback to receive events.

        Args:
            subscriber_id: Type of subscriber.
            callback: Function to call with each event.
            callback_id: Unique ID for this callback registration.

        Raises:
            ValueError: If callback_id is already registered.
        """
        with self._lock:
            if subscriber_id not in self._subscribers:
                self._subscribers[subscriber_id] = {}

            if callback_id in self._subscribers[subscriber_id]:
                raise ValueError(
                    f"Callback ID on subscriber {subscriber_id} "
                    f"already exists: {callback_id}"
                )

            self._subscribers[subscriber_id][callback_id] = callback

    def unsubscribe(
        self, subscriber_id: EventStreamSubscriber, callback_id: str
    ) -> None:
        """Remove a previously registered callback.

        Args:
            subscriber_id: Type of subscriber.
            callback_id: ID of the callback to remove.
        """
        with self._lock:
            if subscriber_id not in self._subscribers:
                logger.warning(
                    "Subscriber not found during unsubscribe: %s",
                    subscriber_id,
                )
                return
            if callback_id not in self._subscribers[subscriber_id]:
                logger.warning(
                    "Callback not found during unsubscribe: %s", callback_id
                )
                return
            self._clean_up_subscriber(subscriber_id, callback_id)

    def add_event(
        self,
        event: Any,
        source: Any,
    ) -> None:
        """Add a new event to the stream.

        Assigns a unique ID and timestamp, redacts secrets, persists the
        event, and enqueues it for subscriber notification.

        Args:
            event: The Event instance to add.
            source: The EventSource indicating who created this event.
        """
        from OttoSoftwareEngineer.core.events.event import Event

        if event.id != Event.INVALID_ID:
            raise ValueError(
                f"Event already has an ID: {event.id}. "
                "It was probably added back to the EventStream from "
                "inside a handler, triggering a loop."
            )

        event._timestamp = datetime.now().isoformat()
        event._source = source

        with self._lock:
            event._id = self.cur_id
            self.cur_id += 1

            event_data = self._event_to_dict(event)
            event_data = self._replace_secrets(event_data)
            self._events.append(event_data)

        self._queue.put(event)

    def get_events(
        self,
        start_id: int = 0,
        end_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve events from the stream by ID range.

        Args:
            start_id: First event ID to include (inclusive).
            end_id: Last event ID to include (exclusive). None for all.

        Returns:
            List of event dictionaries.
        """
        with self._lock:
            if end_id is None:
                return [e for e in self._events if e.get("id", 0) >= start_id]
            return [
                e
                for e in self._events
                if start_id <= e.get("id", 0) < end_id
            ]

    def set_secrets(self, secrets: dict[str, str]) -> None:
        """Set the secrets to redact from event content."""
        self.secrets = secrets.copy()

    def update_secrets(self, secrets: dict[str, str]) -> None:
        """Add additional secrets to redact."""
        self.secrets.update(secrets)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _replace_secrets(
        self, data: dict[str, Any], is_top_level: bool = True
    ) -> dict[str, Any]:
        """Recursively redact secret values from event data.

        Mirrors the Devin.ai approach of never exposing credentials
        in the event stream or session logs.
        """
        protected_fields = {
            "timestamp",
            "id",
            "source",
            "cause",
            "action_type",
            "observation_type",
        }

        for key in data:
            if is_top_level and key in protected_fields:
                continue
            elif isinstance(data[key], dict):
                data[key] = self._replace_secrets(
                    data[key], is_top_level=False
                )
            elif isinstance(data[key], str):
                for secret in self.secrets.values():
                    data[key] = data[key].replace(secret, "<secret_hidden>")
        return data

    def _event_to_dict(self, event: Any) -> dict[str, Any]:
        """Serialize an event to a dictionary for storage."""
        from dataclasses import asdict

        try:
            data = asdict(event)
        except TypeError:
            data = {"content": str(event)}

        data["id"] = event.id
        data["timestamp"] = event.timestamp
        data["source"] = event.source.value if event.source else None
        data["cause"] = event.cause
        return data

    def _clean_up_subscriber(
        self, subscriber_id: str, callback_id: str
    ) -> None:
        """Remove a subscriber callback and clean up resources."""
        if subscriber_id not in self._subscribers:
            return
        if callback_id not in self._subscribers[subscriber_id]:
            return
        del self._subscribers[subscriber_id][callback_id]

    def _run_queue_loop(self) -> None:
        """Background thread that processes the event queue."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._process_queue())
        finally:
            loop.close()

    async def _process_queue(self) -> None:
        """Dispatch queued events to all subscribers."""
        while not self._stop_flag.is_set():
            try:
                event = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            for key in sorted(self._subscribers.keys()):
                callbacks = self._subscribers[key]
                callback_ids = list(callbacks.keys())
                for callback_id in callback_ids:
                    if callback_id in callbacks:
                        callback = callbacks[callback_id]
                        try:
                            callback(event)
                        except Exception:
                            logger.exception(
                                "Error in event callback %s for "
                                "subscriber %s",
                                callback_id,
                                key,
                            )
