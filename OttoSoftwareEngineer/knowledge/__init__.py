"""Knowledge system for OttoSoftwareEngineer.

Provides persistent knowledge management capabilities:
- Playbooks: Reusable step-by-step task procedures
- Knowledge notes: Persistent information store
- Skills: Repository-specific instructions
- Microagents: Repo-specific agent behavior customization

Mirrors Devin.ai's knowledge management features including
Devin Wiki, playbooks, and skills loaded from repositories.
"""

from OttoSoftwareEngineer.knowledge.playbook import Playbook, PlaybookManager
from OttoSoftwareEngineer.knowledge.knowledge_store import (
    KnowledgeNote,
    KnowledgeStore,
)
from OttoSoftwareEngineer.knowledge.skill import Skill, SkillManager
from OttoSoftwareEngineer.knowledge.microagent import Microagent, MicroagentLoader

__all__ = [
    "Playbook",
    "PlaybookManager",
    "KnowledgeNote",
    "KnowledgeStore",
    "Skill",
    "SkillManager",
    "Microagent",
    "MicroagentLoader",
]
