"""Server module for OttoSoftwareEngineer.

Provides the communication layer between the frontend and the agent:
- SessionManager: Manages multiple concurrent agent sessions
- AgentSession: Lifecycle of a single conversation/task
- API routes: REST endpoints for session management

Mirrors the Devin.ai web application backend that handles real-time
streaming of agent events to the browser-based UI.
"""

from OttoSoftwareEngineer.server.session_manager import SessionManager
from OttoSoftwareEngineer.server.agent_session import AgentSession

__all__ = [
    "SessionManager",
    "AgentSession",
]
