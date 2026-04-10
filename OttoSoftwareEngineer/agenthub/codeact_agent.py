"""CodeAct Agent for OttoSoftwareEngineer.

The primary agent implementation using the ReAct (Reasoning + Acting)
pattern with code-based actions. This mirrors the Devin.ai agent
architecture where the agent:

1. Observes the current state (conversation history, tool outputs)
2. Thinks about what to do next (LLM reasoning)
3. Acts by calling tools (shell, editor, browser, etc.)
4. Observes the result and repeats

The CodeAct agent formats all tool interactions as structured actions
and uses the LLM to decide which tool to use and with what parameters.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from OttoSoftwareEngineer.agenthub.base_agent import BaseAgent
from OttoSoftwareEngineer.core.events.actions import (
    Action,
    AgentFinishAction,
    AgentThinkAction,
    CmdRunAction,
    FileEditAction,
    FileReadAction,
    FileWriteAction,
    MessageAction,
    NullAction,
)
from OttoSoftwareEngineer.core.schema.agent import AgentState

if TYPE_CHECKING:
    from OttoSoftwareEngineer.config import AgentConfig
    from OttoSoftwareEngineer.controller.state import State
    from OttoSoftwareEngineer.llm.llm import LLM

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Otto, an autonomous AI software engineer.

You have access to the following tools in your sandbox environment:
- **Shell**: Execute bash commands (build, test, git, etc.)
- **Editor**: Read, write, and edit files
- **Browser**: Navigate web pages and interact with them
- **Search**: Search through codebases using regex and glob patterns
- **IPython**: Execute Python code in a Jupyter kernel

## Core Principles
1. **Plan before acting**: Analyze the task, understand the codebase, then execute
2. **Be thorough**: Complete the full task, don't stop early
3. **Test your work**: Run tests and verify your changes work
4. **Communicate clearly**: Keep the user informed of progress
5. **Handle errors gracefully**: When something fails, try alternative approaches

## Workflow
1. Understand the user's request
2. Explore the codebase to understand the context
3. Create a plan
4. Implement changes step by step
5. Test the implementation
6. Report results

When you have completed the task, use the finish action to signal completion.
When you need user input, ask a clear question and wait for a response.
"""


class CodeActAgent(BaseAgent):
    """Primary agent using ReAct pattern with code actions.

    The CodeActAgent is the main agent implementation that mirrors
    Devin.ai's core agent loop:

    1. Format conversation history as LLM messages
    2. Send to LLM with tool definitions
    3. Parse the LLM response into an action
    4. Return the action for runtime execution

    The agent maintains the full conversation context and uses
    function calling to interact with the sandbox tools.

    Attributes:
        llm: The LLM for reasoning.
        system_prompt: The system prompt defining agent behavior.
    """

    def __init__(
        self,
        llm: LLM,
        config: AgentConfig | None = None,
    ) -> None:
        """Initialize the CodeActAgent.

        Args:
            llm: The LLM instance for reasoning.
            config: Agent behavior configuration.
        """
        super().__init__(llm, config)
        self.system_prompt = SYSTEM_PROMPT

    def step(self, state: State) -> Action:
        """Decide the next action based on current state.

        Implements the ReAct loop:
        1. Build messages from state history
        2. Call LLM with tool definitions
        3. Parse response into an action
        4. Return the action

        Args:
            state: Current session state.

        Returns:
            The next action to execute.
        """
        # Check for terminal conditions
        if state.agent_state in AgentState.terminal_states():
            return AgentFinishAction(thought="Session is in terminal state")

        # Build messages for the LLM
        messages = self._build_messages(state)

        # Get tool definitions
        tools = self._get_tool_definitions()

        # Call LLM (synchronous wrapper for the step method)
        try:
            import asyncio

            response = asyncio.get_event_loop().run_until_complete(
                self.llm.completion(messages=messages, functions=tools)
            )
        except Exception as e:
            logger.error("LLM call failed: %s", str(e))
            return AgentThinkAction(
                thought=f"LLM call failed: {str(e)}. Will retry."
            )

        # Parse response into action
        action = self._parse_response(response)
        return action

    def get_system_prompt(self) -> str:
        """Get the system prompt for the CodeAct agent.

        Returns:
            The system prompt string.
        """
        return self.system_prompt

    def _build_messages(
        self, state: State
    ) -> list[dict[str, Any]]:
        """Build LLM messages from the session state.

        Converts the action/observation history into a format
        suitable for the LLM API.

        Args:
            state: Current session state.

        Returns:
            List of message dictionaries.
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]

        # Add plan context if available
        plan_summary = state.get_plan_summary()
        if plan_summary != "No plan defined.":
            messages.append(
                {
                    "role": "system",
                    "content": f"Current plan:\n{plan_summary}",
                }
            )

        # Convert history to messages
        for event_data in state.history:
            msg = self._event_to_message(event_data)
            if msg:
                messages.append(msg)

        return messages

    def _event_to_message(
        self, event_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Convert an event dictionary to an LLM message.

        Args:
            event_data: Event data from the state history.

        Returns:
            Message dictionary, or None if not applicable.
        """
        action_type = event_data.get("action_type")
        observation_type = event_data.get("observation_type")
        content = event_data.get("content", "")

        if action_type == "message":
            source = event_data.get("_source", "user")
            role = "user" if source == "user" else "assistant"
            return {"role": role, "content": content}

        if action_type == "cmd_run":
            command = event_data.get("command", "")
            return {
                "role": "assistant",
                "content": f"Running command: {command}",
            }

        if observation_type == "cmd_output":
            command = event_data.get("command", "")
            exit_code = event_data.get("exit_code", 0)
            return {
                "role": "user",
                "content": (
                    f"Command output (exit code {exit_code}):\n"
                    f"$ {command}\n{content}"
                ),
            }

        if observation_type == "error":
            return {
                "role": "user",
                "content": f"Error: {content}",
            }

        if action_type == "agent_think":
            thought = event_data.get("thought", content)
            return {"role": "assistant", "content": thought}

        if observation_type in ("file_read", "file_write", "file_edit"):
            path = event_data.get("path", "")
            return {
                "role": "user",
                "content": f"File operation on {path}: {content[:500]}",
            }

        return None

    def _get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get function/tool definitions for the LLM.

        Returns:
            List of tool definition dictionaries.
        """
        return [
            {
                "name": "shell",
                "description": "Execute a bash command in the sandbox",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The bash command to execute",
                        }
                    },
                    "required": ["command"],
                },
            },
            {
                "name": "read_file",
                "description": "Read the contents of a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file",
                        }
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "write_file",
                "description": "Write content to a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file",
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write",
                        },
                    },
                    "required": ["path", "content"],
                },
            },
            {
                "name": "edit_file",
                "description": "Apply a find-and-replace edit to a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file",
                        },
                        "old_text": {
                            "type": "string",
                            "description": "Text to find",
                        },
                        "new_text": {
                            "type": "string",
                            "description": "Replacement text",
                        },
                    },
                    "required": ["path", "old_text", "new_text"],
                },
            },
            {
                "name": "finish",
                "description": "Signal that the task is complete",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "thought": {
                            "type": "string",
                            "description": "Summary of what was accomplished",
                        }
                    },
                    "required": ["thought"],
                },
            },
        ]

    def _parse_response(self, response: dict[str, Any]) -> Action:
        """Parse an LLM response into an action.

        Handles both text responses and function call responses.

        Args:
            response: The LLM response dictionary.

        Returns:
            The parsed Action.
        """
        # Check for function call
        function_call = response.get("function_call")
        if function_call:
            return self._parse_function_call(function_call)

        # Plain text response - treat as message
        content = response.get("content", "")
        if content:
            return MessageAction(content=content)

        return NullAction()

    def _parse_function_call(
        self, function_call: dict[str, Any]
    ) -> Action:
        """Parse a function call into an action.

        Args:
            function_call: Function call data from the LLM.

        Returns:
            The corresponding Action.
        """
        name = function_call.get("name", "")
        args = function_call.get("arguments", {})

        if isinstance(args, str):
            import json

            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}

        if name == "shell":
            return CmdRunAction(command=args.get("command", ""))

        if name == "read_file":
            return FileReadAction(path=args.get("path", ""))

        if name == "write_file":
            return FileWriteAction(
                path=args.get("path", ""),
                content=args.get("content", ""),
            )

        if name == "edit_file":
            return FileEditAction(
                path=args.get("path", ""),
                old_text=args.get("old_text", ""),
                new_text=args.get("new_text", ""),
            )

        if name == "finish":
            return AgentFinishAction(thought=args.get("thought", ""))

        logger.warning("Unknown function call: %s", name)
        return NullAction()


# Register the CodeActAgent
BaseAgent.register("CodeActAgent", CodeActAgent)
