"""LLM metrics tracking for OttoSoftwareEngineer.

Tracks cost, latency, and token usage across LLM calls,
enabling budget enforcement and usage analytics.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class LLMCallMetric:
    """Metrics from a single LLM API call.

    Attributes:
        model: Model identifier used.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        cached_tokens: Number of cached/reused tokens.
        cost: Estimated cost in USD.
        latency: Request duration in seconds.
        timestamp: Unix timestamp of the call.
    """

    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost: float = 0.0
    latency: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class LLMMetrics:
    """Aggregated metrics across all LLM calls in a session.

    Provides session-level cost tracking similar to Devin.ai's
    ACU (Agent Compute Unit) metering.

    Attributes:
        calls: List of individual call metrics.
        total_cost: Sum of all call costs.
        total_input_tokens: Sum of all input tokens.
        total_output_tokens: Sum of all output tokens.
        total_cached_tokens: Sum of all cached tokens.
    """

    calls: list[LLMCallMetric] = field(default_factory=list)
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cached_tokens: int = 0

    def record_call(self, metric: LLMCallMetric) -> None:
        """Record metrics from an LLM call.

        Args:
            metric: The call metrics to record.
        """
        self.calls.append(metric)
        self.total_cost += metric.cost
        self.total_input_tokens += metric.input_tokens
        self.total_output_tokens += metric.output_tokens
        self.total_cached_tokens += metric.cached_tokens

    @property
    def total_calls(self) -> int:
        """Total number of LLM API calls made."""
        return len(self.calls)

    @property
    def average_latency(self) -> float:
        """Average latency across all calls in seconds."""
        if not self.calls:
            return 0.0
        return sum(c.latency for c in self.calls) / len(self.calls)

    def get_summary(self) -> dict[str, float | int]:
        """Get a summary of metrics for display."""
        return {
            "total_calls": self.total_calls,
            "total_cost_usd": round(self.total_cost, 4),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cached_tokens": self.total_cached_tokens,
            "average_latency_s": round(self.average_latency, 3),
        }
