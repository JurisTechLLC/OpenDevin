"""Base tool interface for OttoSoftwareEngineer.

All sandbox tools inherit from this base class, providing a consistent
interface for tool registration, execution, and documentation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Result from a tool execution.

    Attributes:
        success: Whether the tool execution succeeded.
        output: The tool's output content.
        error: Error message if execution failed.
        metadata: Additional result metadata.
    """

    success: bool = True
    output: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    """Abstract base class for sandbox tools.

    Each tool represents a capability available to the agent within
    the sandboxed environment (shell, browser, editor, search).

    Attributes:
        name: Unique tool identifier.
        description: Human-readable tool description.
    """

    name: str = ""
    description: str = ""

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with the given parameters.

        Args:
            **kwargs: Tool-specific parameters.

        Returns:
            The result of the tool execution.
        """

    def get_schema(self) -> dict[str, Any]:
        """Get the JSON schema for this tool's parameters.

        Returns:
            JSON schema dictionary for function calling.
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {},
        }
