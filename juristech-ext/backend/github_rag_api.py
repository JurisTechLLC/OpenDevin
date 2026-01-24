"""
JurisTech OpenHands Extension - GitHub RAG API Endpoints
Provides REST API for GitHub Desktop RAG integration.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from .github_rag_integration import (
    GitHubRAGIntegration,
    GitHubRepoInfo,
    get_github_rag_integration,
    auto_index_on_repo_select
)

router = APIRouter(prefix="/api/github-rag", tags=["github-rag"])


# Request/Response Models
class RepoPathRequest(BaseModel):
    path: str


class SelectRepoRequest(BaseModel):
    full_name: str


class IndexRepoRequest(BaseModel):
    full_name: str
    force: bool = False


class SearchRequest(BaseModel):
    query: str
    repo_filter: Optional[str] = None
    max_results: int = 10


class ContextRequest(BaseModel):
    query: str
    max_tokens: int = 4000


class SyncRepoRequest(BaseModel):
    openhands_repo: str


class RepoInfoResponse(BaseModel):
    name: str
    owner: str
    full_name: str
    local_path: str
    is_indexed: bool
    last_indexed: Optional[float]
    file_count: int


# Endpoints

@router.get("/repos")
async def list_repos():
    """List all discovered GitHub repositories."""
    integration = get_github_rag_integration()
    repos = integration.get_discovered_repos()
    
    return {
        "repos": [
            {
                "name": r.name,
                "owner": r.owner,
                "full_name": r.full_name,
                "local_path": r.local_path,
                "is_indexed": r.is_indexed,
                "last_indexed": r.last_indexed,
                "file_count": r.file_count
            }
            for r in repos
        ],
        "current_repo": integration._current_repo
    }


@router.post("/repos/discover")
async def discover_repos():
    """Discover all GitHub repositories on the system."""
    integration = get_github_rag_integration()
    repos = integration.discover_repos()
    
    return {
        "discovered": len(repos),
        "repos": [
            {
                "name": r.name,
                "owner": r.owner,
                "full_name": r.full_name,
                "local_path": r.local_path
            }
            for r in repos
        ]
    }


@router.post("/repos/add")
async def add_repo_path(request: RepoPathRequest):
    """Manually add a repository path."""
    integration = get_github_rag_integration()
    repo = integration.add_repo_path(request.path)
    
    if not repo:
        raise HTTPException(status_code=400, detail="Could not find a valid git repository at the specified path")
    
    return {
        "status": "success",
        "repo": {
            "name": repo.name,
            "owner": repo.owner,
            "full_name": repo.full_name,
            "local_path": repo.local_path
        }
    }


@router.post("/repos/select")
async def select_repo(request: SelectRepoRequest, background_tasks: BackgroundTasks):
    """
    Select a repository for RAG indexing.
    This will automatically index the repository if not already indexed.
    """
    integration = get_github_rag_integration()
    
    # Run indexing in background
    async def do_select():
        await integration.select_repo(request.full_name)
    
    background_tasks.add_task(do_select)
    
    return {
        "status": "selecting",
        "message": f"Selecting and indexing {request.full_name}",
        "full_name": request.full_name
    }


@router.post("/repos/index")
async def index_repo(request: IndexRepoRequest, background_tasks: BackgroundTasks):
    """Index a specific repository."""
    integration = get_github_rag_integration()
    
    repo = integration.get_repo(request.full_name)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository not found: {request.full_name}")
    
    # Run indexing in background
    async def do_index():
        await integration.index_repo(request.full_name, force=request.force)
    
    background_tasks.add_task(do_index)
    
    return {
        "status": "indexing",
        "message": f"Indexing {request.full_name}",
        "full_name": request.full_name
    }


@router.get("/repos/current")
async def get_current_repo():
    """Get the currently selected repository."""
    integration = get_github_rag_integration()
    repo = integration.get_current_repo()
    
    if not repo:
        return {"current_repo": None}
    
    return {
        "current_repo": {
            "name": repo.name,
            "owner": repo.owner,
            "full_name": repo.full_name,
            "local_path": repo.local_path,
            "is_indexed": repo.is_indexed,
            "last_indexed": repo.last_indexed,
            "file_count": repo.file_count
        }
    }


@router.post("/search")
async def search_code(request: SearchRequest):
    """Search for code across indexed repositories."""
    integration = get_github_rag_integration()
    
    try:
        results = await integration.search_code(
            query=request.query,
            repo_filter=request.repo_filter,
            max_results=request.max_results
        )
        
        return {
            "query": request.query,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/context")
async def get_context(request: ContextRequest):
    """Get relevant code context for a query."""
    integration = get_github_rag_integration()
    
    try:
        context = await integration.get_context_for_query(
            query=request.query,
            max_tokens=request.max_tokens
        )
        
        return {
            "query": request.query,
            "context": context
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def sync_with_openhands(request: SyncRepoRequest, background_tasks: BackgroundTasks):
    """
    Sync the RAG selection with the OpenHands selected repository.
    This is called when the user selects a repository in OpenHands.
    """
    integration = get_github_rag_integration()
    
    # Check if repo exists locally
    repo = integration.get_repo(request.openhands_repo)
    
    if not repo:
        # Try to discover it
        integration.discover_repos()
        repo = integration.get_repo(request.openhands_repo)
    
    if not repo:
        return {
            "status": "not_found",
            "message": f"Repository {request.openhands_repo} not found locally. Please clone it using GitHub Desktop.",
            "suggestion": "Clone the repository using GitHub Desktop, then try again."
        }
    
    # Select and index in background
    async def do_sync():
        await integration.select_repo(request.openhands_repo)
    
    background_tasks.add_task(do_sync)
    
    return {
        "status": "syncing",
        "message": f"Syncing RAG with {request.openhands_repo}",
        "repo": {
            "name": repo.name,
            "owner": repo.owner,
            "full_name": repo.full_name,
            "local_path": repo.local_path,
            "is_indexed": repo.is_indexed
        }
    }


@router.get("/stats")
async def get_stats():
    """Get statistics about the GitHub RAG integration."""
    integration = get_github_rag_integration()
    return integration.get_stats()


# Health check
@router.get("/health")
async def health_check():
    """Health check endpoint."""
    integration = get_github_rag_integration()
    stats = integration.get_stats()
    
    return {
        "status": "healthy",
        "discovered_repos": stats["discovered_repos"],
        "indexed_repos": stats["indexed_repos"],
        "current_repo": stats["current_repo"]
    }
