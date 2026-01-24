"""
JurisTech OpenHands Extension - Supervisor AI Configuration
Defines configuration classes for supervisor AI instances.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import json
from pathlib import Path


class SupervisorType(Enum):
    """Types of supervisor AIs available."""
    GENERAL = "general"  # General purpose supervisor for maintaining vision/goals
    ARCHITECTURE = "architecture"  # Focuses on code architecture and design patterns
    SECURITY = "security"  # Focuses on security risks and vulnerabilities
    PERFORMANCE = "performance"  # Focuses on performance optimization
    TESTING = "testing"  # Focuses on test coverage and quality
    CUSTOM = "custom"  # User-defined supervisor type


@dataclass
class SupervisorConfig:
    """Configuration for a single supervisor AI instance."""
    
    # Unique identifier for this supervisor
    id: str
    
    # Display name shown in UI
    name: str
    
    # Type of supervisor
    supervisor_type: SupervisorType
    
    # Model configuration
    model_name: str = "anthropic/claude-opus-4-5-20251101"
    model_provider: str = "anthropic"
    model_base_url: Optional[str] = None
    api_key_env: str = "ANTHROPIC_API_KEY"
    
    # Temperature for responses (lower = more focused)
    temperature: float = 0.3
    
    # Maximum tokens for supervisor responses
    max_tokens: int = 2048
    
    # System prompt for this supervisor
    system_prompt: str = ""
    
    # Whether this supervisor is enabled
    enabled: bool = True
    
    # Priority order (lower = responds first)
    priority: int = 0
    
    # Whether to auto-generate system prompt based on type
    auto_generate_prompt: bool = True
    
    # Domain-specific focus areas
    focus_areas: List[str] = field(default_factory=list)
    
    # Custom instructions added by user
    custom_instructions: str = ""
    
    # EXPERIMENTAL: Auto-send feature (only for GENERAL supervisor)
    # When enabled, the supervisor can automatically approve and send responses
    # to continue the programming flow without human intervention
    auto_send_enabled: bool = False
    
    # Confidence threshold for auto-send (0.0 to 1.0)
    # Only auto-send if supervisor confidence is above this threshold
    auto_send_confidence_threshold: float = 0.8
    
    # Maximum consecutive auto-sends before requiring human review
    auto_send_max_consecutive: int = 5
    
    # Keywords that will always require human review (never auto-send)
    auto_send_stop_keywords: List[str] = field(default_factory=lambda: [
        "delete", "remove", "drop", "truncate", "destroy",
        "security", "credential", "password", "secret", "key",
        "production", "deploy", "release", "publish"
    ])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "supervisor_type": self.supervisor_type.value,
            "model_name": self.model_name,
            "model_provider": self.model_provider,
            "model_base_url": self.model_base_url,
            "api_key_env": self.api_key_env,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "system_prompt": self.system_prompt,
            "enabled": self.enabled,
            "priority": self.priority,
            "auto_generate_prompt": self.auto_generate_prompt,
            "focus_areas": self.focus_areas,
            "custom_instructions": self.custom_instructions,
            "auto_send_enabled": self.auto_send_enabled,
            "auto_send_confidence_threshold": self.auto_send_confidence_threshold,
            "auto_send_max_consecutive": self.auto_send_max_consecutive,
            "auto_send_stop_keywords": self.auto_send_stop_keywords
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SupervisorConfig":
        """Create from dictionary."""
        data = data.copy()
        data["supervisor_type"] = SupervisorType(data.get("supervisor_type", "general"))
        return cls(**data)


# Default system prompts for each supervisor type
DEFAULT_SYSTEM_PROMPTS = {
    SupervisorType.GENERAL: """You are a General Supervisor AI for software development. Your role is to:

1. MAINTAIN VISION: Keep track of the overall goals and vision for the project. When the AI agent proposes changes, evaluate whether they align with the stated objectives.

2. PREVENT DRIFT: Watch for signs that the AI agent is drifting from the original requirements or taking shortcuts that compromise quality.

3. PROVIDE PERSPECTIVE: When reviewing agent proposals, offer constructive feedback that helps maintain focus on the end goal.

4. GUIDE DEVELOPMENT: Help the human developer articulate their vision clearly and translate it into actionable requirements.

Your responses should be:
- Concise but thorough
- Focused on alignment with stated goals
- Constructive and actionable
- Aware of the full codebase context (via RAG)

When reviewing agent proposals, structure your response as:
[ALIGNMENT]: How well does this align with the stated goals?
[CONCERNS]: Any potential issues or shortcuts being taken?
[SUGGESTIONS]: Recommendations for improvement
[VERDICT]: APPROVE / NEEDS_REVISION / REJECT""",

    SupervisorType.ARCHITECTURE: """You are an Architecture Supervisor AI. Your role is to:

1. MAINTAIN ARCHITECTURAL INTEGRITY: Ensure code changes follow established patterns and don't introduce architectural debt.

2. REVIEW DESIGN DECISIONS: Evaluate whether proposed changes follow SOLID principles, maintain separation of concerns, and use appropriate design patterns.

3. PREVENT ANTI-PATTERNS: Watch for code smells, tight coupling, and violations of the project's architectural guidelines.

4. GUIDE REFACTORING: When architecture improvements are needed, provide clear guidance on how to restructure code.

When reviewing agent proposals, structure your response as:
[ARCHITECTURE]: Does this follow the project's architectural patterns?
[DESIGN]: Are design patterns used appropriately?
[COUPLING]: Are there concerns about tight coupling or dependencies?
[SUGGESTIONS]: Architectural improvements recommended
[VERDICT]: APPROVE / NEEDS_REVISION / REJECT""",

    SupervisorType.SECURITY: """You are a Security Supervisor AI. Your role is to:

1. IDENTIFY VULNERABILITIES: Watch for security issues like injection attacks, authentication bypasses, data exposure, etc.

2. ENFORCE SECURITY PRACTICES: Ensure code follows security best practices (input validation, output encoding, secure defaults).

3. PROTECT SENSITIVE DATA: Watch for improper handling of credentials, PII, or other sensitive information.

4. COMPLIANCE AWARENESS: Consider regulatory requirements (GDPR, HIPAA, SOC2) when reviewing changes.

When reviewing agent proposals, structure your response as:
[VULNERABILITIES]: Any security vulnerabilities identified?
[DATA_HANDLING]: Are sensitive data handled properly?
[AUTHENTICATION]: Are auth/authz concerns addressed?
[COMPLIANCE]: Any compliance considerations?
[VERDICT]: APPROVE / NEEDS_REVISION / REJECT""",

    SupervisorType.PERFORMANCE: """You are a Performance Supervisor AI. Your role is to:

1. IDENTIFY BOTTLENECKS: Watch for code that could cause performance issues (N+1 queries, memory leaks, etc.).

2. OPTIMIZE EFFICIENCY: Suggest improvements for algorithmic complexity and resource usage.

3. SCALABILITY: Consider how changes will perform at scale.

4. RESOURCE MANAGEMENT: Watch for proper cleanup of resources, connections, and memory.

When reviewing agent proposals, structure your response as:
[COMPLEXITY]: Time/space complexity concerns?
[SCALABILITY]: Will this scale appropriately?
[RESOURCES]: Are resources managed properly?
[SUGGESTIONS]: Performance improvements recommended
[VERDICT]: APPROVE / NEEDS_REVISION / REJECT""",

    SupervisorType.TESTING: """You are a Testing Supervisor AI. Your role is to:

1. TEST COVERAGE: Ensure adequate test coverage for new and modified code.

2. TEST QUALITY: Review test cases for completeness, edge cases, and meaningful assertions.

3. TESTABILITY: Ensure code is written in a testable manner (dependency injection, mockable interfaces).

4. REGRESSION PREVENTION: Watch for changes that could break existing functionality.

When reviewing agent proposals, structure your response as:
[COVERAGE]: Is test coverage adequate?
[EDGE_CASES]: Are edge cases covered?
[TESTABILITY]: Is the code testable?
[REGRESSIONS]: Risk of breaking existing tests?
[VERDICT]: APPROVE / NEEDS_REVISION / REJECT""",

    SupervisorType.CUSTOM: """You are a Custom Supervisor AI. Your specific role and focus areas will be defined by the user's custom instructions.

When reviewing agent proposals, provide structured feedback based on your configured focus areas."""
}


@dataclass
class SupervisorsConfig:
    """Configuration for all supervisor AI instances."""
    
    # List of supervisor configurations
    supervisors: List[SupervisorConfig] = field(default_factory=list)
    
    # Global settings
    enabled: bool = True
    
    # Whether to show supervisor responses in a separate panel
    show_in_panel: bool = True
    
    # Whether to auto-insert supervisor response into chat (without sending)
    auto_insert_response: bool = True
    
    # RAG settings
    rag_enabled: bool = True
    rag_index_path: str = "~/.juristech-openhands/rag_index"
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 200
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "supervisors": [s.to_dict() for s in self.supervisors],
            "enabled": self.enabled,
            "show_in_panel": self.show_in_panel,
            "auto_insert_response": self.auto_insert_response,
            "rag_enabled": self.rag_enabled,
            "rag_index_path": self.rag_index_path,
            "rag_chunk_size": self.rag_chunk_size,
            "rag_chunk_overlap": self.rag_chunk_overlap
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SupervisorsConfig":
        """Create from dictionary."""
        supervisors = [SupervisorConfig.from_dict(s) for s in data.get("supervisors", [])]
        return cls(
            supervisors=supervisors,
            enabled=data.get("enabled", True),
            show_in_panel=data.get("show_in_panel", True),
            auto_insert_response=data.get("auto_insert_response", True),
            rag_enabled=data.get("rag_enabled", True),
            rag_index_path=data.get("rag_index_path", "~/.juristech-openhands/rag_index"),
            rag_chunk_size=data.get("rag_chunk_size", 1000),
            rag_chunk_overlap=data.get("rag_chunk_overlap", 200)
        )
    
    def get_enabled_supervisors(self) -> List[SupervisorConfig]:
        """Get list of enabled supervisors sorted by priority."""
        return sorted(
            [s for s in self.supervisors if s.enabled],
            key=lambda x: x.priority
        )
    
    def add_supervisor(self, supervisor: SupervisorConfig) -> None:
        """Add a new supervisor."""
        self.supervisors.append(supervisor)
    
    def remove_supervisor(self, supervisor_id: str) -> bool:
        """Remove a supervisor by ID."""
        for i, s in enumerate(self.supervisors):
            if s.id == supervisor_id:
                self.supervisors.pop(i)
                return True
        return False
    
    def get_supervisor(self, supervisor_id: str) -> Optional[SupervisorConfig]:
        """Get a supervisor by ID."""
        for s in self.supervisors:
            if s.id == supervisor_id:
                return s
        return None


def create_default_general_supervisor() -> SupervisorConfig:
    """Create a default general supervisor configuration."""
    return SupervisorConfig(
        id="general-supervisor",
        name="General Supervisor",
        supervisor_type=SupervisorType.GENERAL,
        model_name="anthropic/claude-opus-4-5-20251101",
        model_provider="anthropic",
        api_key_env="ANTHROPIC_API_KEY",
        temperature=0.3,
        max_tokens=2048,
        system_prompt=DEFAULT_SYSTEM_PROMPTS[SupervisorType.GENERAL],
        enabled=True,
        priority=0,
        auto_generate_prompt=True,
        focus_areas=["vision alignment", "goal tracking", "quality assurance"],
        custom_instructions=""
    )


def get_default_supervisors_config() -> SupervisorsConfig:
    """Get default supervisors configuration with general supervisor."""
    return SupervisorsConfig(
        supervisors=[create_default_general_supervisor()],
        enabled=True,
        show_in_panel=True,
        auto_insert_response=True,
        rag_enabled=True,
        rag_index_path="~/.juristech-openhands/rag_index",
        rag_chunk_size=1000,
        rag_chunk_overlap=200
    )
