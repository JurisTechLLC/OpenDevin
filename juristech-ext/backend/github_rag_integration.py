"""
JurisTech OpenHands Extension - GitHub RAG Integration
Automatically indexes repositories based on GitHub Desktop cloned repos.
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import subprocess

from .rag_manager import RAGManager, get_rag_manager


@dataclass
class GitHubRepoInfo:
    """Information about a GitHub repository."""
    name: str
    owner: str
    full_name: str
    local_path: str
    is_indexed: bool = False
    last_indexed: Optional[float] = None
    file_count: int = 0
    

class GitHubRAGIntegration:
    """
    Integrates GitHub Desktop repositories with the RAG system.
    
    This class:
    1. Discovers repositories cloned via GitHub Desktop
    2. Automatically indexes selected repositories
    3. Maintains a shared RAG database for all supervisors
    4. Syncs with OpenHands repo selection
    """
    
    # Common locations for GitHub Desktop cloned repos
    GITHUB_DESKTOP_PATHS = [
        "~/GitHub",
        "~/Documents/GitHub",
        "~/repos",
        "~/Projects",
        "/home/aiserver/GitHub",
        "/home/aiserver/repos",
    ]
    
    def __init__(
        self,
        config_path: str = "~/.juristech-openhands/github_rag_config.json",
        rag_index_path: str = "~/.juristech-openhands/rag_index"
    ):
        self.config_path = Path(config_path).expanduser()
        self.rag_index_path = Path(rag_index_path).expanduser()
        self._rag_manager: Optional[RAGManager] = None
        self._discovered_repos: Dict[str, GitHubRepoInfo] = {}
        self._current_repo: Optional[str] = None
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file."""
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                data = json.load(f)
                self._current_repo = data.get("current_repo")
                for repo_data in data.get("repos", []):
                    repo = GitHubRepoInfo(**repo_data)
                    self._discovered_repos[repo.full_name] = repo
    
    def _save_config(self) -> None:
        """Save configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "current_repo": self._current_repo,
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
                for r in self._discovered_repos.values()
            ]
        }
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def get_rag_manager(self) -> RAGManager:
        """Get the shared RAG manager instance."""
        if self._rag_manager is None:
            self._rag_manager = get_rag_manager(
                index_path=str(self.rag_index_path)
            )
        return self._rag_manager
    
    def discover_repos(self) -> List[GitHubRepoInfo]:
        """
        Discover all GitHub repositories on the system.
        Looks in common GitHub Desktop locations and finds git repos.
        """
        discovered = []
        
        for base_path in self.GITHUB_DESKTOP_PATHS:
            path = Path(base_path).expanduser()
            if not path.exists():
                continue
            
            # Look for directories containing .git
            for item in path.iterdir():
                if item.is_dir():
                    git_dir = item / ".git"
                    if git_dir.exists():
                        repo_info = self._get_repo_info(item)
                        if repo_info:
                            discovered.append(repo_info)
                            self._discovered_repos[repo_info.full_name] = repo_info
        
        self._save_config()
        return discovered
    
    def _get_repo_info(self, repo_path: Path) -> Optional[GitHubRepoInfo]:
        """Extract repository information from a local git repo."""
        try:
            # Get remote URL
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=str(repo_path),
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return None
            
            remote_url = result.stdout.strip()
            
            # Parse owner/name from URL
            # Handles: https://github.com/owner/repo.git or git@github.com:owner/repo.git
            if "github.com" in remote_url:
                if remote_url.startswith("git@"):
                    # git@github.com:owner/repo.git
                    parts = remote_url.split(":")[-1]
                else:
                    # https://github.com/owner/repo.git
                    parts = "/".join(remote_url.split("/")[-2:])
                
                parts = parts.replace(".git", "")
                if "/" in parts:
                    owner, name = parts.split("/")[:2]
                    
                    # Check if already discovered
                    full_name = f"{owner}/{name}"
                    if full_name in self._discovered_repos:
                        existing = self._discovered_repos[full_name]
                        existing.local_path = str(repo_path)
                        return existing
                    
                    return GitHubRepoInfo(
                        name=name,
                        owner=owner,
                        full_name=full_name,
                        local_path=str(repo_path)
                    )
            
            return None
            
        except Exception:
            return None
    
    def add_repo_path(self, path: str) -> Optional[GitHubRepoInfo]:
        """Manually add a repository path."""
        repo_path = Path(path).expanduser()
        if not repo_path.exists():
            return None
        
        repo_info = self._get_repo_info(repo_path)
        if repo_info:
            self._discovered_repos[repo_info.full_name] = repo_info
            self._save_config()
        
        return repo_info
    
    def get_discovered_repos(self) -> List[GitHubRepoInfo]:
        """Get list of all discovered repositories."""
        return list(self._discovered_repos.values())
    
    def get_repo(self, full_name: str) -> Optional[GitHubRepoInfo]:
        """Get a specific repository by full name (owner/repo)."""
        return self._discovered_repos.get(full_name)
    
    async def select_repo(self, full_name: str) -> bool:
        """
        Select a repository for RAG indexing.
        This will automatically index the repository if not already indexed.
        """
        repo = self._discovered_repos.get(full_name)
        if not repo:
            # Try to find it by discovering repos
            self.discover_repos()
            repo = self._discovered_repos.get(full_name)
        
        if not repo:
            return False
        
        self._current_repo = full_name
        
        # Index if not already indexed
        if not repo.is_indexed:
            await self.index_repo(full_name)
        
        self._save_config()
        return True
    
    async def index_repo(self, full_name: str, force: bool = False) -> bool:
        """
        Index a repository for RAG search.
        
        Args:
            full_name: Repository full name (owner/repo)
            force: Force re-indexing even if already indexed
        """
        repo = self._discovered_repos.get(full_name)
        if not repo:
            return False
        
        if repo.is_indexed and not force:
            return True
        
        rag = self.get_rag_manager()
        
        # Index the repository
        import time
        stats = await rag.index_directory(repo.local_path)
        
        # Update repo info
        repo.is_indexed = True
        repo.last_indexed = time.time()
        repo.file_count = stats.get("files_indexed", 0)
        
        self._save_config()
        return True
    
    def get_current_repo(self) -> Optional[GitHubRepoInfo]:
        """Get the currently selected repository."""
        if self._current_repo:
            return self._discovered_repos.get(self._current_repo)
        return None
    
    async def search_code(
        self,
        query: str,
        repo_filter: Optional[str] = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for code across indexed repositories.
        
        Args:
            query: Search query
            repo_filter: Optional repository to filter by (full_name)
            max_results: Maximum number of results
        """
        rag = self.get_rag_manager()
        results = await rag.search(query, n_results=max_results)
        
        # Filter by repo if specified
        if repo_filter:
            repo = self._discovered_repos.get(repo_filter)
            if repo:
                results = [
                    r for r in results
                    if r.get("file_path", "").startswith(repo.local_path)
                ]
        
        return results
    
    async def get_context_for_query(
        self,
        query: str,
        max_tokens: int = 4000
    ) -> str:
        """
        Get relevant code context for a query.
        Uses the currently selected repository.
        """
        rag = self.get_rag_manager()
        return await rag.get_context_for_query(query, max_tokens=max_tokens)
    
    def sync_with_openhands_repo(self, openhands_repo: str) -> bool:
        """
        Sync the RAG selection with the OpenHands selected repository.
        
        Args:
            openhands_repo: Repository selected in OpenHands (format: owner/repo)
        """
        # Check if we have this repo locally
        if openhands_repo in self._discovered_repos:
            asyncio.create_task(self.select_repo(openhands_repo))
            return True
        
        # Try to discover it
        self.discover_repos()
        if openhands_repo in self._discovered_repos:
            asyncio.create_task(self.select_repo(openhands_repo))
            return True
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the RAG integration."""
        rag = self.get_rag_manager()
        rag_stats = rag.get_stats()
        
        return {
            "discovered_repos": len(self._discovered_repos),
            "indexed_repos": sum(1 for r in self._discovered_repos.values() if r.is_indexed),
            "current_repo": self._current_repo,
            "rag_stats": rag_stats
        }


# Global instance
_github_rag_integration: Optional[GitHubRAGIntegration] = None


def get_github_rag_integration() -> GitHubRAGIntegration:
    """Get or create the global GitHub RAG integration instance."""
    global _github_rag_integration
    
    if _github_rag_integration is None:
        _github_rag_integration = GitHubRAGIntegration()
    
    return _github_rag_integration


async def auto_index_on_repo_select(repo_full_name: str) -> bool:
    """
    Convenience function to auto-index when a repo is selected in OpenHands.
    This should be called when the user selects a repository in the OpenHands UI.
    """
    integration = get_github_rag_integration()
    return await integration.select_repo(repo_full_name)
