"""Code editor tool for OttoSoftwareEngineer.

Provides file editing capabilities within the sandbox, mirroring
Devin.ai's built-in code editor that supports reading, writing,
and targeted editing of files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from OttoSoftwareEngineer.runtime.tools.base import Tool, ToolResult


class EditorTool(Tool):
    """File editor tool for reading, writing, and editing code.

    Provides the agent with code editing capabilities similar to
    Devin.ai's IDE integration:
    - Read file contents with line numbers
    - Write new files
    - Apply targeted find-and-replace edits
    - Search within files

    Attributes:
        workspace_dir: Root directory for file operations.
    """

    name = "editor"
    description = "Read, write, and edit files in the workspace"

    def __init__(self, workspace_dir: str = "/workspace") -> None:
        """Initialize the EditorTool.

        Args:
            workspace_dir: Root directory for file operations.
        """
        self.workspace_dir = Path(workspace_dir)

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute an editor action.

        Args:
            **kwargs: Editor action parameters including:
                action: The editor action (read, write, edit, search).
                path: File path (relative to workspace).
                content: Content for write operations.
                old_text: Text to find (for edit action).
                new_text: Replacement text (for edit action).
                start_line: Start line for partial reads.
                end_line: End line for partial reads.

        Returns:
            The result of the editor operation.
        """
        action = kwargs.get("action", "read")

        if action == "read":
            return self._read_file(
                kwargs.get("path", ""),
                kwargs.get("start_line", 0),
                kwargs.get("end_line", -1),
            )
        elif action == "write":
            return self._write_file(
                kwargs.get("path", ""),
                kwargs.get("content", ""),
            )
        elif action == "edit":
            return self._edit_file(
                kwargs.get("path", ""),
                kwargs.get("old_text", ""),
                kwargs.get("new_text", ""),
            )
        else:
            return ToolResult(
                success=False, error=f"Unknown editor action: {action}"
            )

    def _read_file(
        self, path: str, start_line: int = 0, end_line: int = -1
    ) -> ToolResult:
        """Read a file with optional line range."""
        try:
            file_path = self._resolve_path(path)
            content = file_path.read_text()

            if start_line > 0 or end_line > 0:
                lines = content.splitlines(keepends=True)
                start = max(0, start_line)
                end = end_line if end_line > 0 else len(lines)
                content = "".join(lines[start:end])

            return ToolResult(
                success=True,
                output=content,
                metadata={"path": path, "action": "read"},
            )
        except FileNotFoundError:
            return ToolResult(
                success=False, error=f"File not found: {path}"
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _write_file(self, path: str, content: str) -> ToolResult:
        """Write content to a file."""
        try:
            file_path = self._resolve_path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            return ToolResult(
                success=True,
                output=f"File written: {path}",
                metadata={"path": path, "action": "write"},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _edit_file(
        self, path: str, old_text: str, new_text: str
    ) -> ToolResult:
        """Apply a find-and-replace edit to a file."""
        try:
            file_path = self._resolve_path(path)
            content = file_path.read_text()

            if old_text not in content:
                return ToolResult(
                    success=False,
                    error=f"Text not found in {path}: {old_text[:100]}...",
                )

            new_content = content.replace(old_text, new_text, 1)
            file_path.write_text(new_content)

            return ToolResult(
                success=True,
                output=f"File edited: {path}",
                metadata={"path": path, "action": "edit"},
            )
        except FileNotFoundError:
            return ToolResult(
                success=False, error=f"File not found: {path}"
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to the workspace."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.workspace_dir / p

    def get_schema(self) -> dict[str, Any]:
        """Get the JSON schema for editor tool parameters."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "write", "edit"],
                        "description": "The editor action to perform",
                    },
                    "path": {
                        "type": "string",
                        "description": "File path relative to workspace",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content for write operations",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "Text to find for edit",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "Replacement text for edit",
                    },
                },
                "required": ["action", "path"],
            },
        }
