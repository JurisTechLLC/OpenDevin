"""Configuration system for OttoSoftwareEngineer.

Provides a hierarchical configuration system supporting:
- TOML config files
- Environment variable overrides
- Runtime configuration merging

Mirrors the Devin.ai configuration model where each session
can be customized with different LLM providers, sandbox settings,
and agent behaviors.
"""

from OttoSoftwareEngineer.config.otto_config import OttoConfig
from OttoSoftwareEngineer.config.llm_config import LLMConfig
from OttoSoftwareEngineer.config.sandbox_config import SandboxConfig
from OttoSoftwareEngineer.config.agent_config import AgentConfig

__all__ = [
    "OttoConfig",
    "LLMConfig",
    "SandboxConfig",
    "AgentConfig",
]
