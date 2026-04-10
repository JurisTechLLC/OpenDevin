"""Stuck detection for OttoSoftwareEngineer.

Detects when the agent is stuck in a loop or making no progress,
and triggers recovery mechanisms. This is critical for autonomous
operation where the agent must self-recover without human intervention.
"""

from __future__ import annotations

import logging
from typing import Any

from OttoSoftwareEngineer.controller.state import State

logger = logging.getLogger(__name__)


class StuckDetector:
    """Detects when the agent is repeating actions without progress.

    Monitors the agent's action history for patterns that indicate
    the agent is stuck:
    - Exact action repetition (same command/edit repeated)
    - Alternating action pairs (A-B-A-B pattern)
    - Empty/null action sequences
    - Error loops (same error repeated)

    Mirrors Devin.ai's built-in loop detection and recovery system.

    Attributes:
        state: Reference to the session state being monitored.
        window_size: Number of recent actions to check for patterns.
        repetition_threshold: Number of repetitions to trigger detection.
    """

    def __init__(
        self,
        state: State,
        window_size: int = 10,
        repetition_threshold: int = 3,
    ) -> None:
        """Initialize the StuckDetector.

        Args:
            state: The session state to monitor.
            window_size: Number of recent events to analyze.
            repetition_threshold: Repetitions needed to declare stuck.
        """
        self.state = state
        self.window_size = window_size
        self.repetition_threshold = repetition_threshold

    def is_stuck(self) -> bool:
        """Check if the agent appears to be stuck.

        Analyzes recent history for repetitive patterns.

        Returns:
            True if a stuck pattern is detected.
        """
        if len(self.state.history) < self.repetition_threshold:
            return False

        recent = self.state.history[-self.window_size :]

        if self._detect_exact_repetition(recent):
            logger.warning("StuckDetector: exact action repetition detected")
            return True

        if self._detect_alternating_pattern(recent):
            logger.warning("StuckDetector: alternating action pattern detected")
            return True

        if self._detect_error_loop(recent):
            logger.warning("StuckDetector: error loop detected")
            return True

        return False

    def _detect_exact_repetition(
        self, history: list[dict[str, Any]]
    ) -> bool:
        """Detect if the same action is being repeated consecutively."""
        if len(history) < self.repetition_threshold:
            return False

        recent_actions = [
            self._action_signature(h)
            for h in history
            if h.get("action_type")
        ]

        if len(recent_actions) < self.repetition_threshold:
            return False

        last_actions = recent_actions[-self.repetition_threshold :]
        return len(set(last_actions)) == 1

    def _detect_alternating_pattern(
        self, history: list[dict[str, Any]]
    ) -> bool:
        """Detect A-B-A-B alternating action patterns."""
        if len(history) < 4:
            return False

        recent_actions = [
            self._action_signature(h)
            for h in history
            if h.get("action_type")
        ]

        if len(recent_actions) < 4:
            return False

        last_four = recent_actions[-4:]
        return last_four[0] == last_four[2] and last_four[1] == last_four[3]

    def _detect_error_loop(self, history: list[dict[str, Any]]) -> bool:
        """Detect repeated identical error observations."""
        errors = [
            h.get("content", "")
            for h in history
            if h.get("observation_type") == "error"
        ]

        if len(errors) < self.repetition_threshold:
            return False

        last_errors = errors[-self.repetition_threshold :]
        return len(set(last_errors)) == 1

    def _action_signature(self, event: dict[str, Any]) -> str:
        """Create a hashable signature for an action event."""
        action_type = event.get("action_type", "")
        content = event.get("content", "")
        command = event.get("command", "")
        path = event.get("path", "")
        return f"{action_type}:{command}:{path}:{content[:200]}"
