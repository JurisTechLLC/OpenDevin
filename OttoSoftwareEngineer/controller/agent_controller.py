"""Agent Controller for OttoSoftwareEngineer.

The AgentController is the central orchestration engine that drives the
agent execution loop. It manages the state machine, coordinates between
the agent's intelligence (LLM) and the execution environment (runtime),
handles planning, stuck detection, and delegation.

This mirrors the Devin.ai agent controller architecture:
- Receives user tasks via the EventStream
- Enters planning phase (Devin 2.0 interactive planning)
- Executes the plan step-by-step via the agent loop
- Handles errors, stuck states, rate limiting, and budget limits
- Supports delegation to child agents (managed Devins)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Callable

from OttoSoftwareEngineer.controller.planner import Planner
from OttoSoftwareEngineer.controller.state import State
from OttoSoftwareEngineer.controller.stuck_detector import StuckDetector
from OttoSoftwareEngineer.core.events.actions import (
    Action,
    AgentDelegateAction,
    AgentFinishAction,
    AgentRejectAction,
    ChangeAgentStateAction,
    CmdRunAction,
    MessageAction,
    NullAction,
    PlanCreateAction,
    PlanUpdateAction,
)
from OttoSoftwareEngineer.core.events.event import Event, EventSource
from OttoSoftwareEngineer.core.events.observations import (
    AgentDelegateObservation,
    AgentStateChangedObservation,
    ErrorObservation,
    NullObservation,
    Observation,
)
from OttoSoftwareEngineer.core.events.stream import EventStream, EventStreamSubscriber
from OttoSoftwareEngineer.core.exceptions import (
    AgentStuckInLoopError,
    LLMContextWindowExceededError,
)
from OttoSoftwareEngineer.core.schema.agent import AgentState

if TYPE_CHECKING:
    from OttoSoftwareEngineer.agenthub.base_agent import BaseAgent
    from OttoSoftwareEngineer.config import AgentConfig, LLMConfig

logger = logging.getLogger(__name__)

TRAFFIC_CONTROL_REMINDER = (
    "Please click on resume button if you'd like to continue, "
    "or start a new task."
)


class AgentController:
    """Central orchestration engine for the Otto agent.

    Manages the complete lifecycle of an agent session:
    1. INIT: Session created, waiting for first user message
    2. PLANNING: Agent analyzes task and creates execution plan
    3. RUNNING: Agent executes plan steps via the execution loop
    4. Terminal: FINISHED, ERROR, STOPPED, or REJECTED

    The controller subscribes to the EventStream to receive events
    and publishes actions/observations back to it.

    Attributes:
        id: Unique session identifier.
        agent: The agent instance providing intelligence.
        event_stream: The event bus for communication.
        state: Current session state.
        confirmation_mode: Whether user confirmation is required.
    """

    id: str
    agent: BaseAgent
    event_stream: EventStream
    state: State
    confirmation_mode: bool
    delegate: AgentController | None
    parent: AgentController | None

    def __init__(
        self,
        agent: BaseAgent,
        event_stream: EventStream,
        max_iterations: int = 200,
        max_budget_per_task: float = 10.0,
        agent_to_llm_config: dict[str, LLMConfig] | None = None,
        agent_configs: dict[str, AgentConfig] | None = None,
        sid: str | None = None,
        confirmation_mode: bool = False,
        initial_state: State | None = None,
        is_delegate: bool = False,
        headless_mode: bool = True,
        status_callback: Callable[..., Any] | None = None,
    ) -> None:
        """Initialize the AgentController.

        Args:
            agent: The agent providing intelligence (LLM-based reasoning).
            event_stream: The event bus for all communication.
            max_iterations: Maximum agent steps allowed.
            max_budget_per_task: Maximum USD budget for LLM costs.
            agent_to_llm_config: Map of agent names to LLM configs.
            agent_configs: Map of agent names to agent configs.
            sid: Session ID (defaults to event_stream.sid).
            confirmation_mode: Require user approval for actions.
            initial_state: Pre-existing state for session recovery.
            is_delegate: Whether this is a child/delegate controller.
            headless_mode: Whether running without a UI.
            status_callback: Optional callback for status updates.
        """
        self.id = sid or event_stream.sid
        self.agent = agent
        self.event_stream = event_stream
        self.headless_mode = headless_mode
        self.is_delegate = is_delegate
        self.confirmation_mode = confirmation_mode
        self.status_callback = status_callback
        self.agent_to_llm_config = agent_to_llm_config or {}
        self.agent_configs = agent_configs or {}

        self.delegate = None
        self.parent = None
        self._closed = False
        self._pending_action: tuple[Action, float] | None = None

        # Initialize state
        if initial_state is not None:
            self.state = initial_state
        else:
            self.state = State(
                max_iterations=max_iterations,
                max_budget_per_task=max_budget_per_task,
                confirmation_mode=confirmation_mode,
            )

        # Initialize subsystems
        self._stuck_detector = StuckDetector(self.state)
        self._planner = Planner(self.state)

        # Subscribe to event stream (only root controller subscribes)
        if not self.is_delegate:
            self.event_stream.subscribe(
                EventStreamSubscriber.AGENT_CONTROLLER,
                self.on_event,
                self.id,
            )

    async def close(self, set_stop_state: bool = True) -> None:
        """Shut down the controller and clean up resources.

        Args:
            set_stop_state: Whether to transition to STOPPED state.
        """
        if set_stop_state:
            await self.set_agent_state_to(AgentState.STOPPED)

        if not self.is_delegate:
            self.event_stream.unsubscribe(
                EventStreamSubscriber.AGENT_CONTROLLER, self.id
            )
        self._closed = True

    # ------------------------------------------------------------------
    # State Machine
    # ------------------------------------------------------------------

    async def set_agent_state_to(self, new_state: AgentState) -> None:
        """Transition the agent to a new lifecycle state.

        Validates the transition and publishes an AgentStateChanged
        observation to the event stream.

        Args:
            new_state: The target state.
        """
        old_state = self.state.agent_state
        if old_state == new_state:
            return

        self.state.agent_state = new_state
        logger.info(
            "[Controller %s] State: %s -> %s",
            self.id,
            old_state.value,
            new_state.value,
        )

        # Publish state change observation
        obs = AgentStateChangedObservation(
            content=f"Agent state changed from {old_state.value} to {new_state.value}",
            new_state=new_state.value,
        )
        self.event_stream.add_event(obs, EventSource.AGENT)

        # Invoke status callback
        if self.status_callback is not None:
            self.status_callback("info", new_state.value, "")

    def get_agent_state(self) -> AgentState:
        """Get the current agent lifecycle state."""
        return self.state.agent_state

    # ------------------------------------------------------------------
    # Event Handling
    # ------------------------------------------------------------------

    def on_event(self, event: Event) -> None:
        """Callback from the EventStream for incoming events.

        Routes events to the delegate if one exists, otherwise
        processes them in this controller.

        Args:
            event: The incoming event.
        """
        if self.delegate is not None:
            delegate_state = self.delegate.get_agent_state()
            if delegate_state in AgentState.terminal_states():
                self._end_delegate()
                return
            return

        asyncio.get_event_loop().run_until_complete(self._on_event(event))

    async def _on_event(self, event: Event) -> None:
        """Internal event processing.

        Updates history and dispatches to the appropriate handler
        based on event type.
        """
        if hasattr(event, "hidden") and event.hidden:
            return

        # Record in history
        from dataclasses import asdict

        try:
            event_data = asdict(event)
        except TypeError:
            event_data = {"content": str(event)}
        self.state.add_history(event_data)

        # Handle based on type
        if isinstance(event, Action):
            await self._handle_action(event)
        elif isinstance(event, Observation):
            await self._handle_observation(event)

        # Decide whether to step
        if self._should_step(event):
            await self._step_with_exception_handling()

    async def _handle_action(self, action: Action) -> None:
        """Process an incoming action event."""
        if isinstance(action, ChangeAgentStateAction):
            target = AgentState(action.target_state)
            await self.set_agent_state_to(target)

    async def _handle_observation(self, observation: Observation) -> None:
        """Process an incoming observation event."""
        if isinstance(observation, AgentDelegateObservation):
            self._end_delegate()

    def _should_step(self, event: Event) -> bool:
        """Determine if the agent should take another step.

        The agent steps after receiving user messages or environment
        observations, but not after its own actions (those are handled
        by the runtime).
        """
        if self.delegate is not None:
            return False

        if isinstance(event, Action):
            if (
                isinstance(event, MessageAction)
                and event.source == EventSource.USER
            ):
                return True
            if isinstance(event, AgentDelegateAction):
                return True
            return False

        if isinstance(event, Observation):
            if isinstance(event, (NullObservation, AgentStateChangedObservation)):
                return False
            return True

        return False

    # ------------------------------------------------------------------
    # Core Execution Loop
    # ------------------------------------------------------------------

    async def _step_with_exception_handling(self) -> None:
        """Execute a single agent step with error recovery."""
        try:
            await self._step()
        except LLMContextWindowExceededError:
            logger.warning(
                "[Controller %s] Context window exceeded, "
                "attempting condensation",
                self.id,
            )
            self.state.last_error = "Context window exceeded"
            await self.set_agent_state_to(AgentState.ERROR)
        except AgentStuckInLoopError:
            logger.warning(
                "[Controller %s] Agent stuck in loop", self.id
            )
            self.state.last_error = "Agent stuck in a loop"
            await self.set_agent_state_to(AgentState.ERROR)
        except Exception as e:
            logger.error(
                "[Controller %s] Error during step: %s",
                self.id,
                str(e),
                exc_info=True,
            )
            self.state.last_error = f"{type(e).__name__}: {str(e)}"
            await self.set_agent_state_to(AgentState.ERROR)

    async def _step(self) -> None:
        """Execute a single iteration of the agent loop.

        This is the core of the Devin-style agent architecture:
        1. Check termination conditions (budget, iterations, stuck)
        2. If in INIT, transition to PLANNING
        3. If in PLANNING, generate the execution plan
        4. If in RUNNING, prompt the agent and execute the action
        5. Handle the resulting observation

        The loop continues until the agent finishes, errors, or
        a termination condition is met.
        """
        current_state = self.get_agent_state()

        # Terminal state - no more steps
        if current_state in AgentState.terminal_states():
            return

        # Paused or waiting - no autonomous steps
        if current_state in (
            AgentState.PAUSED,
            AgentState.AWAITING_USER_INPUT,
            AgentState.AWAITING_USER_CONFIRMATION,
            AgentState.RATE_LIMITED,
        ):
            return

        # Check termination conditions
        if self.state.is_iteration_limit_reached():
            self.state.last_error = "Agent reached maximum iterations"
            await self.set_agent_state_to(AgentState.ERROR)
            return

        if self.state.is_budget_exceeded():
            self.state.last_error = "Agent exceeded budget limit"
            await self.set_agent_state_to(AgentState.ERROR)
            return

        # Check for stuck state
        if self._stuck_detector.is_stuck():
            logger.warning(
                "[Controller %s] Stuck detected, attempting recovery",
                self.id,
            )
            await self._attempt_loop_recovery()
            return

        # State-specific logic
        if current_state == AgentState.INIT:
            await self.set_agent_state_to(AgentState.PLANNING)
            return

        if current_state == AgentState.PLANNING:
            await self._execute_planning()
            return

        if current_state == AgentState.RUNNING:
            await self._execute_step()
            return

    async def _execute_planning(self) -> None:
        """Execute the planning phase.

        In the Devin 2.0 model, the agent first scans the codebase
        and generates a plan before starting execution.
        """
        # Get the first user message as the task description
        task_description = self._get_task_description()
        if not task_description:
            await self.set_agent_state_to(AgentState.AWAITING_USER_INPUT)
            return

        # Generate plan
        self._planner.create_plan(task_description)

        # Publish plan as an action
        plan_data = [
            {"id": s.id, "description": s.description, "status": s.status}
            for s in self.state.plan
        ]
        plan_action = PlanCreateAction(
            plan=plan_data,
            summary=f"Plan for: {task_description[:200]}",
        )
        self.event_stream.add_event(plan_action, EventSource.AGENT)

        # Transition to running
        await self.set_agent_state_to(AgentState.RUNNING)

    async def _execute_step(self) -> None:
        """Execute a single step in the running phase.

        Prompts the agent for the next action and publishes it
        to the event stream for execution by the runtime.
        """
        self.state.iteration += 1
        self.state.metrics.total_actions += 1

        # Get next action from the agent
        action = self.agent.step(self.state)

        if action is None:
            return

        # Handle terminal actions
        if isinstance(action, AgentFinishAction):
            self.state.outputs = action.outputs
            self.event_stream.add_event(action, EventSource.AGENT)
            await self.set_agent_state_to(AgentState.FINISHED)
            return

        if isinstance(action, AgentRejectAction):
            self.event_stream.add_event(action, EventSource.AGENT)
            await self.set_agent_state_to(AgentState.REJECTED)
            return

        if isinstance(action, MessageAction) and action.wait_for_response:
            self.event_stream.add_event(action, EventSource.AGENT)
            await self.set_agent_state_to(AgentState.AWAITING_USER_INPUT)
            return

        # Handle delegation (managed Devins)
        if isinstance(action, AgentDelegateAction):
            await self._start_delegate(action)
            return

        # Publish action for runtime execution
        self._pending_action = (action, time.time())
        self.event_stream.add_event(action, EventSource.AGENT)

    # ------------------------------------------------------------------
    # Delegation (Managed Devins)
    # ------------------------------------------------------------------

    async def _start_delegate(self, action: AgentDelegateAction) -> None:
        """Start a delegate (child) agent for a sub-task.

        Mirrors Devin.ai's managed Devins feature where the main
        session can spawn child sessions for parallel work.
        """
        logger.info(
            "[Controller %s] Delegating to agent: %s",
            self.id,
            action.agent,
        )

        # Create child agent (simplified - in production would use
        # agent_configs to instantiate the right agent type)
        child_agent = self.agent  # Simplified: reuse same agent

        self.delegate = AgentController(
            agent=child_agent,
            event_stream=self.event_stream,
            max_iterations=self.state.max_iterations,
            max_budget_per_task=self.state.max_budget_per_task,
            sid=f"{self.id}-delegate",
            is_delegate=True,
        )
        self.delegate.parent = self

        await self.delegate.set_agent_state_to(AgentState.RUNNING)

    def _end_delegate(self) -> None:
        """Clean up after a delegate agent finishes."""
        if self.delegate is None:
            return

        delegate_state = self.delegate.state
        outputs = delegate_state.outputs

        # Publish delegate result
        obs = AgentDelegateObservation(
            content=f"Delegate finished with state: {delegate_state.agent_state.value}",
            outputs=outputs,
        )
        self.event_stream.add_event(obs, EventSource.AGENT)

        self.delegate = None

    # ------------------------------------------------------------------
    # Recovery
    # ------------------------------------------------------------------

    async def _attempt_loop_recovery(self) -> None:
        """Attempt to recover from a detected stuck state.

        Strategies (in order):
        1. Inject a recovery message to the agent
        2. Truncate recent history
        3. If all else fails, transition to ERROR
        """
        recovery_message = MessageAction(
            content=(
                "You appear to be stuck in a loop. Please try a different "
                "approach or ask the user for clarification."
            )
        )
        self.event_stream.add_event(recovery_message, EventSource.SYSTEM)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_task_description(self) -> str:
        """Extract the task description from the first user message."""
        for event_data in self.state.history:
            if (
                event_data.get("action_type") == "message"
                and event_data.get("_source") == "user"
            ):
                return event_data.get("content", "")
        return ""

    def get_state(self) -> State:
        """Get the current session state."""
        return self.state

    def __repr__(self) -> str:
        return (
            f"AgentController(id={self.id!r}, "
            f"state={self.state.agent_state.value!r}, "
            f"iteration={self.state.iteration})"
        )
