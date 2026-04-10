"""Playbook system for OttoSoftwareEngineer.

Playbooks are reusable, structured procedures that guide the agent
through common tasks. They can be created by users, shared across
an organization, and triggered automatically or manually.

Mirrors the Devin.ai playbook system where organizations can define
standard procedures for the agent to follow.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PlaybookStep:
    """A single step in a playbook.

    Attributes:
        order: Step sequence number.
        instruction: What the agent should do.
        expected_output: What success looks like.
        is_optional: Whether this step can be skipped.
    """

    order: int = 0
    instruction: str = ""
    expected_output: str = ""
    is_optional: bool = False


@dataclass
class Playbook:
    """A reusable task procedure for the agent.

    Playbooks encode organizational knowledge about how to perform
    specific tasks, ensuring consistency across sessions.

    Attributes:
        id: Unique playbook identifier.
        name: Human-readable playbook name.
        description: What this playbook does.
        steps: Ordered list of execution steps.
        trigger_patterns: Patterns that auto-trigger this playbook.
        tags: Categorization tags.
        version: Playbook version string.
    """

    id: str = ""
    name: str = ""
    description: str = ""
    steps: list[PlaybookStep] = field(default_factory=list)
    trigger_patterns: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    version: str = "1.0"

    def get_instructions(self) -> str:
        """Generate formatted instructions from the playbook steps.

        Returns:
            Formatted instruction string for the agent.
        """
        lines = [f"# Playbook: {self.name}", f"{self.description}", ""]
        for step in sorted(self.steps, key=lambda s: s.order):
            optional = " (optional)" if step.is_optional else ""
            lines.append(f"{step.order}. {step.instruction}{optional}")
            if step.expected_output:
                lines.append(f"   Expected: {step.expected_output}")
        return "\n".join(lines)


class PlaybookManager:
    """Manages playbook storage and retrieval.

    Provides CRUD operations for playbooks and pattern-based
    matching for auto-triggering.

    Attributes:
        playbooks: Dictionary of playbooks by ID.
    """

    def __init__(self) -> None:
        """Initialize the PlaybookManager."""
        self._playbooks: dict[str, Playbook] = {}

    def add(self, playbook: Playbook) -> None:
        """Add a playbook to the store.

        Args:
            playbook: The playbook to add.
        """
        self._playbooks[playbook.id] = playbook
        logger.info("Playbook added: %s (%s)", playbook.name, playbook.id)

    def get(self, playbook_id: str) -> Playbook | None:
        """Get a playbook by ID.

        Args:
            playbook_id: The playbook identifier.

        Returns:
            The playbook, or None if not found.
        """
        return self._playbooks.get(playbook_id)

    def remove(self, playbook_id: str) -> bool:
        """Remove a playbook.

        Args:
            playbook_id: The playbook identifier.

        Returns:
            True if removed, False if not found.
        """
        if playbook_id in self._playbooks:
            del self._playbooks[playbook_id]
            return True
        return False

    def find_by_trigger(self, text: str) -> list[Playbook]:
        """Find playbooks matching trigger patterns.

        Args:
            text: Text to match against trigger patterns.

        Returns:
            List of matching playbooks.
        """
        matches = []
        for playbook in self._playbooks.values():
            for pattern in playbook.trigger_patterns:
                if pattern.lower() in text.lower():
                    matches.append(playbook)
                    break
        return matches

    def list_all(self) -> list[Playbook]:
        """List all playbooks.

        Returns:
            List of all stored playbooks.
        """
        return list(self._playbooks.values())
