"""Tool interfaces for OttoSoftwareEngineer.

Defines the abstract tool interfaces available in the sandbox:
- ShellTool: Execute bash commands
- BrowserTool: Web browsing via CDP
- EditorTool: File editing and navigation
- SearchTool: Codebase search (grep, glob)

Mirrors Devin.ai's tool system where the agent has access to
shell, browser, code editor, and search within its sandbox.
"""

from OttoSoftwareEngineer.runtime.tools.base import Tool
from OttoSoftwareEngineer.runtime.tools.shell import ShellTool
from OttoSoftwareEngineer.runtime.tools.browser import BrowserTool
from OttoSoftwareEngineer.runtime.tools.editor import EditorTool
from OttoSoftwareEngineer.runtime.tools.search import SearchTool

__all__ = [
    "Tool",
    "ShellTool",
    "BrowserTool",
    "EditorTool",
    "SearchTool",
]
