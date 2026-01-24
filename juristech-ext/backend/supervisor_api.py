"""
JurisTech OpenHands Extension - Supervisor API Endpoints
Provides REST API for supervisor AI functionality.
"""

import os
import json
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from .supervisor_config import (
    SupervisorConfig,
    SupervisorsConfig,
    SupervisorType,
    get_default_supervisors_config
)
from .supervisor_manager import (
    SupervisorManager,
    SupervisorResponse,
    get_supervisor_manager,
    reload_supervisor_manager
)
from .rag_manager import get_rag_manager

router = APIRouter(prefix="/api/supervisor", tags=["supervisor"])


# Request/Response Models
class SupervisorConfigRequest(BaseModel):
    id: Optional[str] = None
    name: str
    supervisor_type: str
    model_name: str = "anthropic/claude-opus-4-5-20251101"
    model_provider: str = "anthropic"
    model_base_url: Optional[str] = None
    api_key_env: str = "ANTHROPIC_API_KEY"
    temperature: float = 0.3
    max_tokens: int = 2048
    system_prompt: str = ""
    enabled: bool = True
    priority: int = 10
    auto_generate_prompt: bool = True
    focus_areas: List[str] = []
    custom_instructions: str = ""
    auto_send_enabled: bool = False
    auto_send_confidence_threshold: float = 0.8
    auto_send_max_consecutive: int = 5
    auto_send_stop_keywords: List[str] = []


class SupervisorsConfigRequest(BaseModel):
    supervisors: List[SupervisorConfigRequest]
    enabled: bool = True
    show_in_panel: bool = True
    auto_insert_response: bool = True
    rag_enabled: bool = True
    rag_index_path: str = "~/.juristech-openhands/rag_index"
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 200


class ReviewProposalRequest(BaseModel):
    session_id: str
    proposal: str
    include_code_context: bool = True


class DiscussGoalsRequest(BaseModel):
    session_id: str
    message: str


class UpdateGoalsRequest(BaseModel):
    session_id: str
    goals: str


class UpdateTaskRequest(BaseModel):
    session_id: str
    task: str


class GeneratePromptRequest(BaseModel):
    supervisor_type: str
    focus_areas: List[str]
    custom_requirements: str = ""


class IndexCodebaseRequest(BaseModel):
    directory_path: str


class AutoSendControlRequest(BaseModel):
    session_id: str
    action: str  # "pause" or "resume"


class SupervisorResponseModel(BaseModel):
    supervisor_id: str
    supervisor_name: str
    supervisor_type: str
    response: str
    verdict: str
    confidence: float
    should_auto_send: bool
    metadata: dict


# Endpoints

@router.get("/config")
async def get_config():
    """Get current supervisor configuration."""
    manager = get_supervisor_manager()
    return manager.config.to_dict()


@router.post("/config")
async def save_config(config: SupervisorsConfigRequest):
    """Save supervisor configuration."""
    manager = get_supervisor_manager()
    
    # Convert request to SupervisorsConfig
    supervisors = []
    for s in config.supervisors:
        supervisor = SupervisorConfig(
            id=s.id or f"supervisor-{len(supervisors)}",
            name=s.name,
            supervisor_type=SupervisorType(s.supervisor_type),
            model_name=s.model_name,
            model_provider=s.model_provider,
            model_base_url=s.model_base_url,
            api_key_env=s.api_key_env,
            temperature=s.temperature,
            max_tokens=s.max_tokens,
            system_prompt=s.system_prompt,
            enabled=s.enabled,
            priority=s.priority,
            auto_generate_prompt=s.auto_generate_prompt,
            focus_areas=s.focus_areas,
            custom_instructions=s.custom_instructions,
            auto_send_enabled=s.auto_send_enabled,
            auto_send_confidence_threshold=s.auto_send_confidence_threshold,
            auto_send_max_consecutive=s.auto_send_max_consecutive,
            auto_send_stop_keywords=s.auto_send_stop_keywords
        )
        supervisors.append(supervisor)
    
    manager.config = SupervisorsConfig(
        supervisors=supervisors,
        enabled=config.enabled,
        show_in_panel=config.show_in_panel,
        auto_insert_response=config.auto_insert_response,
        rag_enabled=config.rag_enabled,
        rag_index_path=config.rag_index_path,
        rag_chunk_size=config.rag_chunk_size,
        rag_chunk_overlap=config.rag_chunk_overlap
    )
    
    manager.save_config()
    return {"status": "success", "message": "Configuration saved"}


@router.post("/config/reset")
async def reset_config():
    """Reset configuration to defaults."""
    manager = get_supervisor_manager()
    manager.config = get_default_supervisors_config()
    manager.save_config()
    return {"status": "success", "message": "Configuration reset to defaults"}


@router.post("/review")
async def review_proposal(request: ReviewProposalRequest):
    """Have supervisors review an agent proposal."""
    manager = get_supervisor_manager()
    
    try:
        responses = await manager.review_agent_proposal(
            session_id=request.session_id,
            proposal=request.proposal,
            include_code_context=request.include_code_context
        )
        
        # Convert to response models
        result = []
        for r in responses:
            result.append(SupervisorResponseModel(
                supervisor_id=r.supervisor_id,
                supervisor_name=r.supervisor_name,
                supervisor_type=r.supervisor_type.value,
                response=r.response,
                verdict=r.verdict,
                confidence=r.confidence,
                should_auto_send=r.should_auto_send,
                metadata=r.metadata
            ))
        
        # Get combined response
        combined = manager.format_combined_response(responses)
        
        # Check if auto-send should trigger
        auto_send_triggered = any(r.should_auto_send for r in responses)
        
        return {
            "responses": [r.dict() for r in result],
            "combined_response": combined,
            "auto_send_triggered": auto_send_triggered,
            "all_approved": all(r.verdict == "APPROVE" for r in responses if r.verdict)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/discuss")
async def discuss_goals(request: DiscussGoalsRequest):
    """Have a conversation with the general supervisor about goals."""
    manager = get_supervisor_manager()
    
    try:
        response = await manager.discuss_goals(
            session_id=request.session_id,
            user_message=request.message
        )
        
        return {
            "response": response.response,
            "supervisor_name": response.supervisor_name,
            "metadata": response.metadata
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/goals")
async def update_goals(request: UpdateGoalsRequest):
    """Update project goals for a session."""
    manager = get_supervisor_manager()
    manager.update_project_goals(request.session_id, request.goals)
    return {"status": "success", "message": "Goals updated"}


@router.post("/task")
async def update_task(request: UpdateTaskRequest):
    """Update current task for a session."""
    manager = get_supervisor_manager()
    manager.update_current_task(request.session_id, request.task)
    return {"status": "success", "message": "Task updated"}


@router.get("/context/{session_id}")
async def get_context(session_id: str):
    """Get conversation context for a session."""
    manager = get_supervisor_manager()
    context = manager.get_context(session_id)
    return {
        "project_goals": context.project_goals,
        "current_task": context.current_task,
        "conversation_history": context.conversation_history,
        "agent_proposal": context.agent_proposal
    }


@router.post("/generate-prompt")
async def generate_prompt(request: GeneratePromptRequest):
    """Generate a system prompt for a supervisor type."""
    manager = get_supervisor_manager()
    
    try:
        prompt = await manager.generate_system_prompt(
            supervisor_type=SupervisorType(request.supervisor_type),
            focus_areas=request.focus_areas,
            custom_requirements=request.custom_requirements
        )
        
        return {"prompt": prompt}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index")
async def index_codebase(request: IndexCodebaseRequest, background_tasks: BackgroundTasks):
    """Index a codebase directory for RAG."""
    manager = get_supervisor_manager()
    
    if not manager.config.rag_enabled:
        raise HTTPException(status_code=400, detail="RAG is not enabled")
    
    directory = Path(request.directory_path).expanduser()
    if not directory.exists():
        raise HTTPException(status_code=400, detail=f"Directory not found: {request.directory_path}")
    
    rag_manager = manager._get_rag_manager()
    
    # Run indexing in background
    async def do_index():
        await rag_manager.index_directory(str(directory))
    
    background_tasks.add_task(do_index)
    
    return {
        "status": "indexing_started",
        "message": f"Indexing started for {request.directory_path}"
    }


@router.get("/index/stats")
async def get_index_stats():
    """Get RAG index statistics."""
    manager = get_supervisor_manager()
    
    if not manager.config.rag_enabled:
        return {"enabled": False}
    
    rag_manager = manager._get_rag_manager()
    stats = rag_manager.get_stats()
    
    return {
        "enabled": True,
        "stats": stats
    }


@router.post("/index/clear")
async def clear_index():
    """Clear the RAG index."""
    manager = get_supervisor_manager()
    
    if not manager.config.rag_enabled:
        raise HTTPException(status_code=400, detail="RAG is not enabled")
    
    rag_manager = manager._get_rag_manager()
    rag_manager.clear_index()
    
    return {"status": "success", "message": "Index cleared"}


@router.post("/auto-send/control")
async def control_auto_send(request: AutoSendControlRequest):
    """Control auto-send for a session (pause/resume)."""
    manager = get_supervisor_manager()
    
    if request.action == "pause":
        manager.pause_auto_send(request.session_id)
        return {"status": "success", "message": "Auto-send paused"}
    elif request.action == "resume":
        manager.resume_auto_send(request.session_id)
        return {"status": "success", "message": "Auto-send resumed"}
    else:
        raise HTTPException(status_code=400, detail=f"Invalid action: {request.action}")


@router.get("/auto-send/state/{session_id}")
async def get_auto_send_state(session_id: str):
    """Get auto-send state for a session."""
    manager = get_supervisor_manager()
    state = manager.get_auto_send_state(session_id)
    
    return {
        "consecutive_auto_sends": state.consecutive_auto_sends,
        "total_auto_sends": state.total_auto_sends,
        "last_auto_send_time": state.last_auto_send_time,
        "paused": state.paused
    }


@router.post("/reload")
async def reload_manager():
    """Reload the supervisor manager with fresh configuration."""
    await reload_supervisor_manager()
    return {"status": "success", "message": "Supervisor manager reloaded"}


# Health check
@router.get("/health")
async def health_check():
    """Health check endpoint."""
    manager = get_supervisor_manager()
    return {
        "status": "healthy",
        "enabled": manager.config.enabled,
        "supervisor_count": len(manager.config.supervisors),
        "rag_enabled": manager.config.rag_enabled
    }
