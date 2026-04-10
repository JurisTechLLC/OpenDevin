"""Custom exceptions for OttoSoftwareEngineer.

Defines the exception hierarchy used across the system for
error handling and recovery.
"""


class OttoError(Exception):
    """Base exception for all OttoSoftwareEngineer errors."""


class LLMError(OttoError):
    """Base exception for LLM-related errors."""


class LLMContextWindowExceededError(LLMError):
    """The conversation exceeded the model's context window."""


class LLMMalformedActionError(LLMError):
    """The LLM produced an action that could not be parsed."""


class LLMNoActionError(LLMError):
    """The LLM did not produce any action in its response."""


class LLMResponseError(LLMError):
    """Generic error in the LLM response."""


class AgentError(OttoError):
    """Base exception for agent-related errors."""


class AgentStuckInLoopError(AgentError):
    """The agent is repeating the same actions without progress."""


class AgentRuntimeDisconnectedError(AgentError):
    """The sandbox runtime became unreachable."""


class RuntimeError(OttoError):
    """Base exception for runtime/sandbox errors."""


class SandboxTimeoutError(RuntimeError):
    """An action in the sandbox exceeded its timeout."""


class SandboxNotFoundError(RuntimeError):
    """The requested sandbox container does not exist."""


class SessionError(OttoError):
    """Base exception for session management errors."""


class SessionNotFoundError(SessionError):
    """The requested session does not exist."""


class SessionAlreadyExistsError(SessionError):
    """A session with the given ID already exists."""


class ConfigError(OttoError):
    """Base exception for configuration errors."""


class KnowledgeError(OttoError):
    """Base exception for knowledge/playbook errors."""
