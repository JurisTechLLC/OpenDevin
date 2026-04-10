"""LLM configuration for OttoSoftwareEngineer.

Defines settings for connecting to and using Large Language Models.
Supports multiple providers (OpenAI, Anthropic, Google, AWS Bedrock, local)
mirroring Devin.ai's flexible LLM backend.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LLMConfig:
    """Configuration for a single LLM provider.

    Supports all major providers that Devin.ai integrates with:
    OpenAI (GPT-4/4o/o1), Anthropic (Claude), Google (Gemini),
    AWS Bedrock, and local models via Ollama.

    Attributes:
        model: Model identifier (e.g., 'gpt-4o', 'claude-3-opus').
        api_key: API key for the provider.
        base_url: Custom API endpoint URL.
        max_tokens: Maximum tokens in the response.
        temperature: Sampling temperature (0.0 - 2.0).
        top_p: Nucleus sampling parameter.
        num_retries: Number of retry attempts on failure.
        retry_multiplier: Exponential backoff multiplier.
        retry_min_wait: Minimum seconds between retries.
        retry_max_wait: Maximum seconds between retries.
        timeout: Request timeout in seconds.
        max_input_tokens: Maximum input context tokens.
        cost_per_input_token: Cost tracking per input token.
        cost_per_output_token: Cost tracking per output token.
        supports_vision: Whether the model supports image inputs.
        supports_function_calling: Whether the model supports tool use.
        caching_prompt: Whether to use prompt caching (Anthropic).
    """

    model: str = "gpt-4o"
    api_key: str = ""
    base_url: str = ""
    max_tokens: int = 4096
    temperature: float = 0.0
    top_p: float = 1.0
    num_retries: int = 8
    retry_multiplier: float = 2.0
    retry_min_wait: float = 15.0
    retry_max_wait: float = 120.0
    timeout: int = 600
    max_input_tokens: int = 128000
    cost_per_input_token: float = 0.0
    cost_per_output_token: float = 0.0
    supports_vision: bool = True
    supports_function_calling: bool = True
    caching_prompt: bool = False
    custom_llm_provider: str = ""
    embedding_model: str = ""

    def get_provider(self) -> str:
        """Extract the provider name from the model string."""
        if self.custom_llm_provider:
            return self.custom_llm_provider
        if "/" in self.model:
            return self.model.split("/")[0]
        return "openai"
