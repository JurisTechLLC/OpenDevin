"""Search tool for OttoSoftwareEngineer.

Provides codebase search capabilities within the sandbox, mirroring
Devin.ai's Devin Search feature for exploring and understanding codebases.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from OttoSoftwareEngineer.runtime.tools.base import Tool, ToolResult


class SearchTool(Tool):
    """Codebase search tool using ripgrep and glob patterns.

    Enables the agent to efficiently search through codebases:
    - Content search (grep/ripgrep) with regex support
    - File name search (glob patterns)
    - Symbol search (LSP-based)

    Mirrors Devin.ai's Devin Search feature that provides
    context-aware codebase exploration.

    Attributes:
        workspace_dir: Root directory for search operations.
    """

    name = "search"
    description = "Search through code using regex patterns and glob matching"

    def __init__(self, workspace_dir: str = "/workspace") -> None:
        """Initialize the SearchTool.

        Args:
            workspace_dir: Root directory for searches.
        """
        self.workspace_dir = Path(workspace_dir)

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a search operation.

        Args:
            **kwargs: Search parameters including:
                action: Search type ('grep', 'glob', 'symbol').
                pattern: Search pattern (regex for grep, glob for glob).
                path: Directory to search in (relative to workspace).
                file_type: Filter by file type (e.g., 'py', 'js').
                max_results: Maximum number of results to return.

        Returns:
            Search results.
        """
        action = kwargs.get("action", "grep")
        pattern = kwargs.get("pattern", "")

        if not pattern:
            return ToolResult(success=False, error="No search pattern provided")

        if action == "grep":
            return self._grep(
                pattern,
                kwargs.get("path", "."),
                kwargs.get("file_type", ""),
                kwargs.get("max_results", 50),
            )
        elif action == "glob":
            return self._glob(
                pattern,
                kwargs.get("path", "."),
                kwargs.get("max_results", 50),
            )
        else:
            return ToolResult(
                success=False, error=f"Unknown search action: {action}"
            )

    def _grep(
        self,
        pattern: str,
        path: str,
        file_type: str,
        max_results: int,
    ) -> ToolResult:
        """Search file contents using ripgrep."""
        search_dir = self._resolve_path(path)

        cmd = ["rg", "--max-count", str(max_results), "-n"]
        if file_type:
            cmd.extend(["--type", file_type])
        cmd.extend([pattern, str(search_dir)])

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            return ToolResult(
                success=True,
                output=result.stdout or "No matches found",
                metadata={
                    "pattern": pattern,
                    "action": "grep",
                    "match_count": result.stdout.count("\n"),
                },
            )
        except FileNotFoundError:
            # Fallback to grep if rg not available
            cmd = ["grep", "-rn", f"--max-count={max_results}", pattern, str(search_dir)]
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=30
                )
                return ToolResult(
                    success=True,
                    output=result.stdout or "No matches found",
                    metadata={"pattern": pattern, "action": "grep"},
                )
            except Exception as e:
                return ToolResult(success=False, error=str(e))
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, error="Search timed out after 30s"
            )

    def _glob(
        self, pattern: str, path: str, max_results: int
    ) -> ToolResult:
        """Search for files by name pattern."""
        search_dir = self._resolve_path(path)
        try:
            matches = sorted(search_dir.glob(pattern))[:max_results]
            output = "\n".join(str(m.relative_to(search_dir)) for m in matches)
            return ToolResult(
                success=True,
                output=output or "No matching files found",
                metadata={
                    "pattern": pattern,
                    "action": "glob",
                    "match_count": len(matches),
                },
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
        """Get the JSON schema for search tool parameters."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["grep", "glob"],
                        "description": "Search type",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search in",
                    },
                    "file_type": {
                        "type": "string",
                        "description": "Filter by file type",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results to return",
                    },
                },
                "required": ["action", "pattern"],
            },
        }
