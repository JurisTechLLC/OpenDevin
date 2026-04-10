"""Agent controller module for OttoSoftwareEngineer.

Contains the core agent orchestration engine that manages the execution
loop, state machine, planning, stuck detection, and delegation.

Mirrors the Devin.ai agent controller architecture:
- AgentController: Main execution loop and state machine
- StuckDetector: Detect and recover from infinite loops
- Planner: Interactive planning (Devin 2.0)
- State: Session state tracking and persistence
"""

from OttoSoftwareEngineer.controller.agent_controller import AgentController
from OttoSoftwareEngineer.controller.state import State
from OttoSoftwareEngineer.controller.stuck_detector import StuckDetector
from OttoSoftwareEngineer.controller.planner import Planner

__all__ = [
    "AgentController",
    "State",
    "StuckDetector",
    "Planner",
]
