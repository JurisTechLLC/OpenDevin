"""Master configuration for OttoSoftwareEngineer.

Aggregates all sub-configurations into a single unified config object,
similar to OpenHands' OpenHandsConfig. Supports loading from TOML files,
environment variables, and runtime overrides.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from OttoSoftwareEngineer.config.agent_config import AgentConfig
from OttoSoftwareEngineer.config.llm_config import LLMConfig
from OttoSoftwareEngineer.config.sandbox_config import SandboxConfig


@dataclass
class SecurityConfig:
    """Security settings for the Otto system.

    Attributes:
        security_analyzer: Name of the security analyzer to use.
        confirmation_mode: Require user confirmation for risky actions.
    """

    security_analyzer: str = ""
    confirmation_mode: bool = False


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP (Model Context Protocol) server.

    Mirrors Devin.ai's MCP integration for external tool servers.

    Attributes:
        name: Display name of the MCP server.
        url: Server URL (for SSE/HTTP transport).
        command: Command to run (for stdio transport).
        args: Arguments for the command.
        api_key: Authentication key.
        env_vars: Environment variables for the server process.
    """

    name: str = ""
    url: str = ""
    command: str = ""
    args: list[str] = field(default_factory=list)
    api_key: str = ""
    env_vars: dict[str, str] = field(default_factory=dict)


@dataclass
class MCPConfig:
    """Configuration for all MCP servers.

    Attributes:
        sse_servers: Servers using Server-Sent Events transport.
        stdio_servers: Servers using stdio transport.
        http_servers: Servers using HTTP transport.
    """

    sse_servers: list[MCPServerConfig] = field(default_factory=list)
    stdio_servers: list[MCPServerConfig] = field(default_factory=list)
    http_servers: list[MCPServerConfig] = field(default_factory=list)


@dataclass
class OttoConfig:
    """Master configuration for the OttoSoftwareEngineer system.

    Aggregates all sub-configurations and provides methods for loading
    from various sources. This is the single entry point for all
    configuration access throughout the system.

    Attributes:
        llm: Default LLM configuration.
        llm_configs: Named LLM configurations for different purposes.
        agent: Agent behavior configuration.
        sandbox: Sandbox environment configuration.
        security: Security settings.
        mcp: MCP server configurations.
        workspace_base: Base directory for all workspaces.
        data_dir: Directory for persistent data storage.
        debug: Enable debug mode with verbose logging.
        file_store: Type of file store ('local', 's3').
        file_store_path: Path for the file store.
    """

    llm: LLMConfig = field(default_factory=LLMConfig)
    llm_configs: dict[str, LLMConfig] = field(default_factory=dict)
    agent: AgentConfig = field(default_factory=AgentConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    workspace_base: str = "/tmp/otto-workspace"
    data_dir: str = "/tmp/otto-data"
    debug: bool = False
    file_store: str = "local"
    file_store_path: str = "/tmp/otto-file-store"

    def get_llm_config(self, name: str = "default") -> LLMConfig:
        """Get a named LLM config, falling back to the default.

        Args:
            name: Name of the LLM config to retrieve.

        Returns:
            The requested LLMConfig or the default.
        """
        if name == "default" or name not in self.llm_configs:
            return self.llm
        return self.llm_configs[name]

    @classmethod
    def from_env(cls) -> OttoConfig:
        """Create a configuration from environment variables.

        Environment variables follow the pattern:
        OTTO_<SECTION>_<KEY> (e.g., OTTO_LLM_MODEL, OTTO_SANDBOX_TIMEOUT)

        Returns:
            An OttoConfig populated from environment variables.
        """
        config = cls()

        # LLM settings
        if model := os.environ.get("OTTO_LLM_MODEL"):
            config.llm.model = model
        if api_key := os.environ.get("OTTO_LLM_API_KEY"):
            config.llm.api_key = api_key
        if base_url := os.environ.get("OTTO_LLM_BASE_URL"):
            config.llm.base_url = base_url

        # Sandbox settings
        if runtime := os.environ.get("OTTO_SANDBOX_RUNTIME_TYPE"):
            config.sandbox.runtime_type = runtime
        if workspace := os.environ.get("OTTO_WORKSPACE_BASE"):
            config.workspace_base = workspace

        # Debug
        if os.environ.get("OTTO_DEBUG", "").lower() in ("1", "true"):
            config.debug = True

        return config

    @classmethod
    def from_toml(cls, path: str | Path) -> OttoConfig:
        """Load configuration from a TOML file.

        Args:
            path: Path to the TOML configuration file.

        Returns:
            An OttoConfig populated from the TOML file.

        Raises:
            FileNotFoundError: If the config file doesn't exist.
        """
        import tomllib

        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        config = cls()

        # Parse LLM section
        if llm_data := data.get("llm"):
            for key, value in llm_data.items():
                if hasattr(config.llm, key):
                    setattr(config.llm, key, value)

        # Parse agent section
        if agent_data := data.get("agent"):
            for key, value in agent_data.items():
                if hasattr(config.agent, key):
                    setattr(config.agent, key, value)

        # Parse sandbox section
        if sandbox_data := data.get("sandbox"):
            for key, value in sandbox_data.items():
                if hasattr(config.sandbox, key):
                    setattr(config.sandbox, key, value)

        # Parse top-level settings
        if workspace := data.get("workspace_base"):
            config.workspace_base = workspace
        if debug := data.get("debug"):
            config.debug = debug

        return config
