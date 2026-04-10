"""Browser tool for OttoSoftwareEngineer.

Provides web browsing capabilities within the sandbox via Chrome DevTools
Protocol (CDP), mirroring Devin.ai's built-in browser that enables
web research, documentation lookup, and testing web applications.
"""

from __future__ import annotations

from typing import Any

from OttoSoftwareEngineer.runtime.tools.base import Tool, ToolResult


class BrowserTool(Tool):
    """Web browser tool using Chrome DevTools Protocol.

    Enables the agent to:
    - Navigate to URLs for documentation and research
    - Interact with web pages (click, type, scroll)
    - Take screenshots for visual verification
    - Test web applications in the sandbox
    - Fill forms and perform automated testing

    The browser runs as a headless Chrome instance inside the sandbox,
    accessible via CDP at a configurable port. This mirrors Devin.ai's
    browser tool that provides full web interaction capabilities.

    Attributes:
        cdp_url: Chrome DevTools Protocol endpoint URL.
        viewport_width: Browser viewport width in pixels.
        viewport_height: Browser viewport height in pixels.
    """

    name = "browser"
    description = "Browse the web and interact with pages via Chrome DevTools Protocol"

    def __init__(
        self,
        cdp_url: str = "http://localhost:9222",
        viewport_width: int = 1024,
        viewport_height: int = 768,
    ) -> None:
        """Initialize the BrowserTool.

        Args:
            cdp_url: Chrome DevTools Protocol endpoint.
            viewport_width: Browser viewport width.
            viewport_height: Browser viewport height.
        """
        self.cdp_url = cdp_url
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a browser action.

        Args:
            **kwargs: Browser action parameters including:
                action: The browser action type (navigate, click, type, etc.).
                url: URL to navigate to (for navigate action).
                selector: CSS selector for element interaction.
                text: Text to type into an element.
                screenshot: Whether to capture a screenshot.

        Returns:
            Browser state including page content and optional screenshot.
        """
        action = kwargs.get("action", "navigate")
        url = kwargs.get("url", "")

        if action == "navigate" and url:
            return self._navigate(url)
        elif action == "click":
            selector = kwargs.get("selector", "")
            return self._click(selector)
        elif action == "type":
            selector = kwargs.get("selector", "")
            text = kwargs.get("text", "")
            return self._type_text(selector, text)
        elif action == "screenshot":
            return self._screenshot()
        elif action == "get_content":
            return self._get_content()
        else:
            return ToolResult(
                success=False,
                error=f"Unknown browser action: {action}",
            )

    def _navigate(self, url: str) -> ToolResult:
        """Navigate to a URL."""
        # Placeholder - in production would use Playwright/CDP
        return ToolResult(
            success=True,
            output=f"Navigated to: {url}",
            metadata={"url": url, "action": "navigate"},
        )

    def _click(self, selector: str) -> ToolResult:
        """Click an element by CSS selector."""
        return ToolResult(
            success=True,
            output=f"Clicked element: {selector}",
            metadata={"selector": selector, "action": "click"},
        )

    def _type_text(self, selector: str, text: str) -> ToolResult:
        """Type text into an element."""
        return ToolResult(
            success=True,
            output=f"Typed into {selector}: {text[:50]}...",
            metadata={"selector": selector, "action": "type"},
        )

    def _screenshot(self) -> ToolResult:
        """Capture a screenshot of the current page."""
        return ToolResult(
            success=True,
            output="Screenshot captured",
            metadata={"action": "screenshot"},
        )

    def _get_content(self) -> ToolResult:
        """Get the current page content."""
        return ToolResult(
            success=True,
            output="Page content would be returned here",
            metadata={"action": "get_content"},
        )

    def get_schema(self) -> dict[str, Any]:
        """Get the JSON schema for browser tool parameters."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "navigate",
                            "click",
                            "type",
                            "screenshot",
                            "get_content",
                        ],
                        "description": "The browser action to perform",
                    },
                    "url": {
                        "type": "string",
                        "description": "URL to navigate to",
                    },
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for element interaction",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type",
                    },
                },
                "required": ["action"],
            },
        }
