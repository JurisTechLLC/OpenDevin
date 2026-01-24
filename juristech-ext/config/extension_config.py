"""
JurisTech OpenHands Extension - Configuration
Central configuration for all extension features.
"""

import os
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from pathlib import Path


@dataclass
class VisionSettings:
    """Settings for vision/image processing."""
    enabled: bool = True
    ollama_base_url: str = "http://localhost:11434"
    vision_model: str = "llava:7b"
    max_image_size_mb: float = 10.0
    description_max_tokens: int = 500
    auto_process_images: bool = True


@dataclass
class ModelConfig:
    """Configuration for an LLM model."""
    name: str
    display_name: str
    provider: str  # ollama, anthropic, openai, etc.
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None  # Environment variable name for API key
    is_vision_capable: bool = False
    is_coding_model: bool = True
    max_tokens: int = 4096
    temperature: float = 0.0


@dataclass
class ModelsSettings:
    """Settings for additional coding models."""
    models: List[ModelConfig] = field(default_factory=list)
    default_model: str = "ollama/glm4"
    
    def __post_init__(self):
        if not self.models:
            # Default models
            self.models = [
                ModelConfig(
                    name="ollama/glm4",
                    display_name="GLM-4 (Local)",
                    provider="ollama",
                    base_url="http://localhost:11434",
                    is_coding_model=True
                ),
                ModelConfig(
                    name="ollama/llava:7b",
                    display_name="Llava 7B (Vision)",
                    provider="ollama",
                    base_url="http://localhost:11434",
                    is_vision_capable=True,
                    is_coding_model=False
                ),
                ModelConfig(
                    name="anthropic/claude-opus-4-5-20251101",
                    display_name="Claude Opus 4.5",
                    provider="anthropic",
                    api_key_env="ANTHROPIC_API_KEY",
                    is_coding_model=True,
                    max_tokens=8192
                ),
                ModelConfig(
                    name="anthropic/claude-sonnet-4-5-20251101",
                    display_name="Claude Sonnet 4.5",
                    provider="anthropic",
                    api_key_env="ANTHROPIC_API_KEY",
                    is_coding_model=True,
                    max_tokens=8192
                ),
            ]


@dataclass
class DevinContainerSettings:
    """Settings for the Devin.ai development container."""
    enabled: bool = False
    container_name: str = "juristech-devin-sandbox"
    image: str = "ubuntu:22.04"
    ssh_port: int = 2222
    workspace_path: str = "/workspace"
    expose_ports: List[int] = field(default_factory=lambda: [3000, 3001, 8000, 8080])


@dataclass
class ExtensionConfig:
    """Main configuration for the JurisTech OpenHands Extension."""
    vision: VisionSettings = field(default_factory=VisionSettings)
    models: ModelsSettings = field(default_factory=ModelsSettings)
    devin_container: DevinContainerSettings = field(default_factory=DevinContainerSettings)
    
    # Extension metadata
    version: str = "1.0.0"
    extension_name: str = "JurisTech OpenHands Extension"
    
    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "ExtensionConfig":
        """Load configuration from a JSON file."""
        if config_path is None:
            config_path = os.environ.get(
                "JURISTECH_EXT_CONFIG",
                str(Path.home() / ".juristech-openhands" / "config.json")
            )
        
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                data = json.load(f)
                return cls.from_dict(data)
        
        return cls()
    
    def save(self, config_path: Optional[str] = None):
        """Save configuration to a JSON file."""
        if config_path is None:
            config_path = os.environ.get(
                "JURISTECH_EXT_CONFIG",
                str(Path.home() / ".juristech-openhands" / "config.json")
            )
        
        # Ensure directory exists
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "extension_name": self.extension_name,
            "vision": asdict(self.vision),
            "models": {
                "models": [asdict(m) for m in self.models.models],
                "default_model": self.models.default_model
            },
            "devin_container": asdict(self.devin_container)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtensionConfig":
        """Create from dictionary."""
        vision = VisionSettings(**data.get("vision", {}))
        
        models_data = data.get("models", {})
        models = ModelsSettings(
            models=[ModelConfig(**m) for m in models_data.get("models", [])],
            default_model=models_data.get("default_model", "ollama/glm4")
        )
        
        devin_container = DevinContainerSettings(**data.get("devin_container", {}))
        
        return cls(
            vision=vision,
            models=models,
            devin_container=devin_container,
            version=data.get("version", "1.0.0"),
            extension_name=data.get("extension_name", "JurisTech OpenHands Extension")
        )


# Global config instance
_config: Optional[ExtensionConfig] = None


def get_config() -> ExtensionConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = ExtensionConfig.load()
    return _config


def reload_config():
    """Reload configuration from file."""
    global _config
    _config = ExtensionConfig.load()
    return _config
