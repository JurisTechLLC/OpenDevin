"""Base agent class for OttoSoftwareEngineer.

Defines the abstract interface that all agent implementations must follow.
An agent is responsible for deciding what action to take next based on
the current session state and conversation history.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from OttoSoftwareEngineer.core.events.actions import Action

if TYPE_CHECKING:
    from OttoSoftwareEngineer.config import AgentConfig, LLMConfig
    from OttoSoftwareEngineer.controller.state import State
    from OttoSoftwareEngineer.llm.llm import LLM


class BaseAgent(ABC):
    """Abstract base class for all Otto agents.

    An agent encapsulates the intelligence layer - it receives the
    current state (history of actions and observations) and decides
    what action to take next. This mirrors the Devin.ai architecture
    where the agent's reasoning (LLM) is separated from the execution
    (runtime/sandbox).

    Subclasses must implement:
    - step(): Given current state, return the next action

    Attributes:
        llm: The LLM instance for generating responses.
        config: Agent-specific configuration.
        name: Human-readable agent name.
    """

    # Registry of agent implementations
    _registry: dict[str, type[BaseAgent]] = {}

    def __init__(
        self,
        llm: LLM,
        config: AgentConfig | None = None,
    ) -> None:
        """Initialize the agent.

        Args:
            llm: The LLM instance for reasoning.
            config: Agent behavior configuration.
        """
        self.llm = llm
        self.config = config
        self.name: str = self.__class__.__name__

    @abstractmethod
    def step(self, state: State) -> Action:
        """Decide the next action based on current state.

        This is the core agent method - it examines the conversation
        history and current state, reasons about what to do next,
        and returns an action for the runtime to execute.

        Args:
            state: Current session state with full history.

        Returns:
            The next action to execute.
        """

    def reset(self) -> None:
        """Reset the agent's internal state between tasks."""

    def get_system_prompt(self) -> str:
        """Generate the system prompt for the LLM.

        Returns:
            The system prompt string.
        """
        return ""

    @classmethod
    def register(cls, name: str, agent_cls: type[BaseAgent]) -> None:
        """Register an agent implementation.

        Args:
            name: Name to register under.
            agent_cls: The agent class to register.
        """
        cls._registry[name] = agent_cls

    @classmethod
    def get_cls(cls, name: str) -> type[BaseAgent] | None:
        """Get a registered agent class by name.

        Args:
            name: Registered agent name.

        Returns:
            The agent class, or None if not found.
        """
        return cls._registry.get(name)

    @classmethod
    def list_agents(cls) -> list[str]:
        """List all registered agent names.

        Returns:
            List of registered agent names.
        """
        return list(cls._registry.keys())
