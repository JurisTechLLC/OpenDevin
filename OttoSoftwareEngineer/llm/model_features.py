"""Model feature detection for OttoSoftwareEngineer.

Defines capabilities for different LLM models so the system can
adapt its behavior (e.g., whether to send images, use function
calling, enable prompt caching).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelFeatures:
    """Capabilities of a specific LLM model.

    Used to adapt message formatting and tool usage based on
    what the model supports.

    Attributes:
        supports_vision: Can process image inputs.
        supports_function_calling: Can use tool/function calling.
        supports_prompt_caching: Supports Anthropic-style caching.
        supports_reasoning: Has extended reasoning/thinking mode.
        max_context_tokens: Maximum context window size.
        stop_words: Model-specific stop sequences.
    """

    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_prompt_caching: bool = False
    supports_reasoning: bool = False
    max_context_tokens: int = 128000
    stop_words: list[str] | None = None


# Known model capabilities registry
MODEL_REGISTRY: dict[str, ModelFeatures] = {
    "gpt-4o": ModelFeatures(
        supports_vision=True,
        supports_function_calling=True,
        max_context_tokens=128000,
    ),
    "gpt-4o-mini": ModelFeatures(
        supports_vision=True,
        supports_function_calling=True,
        max_context_tokens=128000,
    ),
    "gpt-4-turbo": ModelFeatures(
        supports_vision=True,
        supports_function_calling=True,
        max_context_tokens=128000,
    ),
    "claude-3-opus": ModelFeatures(
        supports_vision=True,
        supports_function_calling=True,
        supports_prompt_caching=True,
        max_context_tokens=200000,
    ),
    "claude-3-5-sonnet": ModelFeatures(
        supports_vision=True,
        supports_function_calling=True,
        supports_prompt_caching=True,
        supports_reasoning=True,
        max_context_tokens=200000,
    ),
    "claude-3-5-haiku": ModelFeatures(
        supports_vision=True,
        supports_function_calling=True,
        supports_prompt_caching=True,
        max_context_tokens=200000,
    ),
    "gemini-pro": ModelFeatures(
        supports_vision=True,
        supports_function_calling=True,
        max_context_tokens=1000000,
    ),
    "gemini-2.0-flash": ModelFeatures(
        supports_vision=True,
        supports_function_calling=True,
        max_context_tokens=1000000,
    ),
}


def get_features(model: str) -> ModelFeatures:
    """Get the features for a model, with sensible defaults.

    Args:
        model: Model identifier string.

    Returns:
        ModelFeatures for the model.
    """
    # Try exact match
    if model in MODEL_REGISTRY:
        return MODEL_REGISTRY[model]

    # Try prefix match (e.g., "gpt-4o-2024-08-06" -> "gpt-4o")
    for key, features in MODEL_REGISTRY.items():
        if model.startswith(key):
            return features

    # Default: assume basic capabilities
    return ModelFeatures(
        supports_vision=False,
        supports_function_calling=True,
        max_context_tokens=128000,
    )
