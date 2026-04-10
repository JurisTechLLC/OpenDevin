"""Skill system for OttoSoftwareEngineer.

Skills are step-by-step instructions loaded from repository files
(typically .agents/skills/ directories). They provide tested procedures
for specific tasks and are treated as strict checklists by the agent.

Mirrors the Devin.ai skills system where SKILL.md files in repos
provide curated instructions for common tasks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """A skill loaded from a repository.

    Skills contain step-by-step instructions that the agent must
    follow as strict checklists when activated.

    Attributes:
        name: Unique skill identifier.
        description: What this skill does.
        content: The full skill content (markdown).
        path: File path where the skill was loaded from.
        arguments: Expected arguments for the skill.
    """

    name: str = ""
    description: str = ""
    content: str = ""
    path: str = ""
    arguments: list[str] = field(default_factory=list)


class SkillManager:
    """Manages skill discovery and loading from repositories.

    Scans repository directories for SKILL.md files and makes
    them available for activation during agent sessions.

    Attributes:
        skills: Dictionary of skills by name.
    """

    def __init__(self) -> None:
        """Initialize the SkillManager."""
        self._skills: dict[str, Skill] = {}

    def load_from_directory(self, directory: str | Path) -> int:
        """Scan a directory for skill files and load them.

        Looks for SKILL.md files in the standard locations:
        - .agents/skills/*/SKILL.md
        - .claude/skills/*/SKILL.md (compatibility)

        Args:
            directory: Root directory to scan.

        Returns:
            Number of skills loaded.
        """
        root = Path(directory)
        count = 0

        skill_patterns = [
            ".agents/skills/*/SKILL.md",
            ".claude/skills/*/SKILL.md",
        ]

        for pattern in skill_patterns:
            for skill_path in root.glob(pattern):
                try:
                    skill = self._parse_skill_file(skill_path)
                    self._skills[skill.name] = skill
                    count += 1
                    logger.info("Loaded skill: %s from %s", skill.name, skill_path)
                except Exception as e:
                    logger.warning(
                        "Failed to load skill from %s: %s", skill_path, e
                    )

        return count

    def get(self, name: str) -> Skill | None:
        """Get a skill by name.

        Args:
            name: The skill name.

        Returns:
            The skill, or None if not found.
        """
        return self._skills.get(name)

    def list_all(self) -> list[Skill]:
        """List all loaded skills.

        Returns:
            List of all loaded skills.
        """
        return list(self._skills.values())

    def search(self, keyword: str) -> list[Skill]:
        """Search skills by keyword.

        Args:
            keyword: Keyword to search for in name and description.

        Returns:
            List of matching skills.
        """
        keyword_lower = keyword.lower()
        return [
            s
            for s in self._skills.values()
            if keyword_lower in s.name.lower()
            or keyword_lower in s.description.lower()
        ]

    def _parse_skill_file(self, path: Path) -> Skill:
        """Parse a SKILL.md file into a Skill object.

        Args:
            path: Path to the SKILL.md file.

        Returns:
            Parsed Skill object.
        """
        content = path.read_text()
        name = path.parent.name

        # Extract description from first paragraph
        lines = content.strip().split("\n")
        description = ""
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                description = stripped
                break

        return Skill(
            name=name,
            description=description,
            content=content,
            path=str(path),
        )
