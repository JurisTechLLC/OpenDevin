"""LLM integration layer for OttoSoftwareEngineer.

Provides a unified interface to multiple LLM providers, with retry logic,
cost tracking, token counting, and model capability detection.

Mirrors Devin.ai's flexible LLM backend supporting OpenAI, Anthropic,
Google, AWS Bedrock, and local models.
"""

from OttoSoftwareEngineer.llm.llm import LLM
from OttoSoftwareEngineer.llm.metrics import LLMMetrics
from OttoSoftwareEngineer.llm.model_features import ModelFeatures

__all__ = [
    "LLM",
    "LLMMetrics",
    "ModelFeatures",
]
