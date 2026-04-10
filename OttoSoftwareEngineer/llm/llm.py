"""LLM wrapper for OttoSoftwareEngineer.

Provides a unified interface to multiple LLM providers with automatic
retry logic, cost tracking, and message formatting. This mirrors the
Devin.ai approach of supporting multiple providers through a single
abstraction layer.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from OttoSoftwareEngineer.config.llm_config import LLMConfig
from OttoSoftwareEngineer.llm.metrics import LLMCallMetric, LLMMetrics
from OttoSoftwareEngineer.llm.model_features import ModelFeatures, get_features

logger = logging.getLogger(__name__)


class LLM:
    """Unified LLM interface for the Otto system.

    Wraps LLM provider APIs with:
    - Automatic retry with exponential backoff
    - Cost and token tracking
    - Model-specific message formatting
    - Vision/function calling capability detection

    This is the primary interface through which agents communicate
    with language models, mirroring Devin.ai's LLM integration layer.

    Attributes:
        config: LLM provider configuration.
        metrics: Aggregated usage metrics.
        features: Model capability flags.
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize the LLM wrapper.

        Args:
            config: Configuration for the LLM provider.
        """
        self.config = config
        self.metrics = LLMMetrics()
        self.features: ModelFeatures = get_features(config.model)
        self._retry_count = 0

    async def completion(
        self,
        messages: list[dict[str, Any]],
        functions: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> dict[str, Any]:
        """Send a completion request to the LLM.

        Handles retries, cost tracking, and message formatting
        based on model capabilities.

        Args:
            messages: List of message dicts (role, content).
            functions: Optional function/tool definitions.
            temperature: Override sampling temperature.
            max_tokens: Override max output tokens.
            stop: Override stop sequences.

        Returns:
            The LLM response as a dictionary containing:
            - content: The text response
            - function_call: Any function call (if applicable)
            - usage: Token usage information

        Raises:
            Exception: If all retry attempts fail.
        """
        start_time = time.time()

        # Format messages based on model capabilities
        formatted_messages = self._format_messages(messages)

        # Build request parameters
        params: dict[str, Any] = {
            "model": self.config.model,
            "messages": formatted_messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
        }

        if functions and self.features.supports_function_calling:
            params["functions"] = functions

        if stop:
            params["stop"] = stop
        elif self.features.stop_words:
            params["stop"] = self.features.stop_words

        # Execute with retry logic
        response = await self._execute_with_retry(params)

        # Record metrics
        latency = time.time() - start_time
        usage = response.get("usage", {})
        metric = LLMCallMetric(
            model=self.config.model,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            cached_tokens=usage.get("cached_tokens", 0),
            cost=self._calculate_cost(usage),
            latency=latency,
        )
        self.metrics.record_call(metric)

        return response

    def _format_messages(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Format messages based on model capabilities.

        Handles vision content, prompt caching markers, and
        provider-specific formatting requirements.

        Args:
            messages: Raw messages to format.

        Returns:
            Formatted messages suitable for the model.
        """
        formatted = []
        for msg in messages:
            formatted_msg = {"role": msg.get("role", "user")}

            content = msg.get("content", "")

            # Handle vision content
            if isinstance(content, list) and self.features.supports_vision:
                formatted_msg["content"] = content
            elif isinstance(content, list):
                # Strip images for non-vision models
                text_parts = [
                    p.get("text", "")
                    for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                formatted_msg["content"] = "\n".join(text_parts)
            else:
                formatted_msg["content"] = content

            formatted.append(formatted_msg)
        return formatted

    async def _execute_with_retry(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute an LLM request with exponential backoff retry.

        Args:
            params: The request parameters.

        Returns:
            The LLM response dictionary.

        Raises:
            Exception: If all retries are exhausted.
        """
        last_error: Exception | None = None
        wait_time = self.config.retry_min_wait

        for attempt in range(self.config.num_retries + 1):
            try:
                return await self._call_provider(params)
            except Exception as e:
                last_error = e
                if attempt < self.config.num_retries:
                    logger.warning(
                        "LLM call failed (attempt %d/%d): %s. "
                        "Retrying in %.1fs...",
                        attempt + 1,
                        self.config.num_retries + 1,
                        str(e),
                        wait_time,
                    )
                    import asyncio

                    await asyncio.sleep(wait_time)
                    wait_time = min(
                        wait_time * self.config.retry_multiplier,
                        self.config.retry_max_wait,
                    )

        raise last_error or Exception("LLM call failed after all retries")

    async def _call_provider(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Call the LLM provider API.

        This is a template method that should be overridden by
        provider-specific implementations. The default returns
        a placeholder response for development/testing.

        Args:
            params: The request parameters.

        Returns:
            The provider's response.
        """
        # Placeholder implementation - in production, this would call
        # litellm.acompletion() or a provider-specific SDK
        logger.debug(
            "LLM call to %s with %d messages",
            params.get("model", "unknown"),
            len(params.get("messages", [])),
        )

        return {
            "content": "",
            "function_call": None,
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cached_tokens": 0,
            },
        }

    def _calculate_cost(self, usage: dict[str, int]) -> float:
        """Calculate the cost of an LLM call based on token usage.

        Args:
            usage: Token usage dictionary from the provider.

        Returns:
            Estimated cost in USD.
        """
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        cost = (
            input_tokens * self.config.cost_per_input_token
            + output_tokens * self.config.cost_per_output_token
        )
        return cost

    def get_token_count(self, text: str) -> int:
        """Estimate the token count for a text string.

        Args:
            text: The text to count tokens for.

        Returns:
            Estimated token count.
        """
        # Simple estimation: ~4 characters per token
        return len(text) // 4

    @property
    def model_name(self) -> str:
        """The model identifier being used."""
        return self.config.model
