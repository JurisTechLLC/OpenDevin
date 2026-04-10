"""Agent hub for OttoSoftwareEngineer.

Contains agent implementations that provide the intelligence layer:
- BaseAgent: Abstract base class for all agents
- CodeActAgent: Primary agent using the ReAct pattern with code actions

Mirrors the Devin.ai agent architecture where the core agent combines
reasoning (thinking) with action execution (tool use) in an iterative loop.
"""

from OttoSoftwareEngineer.agenthub.base_agent import BaseAgent
from OttoSoftwareEngineer.agenthub.codeact_agent import CodeActAgent

__all__ = [
    "BaseAgent",
    "CodeActAgent",
]
