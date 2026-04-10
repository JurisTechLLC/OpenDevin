"""Agent session management for OttoSoftwareEngineer.

An AgentSession represents a single conversation/task between a user
and the Otto agent. It owns the agent controller, runtime, event stream,
and all associated resources.

Mirrors the Devin.ai session model where each task gets its own
isolated environment with a unique session ID.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Callable

from OttoSoftwareEngineer.config.otto_config import OttoConfig
from OttoSoftwareEngineer.controller.agent_controller import AgentController
from OttoSoftwareEngineer.controller.state import State
from OttoSoftwareEngineer.core.events.actions import MessageAction
from OttoSoftwareEngineer.core.events.event import EventSource
from OttoSoftwareEngineer.core.events.stream import EventStream, EventStreamSubscriber
from OttoSoftwareEngineer.core.schema.agent import AgentState

logger = logging.getLogger(__name__)


class AgentSession:
    """A single Otto agent session.

    Owns and coordinates all components for a conversation:
    - EventStream: Communication bus
    - AgentController: Agent orchestration
    - Runtime: Sandboxed execution environment

    Lifecycle:
    1. Created by SessionManager
    2. Initialized with config and agent
    3. User sends messages via send_message()
    4. Events stream to frontend via get_events()
    5. Session ends when agent finishes or user stops

    Attributes:
        sid: Unique session identifier.
        config: System configuration.
        event_stream: Communication bus for this session.
        controller: Agent controller managing execution.
        status: Current session status.
    """

    def __init__(
        self,
        sid: str | None = None,
        config: OttoConfig | None = None,
        status_callback: Callable[..., Any] | None = None,
    ) -> None:
        """Initialize an AgentSession.

        Args:
            sid: Session ID (auto-generated if not provided).
            config: System configuration.
            status_callback: Optional callback for status updates.
        """
        self.sid = sid or str(uuid.uuid4())
        self.config = config or OttoConfig()
        self.status_callback = status_callback
        self.event_stream = EventStream(self.sid)
        self.controller: AgentController | None = None
        self._runtime: Any = None
        self._is_running = False

    async def start(
        self,
        agent: Any,
        runtime: Any | None = None,
    ) -> None:
        """Start the session with an agent and runtime.

        Creates the agent controller and connects all components.

        Args:
            agent: The agent instance (BaseAgent).
            runtime: Optional runtime (creates default if not provided).
        """
        logger.info("[Session %s] Starting session", self.sid)

        self._runtime = runtime

        # Create agent controller
        self.controller = AgentController(
            agent=agent,
            event_stream=self.event_stream,
            max_iterations=self.config.agent.max_iterations,
            max_budget_per_task=self.config.agent.max_budget_per_task,
            sid=self.sid,
            confirmation_mode=self.config.agent.enable_confirmation_mode,
            headless_mode=True,
            status_callback=self.status_callback,
        )

        self._is_running = True
        logger.info("[Session %s] Session started", self.sid)

    async def send_message(self, content: str) -> None:
        """Send a user message to the agent.

        Args:
            content: The message text.
        """
        if not self._is_running:
            logger.warning(
                "[Session %s] Cannot send message - session not running",
                self.sid,
            )
            return

        action = MessageAction(content=content)
        self.event_stream.add_event(action, EventSource.USER)

        # If agent is waiting for input, resume
        if self.controller and self.controller.get_agent_state() in (
            AgentState.AWAITING_USER_INPUT,
            AgentState.INIT,
        ):
            await self.controller.set_agent_state_to(AgentState.RUNNING)

    def get_events(
        self, start_id: int = 0, end_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Get events from the session stream.

        Args:
            start_id: First event ID to include.
            end_id: Last event ID to include (exclusive).

        Returns:
            List of event dictionaries.
        """
        return self.event_stream.get_events(start_id, end_id)

    def get_state(self) -> dict[str, Any]:
        """Get the current session state.

        Returns:
            Dictionary with session state information.
        """
        state: dict[str, Any] = {
            "sid": self.sid,
            "is_running": self._is_running,
        }

        if self.controller:
            controller_state = self.controller.get_state()
            state.update(
                {
                    "agent_state": controller_state.agent_state.value,
                    "iteration": controller_state.iteration,
                    "plan": controller_state.get_plan_summary(),
                    "metrics": {
                        "total_cost": controller_state.metrics.total_cost,
                        "total_actions": controller_state.metrics.total_actions,
                        "total_llm_calls": controller_state.metrics.total_llm_calls,
                    },
                    "last_error": controller_state.last_error,
                }
            )

        return state

    async def stop(self) -> None:
        """Stop the session and clean up resources."""
        logger.info("[Session %s] Stopping session", self.sid)

        if self.controller:
            await self.controller.close()

        if self._runtime:
            self._runtime.close()

        self.event_stream.close()
        self._is_running = False

        logger.info("[Session %s] Session stopped", self.sid)

    @property
    def is_running(self) -> bool:
        """Whether the session is currently active."""
        return self._is_running
