"""Knowledge store for OttoSoftwareEngineer.

Persistent information store that the agent can create, read, update,
and delete notes. This mirrors the Devin.ai knowledge notes feature
where agents can store and retrieve information across sessions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeNote:
    """A single knowledge note.

    Attributes:
        id: Unique note identifier.
        title: Note title/subject.
        content: Note content (markdown).
        tags: Categorization tags.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        source: Where this knowledge came from.
    """

    id: str = ""
    title: str = ""
    content: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = ""


class KnowledgeStore:
    """Persistent knowledge base for the agent.

    Stores and retrieves knowledge notes, enabling the agent to
    build up institutional knowledge over time. This mirrors the
    Devin.ai knowledge management system.

    Attributes:
        notes: Dictionary of notes by ID.
    """

    def __init__(self) -> None:
        """Initialize the KnowledgeStore."""
        self._notes: dict[str, KnowledgeNote] = {}

    def add(self, note: KnowledgeNote) -> None:
        """Add a knowledge note.

        Args:
            note: The note to add.
        """
        self._notes[note.id] = note
        logger.info("Knowledge note added: %s (%s)", note.title, note.id)

    def get(self, note_id: str) -> KnowledgeNote | None:
        """Get a note by ID.

        Args:
            note_id: The note identifier.

        Returns:
            The note, or None if not found.
        """
        return self._notes.get(note_id)

    def update(self, note_id: str, **updates: Any) -> KnowledgeNote | None:
        """Update a note's fields.

        Args:
            note_id: The note identifier.
            **updates: Fields to update.

        Returns:
            The updated note, or None if not found.
        """
        note = self._notes.get(note_id)
        if note is None:
            return None

        for key, value in updates.items():
            if hasattr(note, key):
                setattr(note, key, value)
        note.updated_at = datetime.now().isoformat()
        return note

    def delete(self, note_id: str) -> bool:
        """Delete a note.

        Args:
            note_id: The note identifier.

        Returns:
            True if deleted, False if not found.
        """
        if note_id in self._notes:
            del self._notes[note_id]
            return True
        return False

    def search(self, query: str, tags: list[str] | None = None) -> list[KnowledgeNote]:
        """Search notes by content and/or tags.

        Args:
            query: Text to search for in title and content.
            tags: Optional tags to filter by.

        Returns:
            List of matching notes.
        """
        results = []
        query_lower = query.lower()
        for note in self._notes.values():
            # Check text match
            text_match = (
                query_lower in note.title.lower()
                or query_lower in note.content.lower()
            )

            # Check tag match
            tag_match = True
            if tags:
                tag_match = any(t in note.tags for t in tags)

            if text_match and tag_match:
                results.append(note)

        return results

    def list_all(self) -> list[KnowledgeNote]:
        """List all knowledge notes.

        Returns:
            List of all stored notes.
        """
        return list(self._notes.values())
