"""Agent state management for OttoSoftwareEngineer.

Tracks the complete state of an agent session, including conversation
history, metrics, iteration counts, and plan state. This enables
session persistence, replay, and recovery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from OttoSoftwareEngineer.core.schema.agent import AgentState


@dataclass
class Metrics:
    """Tracks resource usage metrics for a session.

    Mirrors Devin.ai's ACU (Agent Compute Unit) tracking.

    Attributes:
        total_cost: Total LLM cost in USD.
        total_input_tokens: Total input tokens consumed.
        total_output_tokens: Total output tokens generated.
        total_cached_tokens: Total cached tokens used.
        total_llm_calls: Number of LLM API calls.
        total_actions: Number of actions executed.
    """

    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cached_tokens: int = 0
    total_llm_calls: int = 0
    total_actions: int = 0

    def add_cost(
        self,
        cost: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0,
    ) -> None:
        """Record cost from an LLM call."""
        self.total_cost += cost
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cached_tokens += cached_tokens
        self.total_llm_calls += 1


@dataclass
class PlanStep:
    """A single step in the agent's execution plan.

    Part of the Devin 2.0 interactive planning system.

    Attributes:
        id: Unique identifier for the step.
        description: What needs to be done.
        status: Current status (pending, in_progress, completed, failed).
        details: Additional implementation details.
    """

    id: str = ""
    description: str = ""
    status: str = "pending"
    details: str = ""


@dataclass
class State:
    """Complete state of an agent session.

    Tracks everything needed to understand, persist, and resume
    an agent session. This is the central data structure that the
    AgentController operates on.

    Attributes:
        agent_state: Current lifecycle state of the agent.
        iteration: Current iteration number.
        max_iterations: Maximum allowed iterations.
        max_budget_per_task: Maximum USD budget for this task.
        start_id: First event ID in this session.
        history: Ordered list of (action, observation) pairs.
        plan: Current execution plan steps.
        metrics: Resource usage tracking.
        last_error: Description of the last error, if any.
        outputs: Final outputs from the agent.
        extra_data: Arbitrary additional state.
        confirmation_mode: Whether user confirmation is required.
    """

    agent_state: AgentState = field(default=AgentState.INIT)
    iteration: int = 0
    max_iterations: int = 200
    max_budget_per_task: float = 10.0
    start_id: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    plan: list[PlanStep] = field(default_factory=list)
    metrics: Metrics = field(default_factory=Metrics)
    last_error: str = ""
    outputs: dict[str, Any] = field(default_factory=dict)
    extra_data: dict[str, Any] = field(default_factory=dict)
    confirmation_mode: bool = False

    def add_history(self, event_data: dict[str, Any]) -> None:
        """Add an event to the session history."""
        self.history.append(event_data)

    def is_budget_exceeded(self) -> bool:
        """Check if the session has exceeded its budget."""
        if self.max_budget_per_task <= 0:
            return False
        return self.metrics.total_cost >= self.max_budget_per_task

    def is_iteration_limit_reached(self) -> bool:
        """Check if the session has reached its iteration limit."""
        return self.iteration >= self.max_iterations

    def get_plan_summary(self) -> str:
        """Generate a text summary of the current plan state."""
        if not self.plan:
            return "No plan defined."

        lines = []
        for i, step in enumerate(self.plan, 1):
            status_icon = {
                "pending": "[ ]",
                "in_progress": "[~]",
                "completed": "[x]",
                "failed": "[!]",
            }.get(step.status, "[ ]")
            lines.append(f"{status_icon} {i}. {step.description}")
        return "\n".join(lines)
