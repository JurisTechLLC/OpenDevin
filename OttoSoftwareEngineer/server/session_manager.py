"""Session manager for OttoSoftwareEngineer.

Manages the lifecycle of multiple concurrent agent sessions,
mirroring the Devin.ai platform's ability to run many parallel
sessions simultaneously.

Features:
- Create, retrieve, and destroy sessions
- Track active and completed sessions
- Enforce session limits and quotas
"""

from __future__ import annotations

import logging
from typing import Any

from OttoSoftwareEngineer.config.otto_config import OttoConfig
from OttoSoftwareEngineer.core.exceptions import (
    SessionAlreadyExistsError,
    SessionNotFoundError,
)
from OttoSoftwareEngineer.server.agent_session import AgentSession

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages multiple concurrent agent sessions.

    The SessionManager is the top-level coordinator for all active
    agent sessions. In the Devin.ai model, users can have multiple
    sessions running in parallel (managed Devins), each working on
    independent tasks.

    Features:
    - Session CRUD operations
    - Concurrent session tracking
    - Session limit enforcement
    - Session metadata and status queries

    Attributes:
        config: System configuration.
        max_concurrent_sessions: Maximum allowed concurrent sessions.
    """

    def __init__(
        self,
        config: OttoConfig | None = None,
        max_concurrent_sessions: int = 10,
    ) -> None:
        """Initialize the SessionManager.

        Args:
            config: System configuration.
            max_concurrent_sessions: Maximum concurrent sessions allowed.
        """
        self.config = config or OttoConfig()
        self.max_concurrent_sessions = max_concurrent_sessions
        self._sessions: dict[str, AgentSession] = {}
        self._session_metadata: dict[str, dict[str, Any]] = {}

    async def create_session(
        self,
        sid: str | None = None,
        config: OttoConfig | None = None,
    ) -> AgentSession:
        """Create a new agent session.

        Args:
            sid: Optional session ID (auto-generated if not provided).
            config: Optional session-specific config override.

        Returns:
            The newly created AgentSession.

        Raises:
            SessionAlreadyExistsError: If sid already exists.
        """
        if sid and sid in self._sessions:
            raise SessionAlreadyExistsError(
                f"Session already exists: {sid}"
            )

        active_count = sum(
            1 for s in self._sessions.values() if s.is_running
        )
        if active_count >= self.max_concurrent_sessions:
            logger.warning(
                "Maximum concurrent sessions reached (%d)",
                self.max_concurrent_sessions,
            )

        session_config = config or self.config
        session = AgentSession(sid=sid, config=session_config)

        self._sessions[session.sid] = session
        self._session_metadata[session.sid] = {
            "created": True,
            "status": "created",
        }

        logger.info("Session created: %s", session.sid)
        return session

    def get_session(self, sid: str) -> AgentSession:
        """Retrieve a session by ID.

        Args:
            sid: Session identifier.

        Returns:
            The requested AgentSession.

        Raises:
            SessionNotFoundError: If session doesn't exist.
        """
        if sid not in self._sessions:
            raise SessionNotFoundError(f"Session not found: {sid}")
        return self._sessions[sid]

    async def stop_session(self, sid: str) -> None:
        """Stop a running session.

        Args:
            sid: Session identifier.

        Raises:
            SessionNotFoundError: If session doesn't exist.
        """
        session = self.get_session(sid)
        await session.stop()
        self._session_metadata[sid]["status"] = "stopped"
        logger.info("Session stopped: %s", sid)

    async def destroy_session(self, sid: str) -> None:
        """Destroy a session and clean up all resources.

        Args:
            sid: Session identifier.

        Raises:
            SessionNotFoundError: If session doesn't exist.
        """
        session = self.get_session(sid)
        if session.is_running:
            await session.stop()

        del self._sessions[sid]
        del self._session_metadata[sid]
        logger.info("Session destroyed: %s", sid)

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions with their status.

        Returns:
            List of session info dictionaries.
        """
        sessions = []
        for sid, session in self._sessions.items():
            info = {
                "sid": sid,
                "is_running": session.is_running,
                "metadata": self._session_metadata.get(sid, {}),
            }
            sessions.append(info)
        return sessions

    def get_active_count(self) -> int:
        """Get the number of currently active sessions."""
        return sum(1 for s in self._sessions.values() if s.is_running)

    async def stop_all_sessions(self) -> None:
        """Stop all running sessions."""
        for sid in list(self._sessions.keys()):
            session = self._sessions[sid]
            if session.is_running:
                await session.stop()
        logger.info("All sessions stopped")
