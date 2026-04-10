"""Microagent system for OttoSoftwareEngineer.

Microagents are repository-specific instruction files (AGENTS.md, .agents/)
that customize the agent's behavior for a particular codebase. They encode
project-specific conventions, patterns, and requirements.

Mirrors the Devin.ai microagent system where repos can include instruction
files that the agent loads automatically when working on that codebase.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Microagent:
    """A repository-specific agent instruction set.

    Microagents customize the agent's behavior for a specific codebase,
    encoding project conventions, required tools, and workflow steps.

    Attributes:
        name: Identifier for this microagent.
        content: The instruction content (markdown).
        source: File path where loaded from.
        repo: Repository this microagent belongs to.
        agent_type: Type of microagent (repo, knowledge, task).
    """

    name: str = ""
    content: str = ""
    source: str = ""
    repo: str = ""
    agent_type: str = "repo"
    triggers: list[str] = field(default_factory=list)


class MicroagentLoader:
    """Loads microagent instructions from repository files.

    Scans standard locations in a repository for agent instruction
    files and loads them into the system.

    Standard file locations:
    - .openhands/microagents/
    - .agents/
    - AGENTS.md
    - .github/agents/
    """

    def __init__(self) -> None:
        """Initialize the MicroagentLoader."""
        self._microagents: dict[str, Microagent] = {}

    def load_from_repo(self, repo_path: str | Path) -> list[Microagent]:
        """Load all microagents from a repository.

        Args:
            repo_path: Path to the repository root.

        Returns:
            List of loaded Microagent objects.
        """
        root = Path(repo_path)
        loaded: list[Microagent] = []

        # Check standard locations
        locations = [
            (".openhands/microagents", "*.md"),
            (".agents", "*.md"),
            (".", "AGENTS.md"),
            (".github/agents", "*.md"),
        ]

        for directory, pattern in locations:
            search_path = root / directory
            if search_path.is_file() and directory == ".":
                # Handle root-level AGENTS.md
                agent = self._load_file(root / pattern, str(root))
                if agent:
                    loaded.append(agent)
            elif search_path.is_dir():
                for filepath in search_path.glob(pattern):
                    agent = self._load_file(filepath, str(root))
                    if agent:
                        loaded.append(agent)

        for agent in loaded:
            self._microagents[agent.name] = agent

        logger.info(
            "Loaded %d microagents from %s", len(loaded), repo_path
        )
        return loaded

    def get(self, name: str) -> Microagent | None:
        """Get a microagent by name.

        Args:
            name: The microagent name.

        Returns:
            The microagent, or None if not found.
        """
        return self._microagents.get(name)

    def get_all(self) -> list[Microagent]:
        """Get all loaded microagents.

        Returns:
            List of all loaded microagents.
        """
        return list(self._microagents.values())

    def get_system_prompt_additions(self) -> str:
        """Get combined instructions from all microagents.

        Returns:
            Concatenated microagent instructions for the system prompt.
        """
        parts = []
        for agent in self._microagents.values():
            if agent.content:
                parts.append(
                    f"## Instructions from {agent.name}\n{agent.content}"
                )
        return "\n\n".join(parts)

    def _load_file(
        self, filepath: Path, repo_path: str
    ) -> Microagent | None:
        """Load a single microagent file.

        Args:
            filepath: Path to the microagent file.
            repo_path: Root path of the repository.

        Returns:
            Loaded Microagent, or None if file doesn't exist.
        """
        if not filepath.exists():
            return None

        try:
            content = filepath.read_text()
            name = filepath.stem
            return Microagent(
                name=name,
                content=content,
                source=str(filepath),
                repo=repo_path,
            )
        except Exception as e:
            logger.warning(
                "Failed to load microagent from %s: %s", filepath, e
            )
            return None
