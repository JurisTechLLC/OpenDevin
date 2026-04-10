"""Agent configuration for OttoSoftwareEngineer.

Defines settings that control the agent's behavior, including
iteration limits, budget constraints, and tool preferences.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentConfig:
    """Configuration for agent behavior.

    Controls how the Otto agent operates, including limits on
    iterations and spending, which tools are enabled, and
    how the agent handles errors and stuck states.

    Attributes:
        max_iterations: Maximum agent steps per session.
        max_budget_per_task: Maximum USD spend per task (LLM costs).
        agent_type: The agent implementation to use.
        enable_planning: Enable Devin 2.0-style interactive planning.
        enable_confirmation_mode: Require user approval for actions.
        enable_llm_editor: Use LLM for advanced file editing.
        condenser_type: Strategy for history condensation.
        stuck_detection_enabled: Enable loop/stuck detection.
        max_stuck_retries: Retries before declaring stuck.
        memory_enabled: Enable long-term memory features.
        micro_agent_enabled: Load repo-specific microagents.
    """

    max_iterations: int = 200
    max_budget_per_task: float = 10.0
    agent_type: str = "CodeActAgent"
    enable_planning: bool = True
    enable_confirmation_mode: bool = False
    enable_llm_editor: bool = False
    condenser_type: str = "observation_masking"
    stuck_detection_enabled: bool = True
    max_stuck_retries: int = 3
    memory_enabled: bool = False
    micro_agent_enabled: bool = True
    tools: list[str] = field(
        default_factory=lambda: [
            "shell",
            "browser",
            "editor",
            "search",
            "ipython",
        ]
    )
