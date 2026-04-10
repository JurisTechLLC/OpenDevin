"""Interactive planning system for OttoSoftwareEngineer.

Implements Devin 2.0's interactive planning feature where the agent
proactively researches the codebase and develops a detailed plan
that the user can review and modify before execution begins.

The planner:
1. Analyzes the user's request and codebase context
2. Generates a structured plan with discrete steps
3. Presents the plan for user review/modification
4. Tracks plan execution progress
"""

from __future__ import annotations

import logging
from typing import Any

from OttoSoftwareEngineer.controller.state import PlanStep, State

logger = logging.getLogger(__name__)


class Planner:
    """Interactive planning engine for task decomposition.

    Before executing any code changes, the planner analyzes the
    task and generates a structured execution plan. This mirrors
    Devin 2.0's planning feature where each session starts with
    a plan that can be reviewed and modified.

    Attributes:
        state: Reference to the session state.
    """

    def __init__(self, state: State) -> None:
        """Initialize the Planner.

        Args:
            state: The session state to store plans in.
        """
        self.state = state

    def create_plan(
        self,
        task_description: str,
        context: dict[str, Any] | None = None,
    ) -> list[PlanStep]:
        """Generate an execution plan for the given task.

        Analyzes the task description and any available context
        (repository structure, relevant files, etc.) to produce
        a structured plan.

        Args:
            task_description: Natural language description of the task.
            context: Optional context (file list, repo info, etc.).

        Returns:
            List of PlanStep objects representing the execution plan.
        """
        steps = self._decompose_task(task_description, context or {})
        self.state.plan = steps
        logger.info(
            "Created plan with %d steps for task: %s",
            len(steps),
            task_description[:100],
        )
        return steps

    def update_step(
        self,
        step_id: str,
        status: str | None = None,
        description: str | None = None,
        details: str | None = None,
    ) -> PlanStep | None:
        """Update a specific step in the plan.

        Args:
            step_id: ID of the step to update.
            status: New status (pending, in_progress, completed, failed).
            description: Updated description.
            details: Updated implementation details.

        Returns:
            The updated PlanStep, or None if not found.
        """
        for step in self.state.plan:
            if step.id == step_id:
                if status is not None:
                    step.status = status
                if description is not None:
                    step.description = description
                if details is not None:
                    step.details = details
                return step
        return None

    def get_next_step(self) -> PlanStep | None:
        """Get the next pending step in the plan.

        Returns:
            The next PlanStep with status 'pending', or None if all done.
        """
        for step in self.state.plan:
            if step.status == "pending":
                return step
        return None

    def mark_step_complete(self, step_id: str) -> None:
        """Mark a plan step as completed."""
        self.update_step(step_id, status="completed")

    def mark_step_failed(self, step_id: str, reason: str = "") -> None:
        """Mark a plan step as failed."""
        self.update_step(step_id, status="failed", details=reason)

    def is_plan_complete(self) -> bool:
        """Check if all plan steps are completed or failed."""
        if not self.state.plan:
            return True
        return all(
            step.status in ("completed", "failed")
            for step in self.state.plan
        )

    def _decompose_task(
        self,
        task_description: str,
        context: dict[str, Any],
    ) -> list[PlanStep]:
        """Decompose a task into executable steps.

        This is a template method that can be enhanced with LLM-based
        planning. The default implementation creates a basic plan
        structure that the agent can refine.

        Args:
            task_description: The task to decompose.
            context: Available context for planning.

        Returns:
            List of PlanStep objects.
        """
        steps = [
            PlanStep(
                id="step-1",
                description="Analyze the codebase and understand the task requirements",
                status="pending",
            ),
            PlanStep(
                id="step-2",
                description="Identify relevant files and dependencies",
                status="pending",
            ),
            PlanStep(
                id="step-3",
                description="Implement the required changes",
                status="pending",
            ),
            PlanStep(
                id="step-4",
                description="Run tests and verify the implementation",
                status="pending",
            ),
            PlanStep(
                id="step-5",
                description="Create a pull request with the changes",
                status="pending",
            ),
        ]

        return steps
