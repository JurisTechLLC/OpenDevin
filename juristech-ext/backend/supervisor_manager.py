"""
JurisTech OpenHands Extension - Supervisor Manager
Manages supervisor AI instances and coordinates their responses.
"""

import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
import httpx

from .supervisor_config import (
    SupervisorConfig,
    SupervisorsConfig,
    SupervisorType,
    DEFAULT_SYSTEM_PROMPTS,
    get_default_supervisors_config,
    create_default_general_supervisor
)
from .rag_manager import RAGManager, get_rag_manager


@dataclass
class SupervisorResponse:
    """Response from a supervisor AI."""
    supervisor_id: str
    supervisor_name: str
    supervisor_type: SupervisorType
    response: str
    verdict: str  # APPROVE, NEEDS_REVISION, REJECT, or empty
    metadata: Dict[str, Any]
    confidence: float = 0.0  # Confidence score for auto-send decisions
    should_auto_send: bool = False  # Whether this response should trigger auto-send


@dataclass
class AutoSendState:
    """Tracks auto-send state for a session."""
    consecutive_auto_sends: int = 0
    last_auto_send_time: float = 0.0
    total_auto_sends: int = 0
    paused: bool = False  # User can pause auto-send


@dataclass
class ConversationContext:
    """Context for supervisor conversation."""
    project_goals: str = ""
    current_task: str = ""
    conversation_history: List[Dict[str, str]] = None
    agent_proposal: str = ""
    relevant_code: str = ""
    
    def __post_init__(self):
        if self.conversation_history is None:
            self.conversation_history = []


class SupervisorManager:
    """
    Manages supervisor AI instances and coordinates their responses.
    """
    
    def __init__(
        self,
        config: Optional[SupervisorsConfig] = None,
        config_path: str = "~/.juristech-openhands/supervisors_config.json"
    ):
        self.config_path = Path(config_path).expanduser()
        self.config = config or self._load_config()
        self._rag_manager: Optional[RAGManager] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        
        # Conversation context per session
        self._contexts: Dict[str, ConversationContext] = {}
        
        # Auto-send state per session
        self._auto_send_states: Dict[str, AutoSendState] = {}
        
        # Callback for auto-send (to be set by the integration layer)
        self._auto_send_callback: Optional[Callable[[str, str], None]] = None
    
    def _load_config(self) -> SupervisorsConfig:
        """Load configuration from file or create default."""
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                data = json.load(f)
                return SupervisorsConfig.from_dict(data)
        return get_default_supervisors_config()
    
    def save_config(self) -> None:
        """Save configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.config.to_dict(), f, indent=2)
    
    def _get_rag_manager(self) -> RAGManager:
        """Get or create RAG manager."""
        if self._rag_manager is None:
            self._rag_manager = get_rag_manager(
                index_path=self.config.rag_index_path,
                chunk_size=self.config.rag_chunk_size,
                chunk_overlap=self.config.rag_chunk_overlap
            )
        return self._rag_manager
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=120.0)
        return self._http_client
    
    def get_context(self, session_id: str) -> ConversationContext:
        """Get or create conversation context for a session."""
        if session_id not in self._contexts:
            self._contexts[session_id] = ConversationContext()
        return self._contexts[session_id]
    
    def update_project_goals(self, session_id: str, goals: str) -> None:
        """Update project goals for a session."""
        context = self.get_context(session_id)
        context.project_goals = goals
    
    def update_current_task(self, session_id: str, task: str) -> None:
        """Update current task for a session."""
        context = self.get_context(session_id)
        context.current_task = task
    
    def add_to_history(
        self,
        session_id: str,
        role: str,
        content: str
    ) -> None:
        """Add message to conversation history."""
        context = self.get_context(session_id)
        context.conversation_history.append({
            "role": role,
            "content": content
        })
        # Keep last 20 messages to avoid context overflow
        if len(context.conversation_history) > 20:
            context.conversation_history = context.conversation_history[-20:]
    
    def get_auto_send_state(self, session_id: str) -> AutoSendState:
        """Get or create auto-send state for a session."""
        if session_id not in self._auto_send_states:
            self._auto_send_states[session_id] = AutoSendState()
        return self._auto_send_states[session_id]
    
    def set_auto_send_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set the callback function for auto-send."""
        self._auto_send_callback = callback
    
    def pause_auto_send(self, session_id: str) -> None:
        """Pause auto-send for a session."""
        state = self.get_auto_send_state(session_id)
        state.paused = True
    
    def resume_auto_send(self, session_id: str) -> None:
        """Resume auto-send for a session."""
        state = self.get_auto_send_state(session_id)
        state.paused = False
        state.consecutive_auto_sends = 0  # Reset counter on resume
    
    def _check_stop_keywords(
        self,
        content: str,
        stop_keywords: List[str]
    ) -> bool:
        """Check if content contains any stop keywords that prevent auto-send."""
        content_lower = content.lower()
        for keyword in stop_keywords:
            if keyword.lower() in content_lower:
                return True
        return False
    
    def _extract_confidence(self, response_text: str) -> float:
        """
        Extract confidence score from supervisor response.
        Looks for patterns like [CONFIDENCE]: 0.85 or confidence: 85%
        """
        import re
        
        # Look for explicit confidence markers
        patterns = [
            r'\[CONFIDENCE\]:\s*([\d.]+)',
            r'confidence:\s*([\d.]+)',
            r'confidence\s*=\s*([\d.]+)',
            r'(\d+)%\s*confident',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response_text, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                # Convert percentage to decimal if needed
                if value > 1:
                    value = value / 100
                return min(1.0, max(0.0, value))
        
        # Infer confidence from verdict
        if "[VERDICT]: APPROVE" in response_text or "VERDICT: APPROVE" in response_text:
            return 0.9
        elif "[VERDICT]: NEEDS_REVISION" in response_text or "VERDICT: NEEDS_REVISION" in response_text:
            return 0.5
        elif "[VERDICT]: REJECT" in response_text or "VERDICT: REJECT" in response_text:
            return 0.2
        
        return 0.5  # Default confidence
    
    def _should_auto_send(
        self,
        session_id: str,
        responses: List["SupervisorResponse"],
        proposal: str
    ) -> bool:
        """
        Determine if auto-send should be triggered.
        
        Auto-send only happens when:
        1. All enabled supervisors have responded
        2. The general supervisor has auto_send_enabled
        3. All responses have APPROVE verdict
        4. Confidence is above threshold
        5. No stop keywords are present
        6. Consecutive auto-sends haven't exceeded max
        7. Auto-send is not paused
        """
        state = self.get_auto_send_state(session_id)
        
        # Check if paused
        if state.paused:
            return False
        
        # Find the general supervisor config
        general_supervisor = None
        for s in self.config.supervisors:
            if s.supervisor_type == SupervisorType.GENERAL and s.enabled:
                general_supervisor = s
                break
        
        if not general_supervisor or not general_supervisor.auto_send_enabled:
            return False
        
        # Check if all enabled supervisors have responded
        enabled_supervisors = self.config.get_enabled_supervisors()
        if len(responses) < len(enabled_supervisors):
            return False
        
        # Check all verdicts are APPROVE
        for response in responses:
            if response.verdict != "APPROVE":
                return False
        
        # Check confidence threshold (use average confidence)
        avg_confidence = sum(r.confidence for r in responses) / len(responses)
        if avg_confidence < general_supervisor.auto_send_confidence_threshold:
            return False
        
        # Check for stop keywords in proposal
        if self._check_stop_keywords(proposal, general_supervisor.auto_send_stop_keywords):
            return False
        
        # Check consecutive auto-sends
        if state.consecutive_auto_sends >= general_supervisor.auto_send_max_consecutive:
            return False
        
        return True
    
    async def _call_anthropic(
        self,
        supervisor: SupervisorConfig,
        messages: List[Dict[str, str]],
        system_prompt: str
    ) -> str:
        """Call Anthropic API for supervisor response."""
        api_key = os.environ.get(supervisor.api_key_env)
        if not api_key:
            raise ValueError(f"API key not found in environment: {supervisor.api_key_env}")
        
        client = await self._get_http_client()
        
        # Build request
        request_data = {
            "model": supervisor.model_name.replace("anthropic/", ""),
            "max_tokens": supervisor.max_tokens,
            "temperature": supervisor.temperature,
            "system": system_prompt,
            "messages": messages
        }
        
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json=request_data
        )
        
        if response.status_code != 200:
            raise Exception(f"Anthropic API error: {response.status_code} - {response.text}")
        
        result = response.json()
        return result["content"][0]["text"]
    
    async def _call_ollama(
        self,
        supervisor: SupervisorConfig,
        messages: List[Dict[str, str]],
        system_prompt: str
    ) -> str:
        """Call Ollama API for supervisor response."""
        base_url = supervisor.model_base_url or "http://localhost:11434"
        client = await self._get_http_client()
        
        # Build messages with system prompt
        ollama_messages = [{"role": "system", "content": system_prompt}]
        ollama_messages.extend(messages)
        
        request_data = {
            "model": supervisor.model_name.replace("ollama/", ""),
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": supervisor.temperature,
                "num_predict": supervisor.max_tokens
            }
        }
        
        response = await client.post(
            f"{base_url}/api/chat",
            json=request_data
        )
        
        if response.status_code != 200:
            raise Exception(f"Ollama API error: {response.status_code} - {response.text}")
        
        result = response.json()
        return result["message"]["content"]
    
    async def _call_supervisor(
        self,
        supervisor: SupervisorConfig,
        messages: List[Dict[str, str]],
        system_prompt: str
    ) -> str:
        """Call supervisor AI based on provider."""
        if supervisor.model_provider == "anthropic":
            return await self._call_anthropic(supervisor, messages, system_prompt)
        elif supervisor.model_provider == "ollama":
            return await self._call_ollama(supervisor, messages, system_prompt)
        else:
            raise ValueError(f"Unsupported provider: {supervisor.model_provider}")
    
    def _build_system_prompt(
        self,
        supervisor: SupervisorConfig,
        context: ConversationContext
    ) -> str:
        """Build system prompt for supervisor."""
        # Start with base prompt
        if supervisor.auto_generate_prompt and not supervisor.system_prompt:
            base_prompt = DEFAULT_SYSTEM_PROMPTS.get(
                supervisor.supervisor_type,
                DEFAULT_SYSTEM_PROMPTS[SupervisorType.GENERAL]
            )
        else:
            base_prompt = supervisor.system_prompt
        
        # Add project context
        prompt_parts = [base_prompt]
        
        if context.project_goals:
            prompt_parts.append(f"\n\n## Project Goals\n{context.project_goals}")
        
        if context.current_task:
            prompt_parts.append(f"\n\n## Current Task\n{context.current_task}")
        
        if supervisor.focus_areas:
            prompt_parts.append(f"\n\n## Focus Areas\n" + "\n".join(f"- {area}" for area in supervisor.focus_areas))
        
        if supervisor.custom_instructions:
            prompt_parts.append(f"\n\n## Custom Instructions\n{supervisor.custom_instructions}")
        
        return "\n".join(prompt_parts)
    
    async def get_relevant_code_context(
        self,
        query: str,
        max_tokens: int = 4000
    ) -> str:
        """Get relevant code context from RAG database."""
        if not self.config.rag_enabled:
            return ""
        
        try:
            rag = self._get_rag_manager()
            return await rag.get_context_for_query(query, max_tokens=max_tokens)
        except Exception as e:
            return f"[RAG Error: {str(e)}]"
    
    async def review_agent_proposal(
        self,
        session_id: str,
        proposal: str,
        include_code_context: bool = True
    ) -> List[SupervisorResponse]:
        """
        Have all enabled supervisors review an agent proposal.
        
        Args:
            session_id: Session identifier
            proposal: The agent's proposal to review
            include_code_context: Whether to include RAG code context
            
        Returns:
            List of supervisor responses in priority order
        """
        if not self.config.enabled:
            return []
        
        context = self.get_context(session_id)
        context.agent_proposal = proposal
        
        # Get relevant code context if enabled
        if include_code_context and self.config.rag_enabled:
            context.relevant_code = await self.get_relevant_code_context(proposal)
        
        # Get enabled supervisors
        supervisors = self.config.get_enabled_supervisors()
        if not supervisors:
            return []
        
        responses = []
        
        for supervisor in supervisors:
            try:
                # Build system prompt
                system_prompt = self._build_system_prompt(supervisor, context)
                
                # Build messages
                messages = []
                
                # Add conversation history
                for msg in context.conversation_history[-10:]:  # Last 10 messages
                    messages.append(msg)
                
                # Add the proposal to review
                review_prompt = f"""Please review the following proposal from the AI agent:

## Agent Proposal
{proposal}

"""
                if context.relevant_code:
                    review_prompt += f"""
{context.relevant_code}
"""
                
                review_prompt += """
Please provide your assessment following your structured response format."""
                
                messages.append({"role": "user", "content": review_prompt})
                
                # Call supervisor
                response_text = await self._call_supervisor(
                    supervisor,
                    messages,
                    system_prompt
                )
                
                # Extract verdict if present
                verdict = ""
                for v in ["APPROVE", "NEEDS_REVISION", "REJECT"]:
                    if f"[VERDICT]: {v}" in response_text or f"VERDICT: {v}" in response_text:
                        verdict = v
                        break
                
                # Extract confidence score
                confidence = self._extract_confidence(response_text)
                
                responses.append(SupervisorResponse(
                    supervisor_id=supervisor.id,
                    supervisor_name=supervisor.name,
                    supervisor_type=supervisor.supervisor_type,
                    response=response_text,
                    verdict=verdict,
                    metadata={
                        "model": supervisor.model_name,
                        "temperature": supervisor.temperature
                    },
                    confidence=confidence,
                    should_auto_send=False  # Will be determined after all responses
                ))
                
            except Exception as e:
                responses.append(SupervisorResponse(
                    supervisor_id=supervisor.id,
                    supervisor_name=supervisor.name,
                    supervisor_type=supervisor.supervisor_type,
                    response=f"[Error: {str(e)}]",
                    verdict="",
                    metadata={"error": str(e)},
                    confidence=0.0,
                    should_auto_send=False
                ))
        
        # After all supervisors have responded, determine if auto-send should trigger
        should_auto_send = self._should_auto_send(session_id, responses, proposal)
        
        if should_auto_send:
            # Mark the last response (general supervisor should be first due to priority)
            # to indicate auto-send should happen
            for response in responses:
                if response.supervisor_type == SupervisorType.GENERAL:
                    response.should_auto_send = True
                    break
            
            # Update auto-send state
            import time
            state = self.get_auto_send_state(session_id)
            state.consecutive_auto_sends += 1
            state.total_auto_sends += 1
            state.last_auto_send_time = time.time()
            
            # Trigger auto-send callback if set
            if self._auto_send_callback:
                combined_response = self.format_combined_response(responses)
                self._auto_send_callback(session_id, combined_response)
        else:
            # Reset consecutive counter if not auto-sending
            state = self.get_auto_send_state(session_id)
            state.consecutive_auto_sends = 0
        
        return responses
    
    async def discuss_goals(
        self,
        session_id: str,
        user_message: str
    ) -> SupervisorResponse:
        """
        Have a conversation with the general supervisor about project goals.
        
        Args:
            session_id: Session identifier
            user_message: User's message about goals/vision
            
        Returns:
            Supervisor response
        """
        context = self.get_context(session_id)
        
        # Find general supervisor
        general_supervisor = None
        for s in self.config.supervisors:
            if s.supervisor_type == SupervisorType.GENERAL and s.enabled:
                general_supervisor = s
                break
        
        if not general_supervisor:
            general_supervisor = create_default_general_supervisor()
        
        # Build system prompt for goal discussion
        system_prompt = """You are a General Supervisor AI helping a developer articulate their project vision and goals.

Your role in this conversation is to:
1. Help the developer clearly define what they want to achieve
2. Ask clarifying questions to understand the full scope
3. Identify potential challenges or considerations
4. Help translate the vision into actionable requirements
5. Summarize the goals in a clear, structured format

Be conversational but focused. Help the developer think through their ideas thoroughly."""
        
        if context.project_goals:
            system_prompt += f"\n\n## Current Project Goals\n{context.project_goals}"
        
        # Build messages
        messages = list(context.conversation_history[-10:])
        messages.append({"role": "user", "content": user_message})
        
        # Call supervisor
        response_text = await self._call_supervisor(
            general_supervisor,
            messages,
            system_prompt
        )
        
        # Add to history
        self.add_to_history(session_id, "user", user_message)
        self.add_to_history(session_id, "assistant", response_text)
        
        return SupervisorResponse(
            supervisor_id=general_supervisor.id,
            supervisor_name=general_supervisor.name,
            supervisor_type=general_supervisor.supervisor_type,
            response=response_text,
            verdict="",
            metadata={"model": general_supervisor.model_name}
        )
    
    async def generate_system_prompt(
        self,
        supervisor_type: SupervisorType,
        focus_areas: List[str],
        custom_requirements: str = ""
    ) -> str:
        """
        Have the supervisor AI generate its own system prompt.
        
        Args:
            supervisor_type: Type of supervisor
            focus_areas: Areas to focus on
            custom_requirements: Additional requirements from user
            
        Returns:
            Generated system prompt
        """
        # Use general supervisor to generate the prompt
        general_supervisor = None
        for s in self.config.supervisors:
            if s.supervisor_type == SupervisorType.GENERAL and s.enabled:
                general_supervisor = s
                break
        
        if not general_supervisor:
            general_supervisor = create_default_general_supervisor()
        
        generation_prompt = f"""Generate a system prompt for a {supervisor_type.value} Supervisor AI.

The supervisor should focus on these areas:
{chr(10).join(f'- {area}' for area in focus_areas)}

Additional requirements:
{custom_requirements if custom_requirements else 'None specified'}

The system prompt should:
1. Clearly define the supervisor's role and responsibilities
2. Specify how it should review agent proposals
3. Include a structured response format with clear sections
4. End with a VERDICT section (APPROVE / NEEDS_REVISION / REJECT)

Generate only the system prompt, nothing else."""
        
        messages = [{"role": "user", "content": generation_prompt}]
        
        response = await self._call_supervisor(
            general_supervisor,
            messages,
            "You are an expert at creating system prompts for AI supervisors. Generate clear, effective prompts."
        )
        
        return response
    
    def format_combined_response(
        self,
        responses: List[SupervisorResponse]
    ) -> str:
        """
        Format multiple supervisor responses into a single combined response.
        
        Args:
            responses: List of supervisor responses
            
        Returns:
            Formatted combined response
        """
        if not responses:
            return ""
        
        parts = ["## Supervisor Review\n"]
        
        for response in responses:
            parts.append(f"### {response.supervisor_name} ({response.supervisor_type.value})")
            parts.append(response.response)
            if response.verdict:
                parts.append(f"\n**Verdict: {response.verdict}**")
            parts.append("\n---\n")
        
        # Add overall summary if multiple supervisors
        if len(responses) > 1:
            verdicts = [r.verdict for r in responses if r.verdict]
            if verdicts:
                if all(v == "APPROVE" for v in verdicts):
                    parts.append("**Overall: All supervisors APPROVE**")
                elif any(v == "REJECT" for v in verdicts):
                    parts.append("**Overall: At least one supervisor REJECTS - review required**")
                else:
                    parts.append("**Overall: Revisions suggested - please review feedback**")
        
        return "\n".join(parts)
    
    async def close(self) -> None:
        """Close resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


# Global supervisor manager instance
_supervisor_manager: Optional[SupervisorManager] = None


def get_supervisor_manager() -> SupervisorManager:
    """Get or create the global supervisor manager instance."""
    global _supervisor_manager
    
    if _supervisor_manager is None:
        _supervisor_manager = SupervisorManager()
    
    return _supervisor_manager


async def reload_supervisor_manager() -> SupervisorManager:
    """Reload the supervisor manager with fresh configuration."""
    global _supervisor_manager
    
    if _supervisor_manager:
        await _supervisor_manager.close()
    
    _supervisor_manager = SupervisorManager()
    return _supervisor_manager
