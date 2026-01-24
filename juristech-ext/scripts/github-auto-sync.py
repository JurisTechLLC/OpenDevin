#!/usr/bin/env python3
"""
JurisTech OpenHands Extension - GitHub Auto-Sync Service
Automatically pulls updates for all cloned GitHub repositories.

This script runs as a background service and:
1. Monitors all discovered GitHub repositories
2. Periodically checks for remote changes
3. Automatically pulls updates when changes are detected
4. Re-indexes the RAG database after updates

Usage:
    python3 github-auto-sync.py [--interval SECONDS] [--once]
    
Options:
    --interval SECONDS  Check interval in seconds (default: 300 = 5 minutes)
    --once              Run once and exit (useful for cron jobs)
"""

import os
import sys
import json
import time
import logging
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            Path.home() / '.juristech-openhands' / 'auto-sync.log'
        )
    ]
)
logger = logging.getLogger(__name__)


class GitHubAutoSync:
    """
    Automatically syncs GitHub repositories with their remotes.
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
        config_path: str = "~/.juristech-openhands/auto-sync-config.json",
        check_interval: int = 300  # 5 minutes
    ):
        self.config_path = Path(config_path).expanduser()
        self.check_interval = check_interval
        self._repos: Dict[str, Dict] = {}
        self._load_config()
        
        # Ensure log directory exists
        log_dir = Path.home() / '.juristech-openhands'
        log_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self) -> None:
        """Load configuration from file."""
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                data = json.load(f)
                self._repos = data.get("repos", {})
                self.check_interval = data.get("check_interval", self.check_interval)
    
    def _save_config(self) -> None:
        """Save configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "repos": self._repos,
            "check_interval": self.check_interval,
            "last_updated": datetime.now().isoformat()
        }
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def discover_repos(self) -> List[str]:
        """Discover all GitHub repositories on the system."""
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
                        repo_path = str(item)
                        if repo_path not in self._repos:
                            self._repos[repo_path] = {
                                "path": repo_path,
                                "last_sync": None,
                                "last_commit": None,
                                "enabled": True
                            }
                        discovered.append(repo_path)
        
        self._save_config()
        logger.info(f"Discovered {len(discovered)} repositories")
        return discovered
    
    def _run_git_command(
        self,
        repo_path: str,
        command: List[str]
    ) -> Tuple[bool, str]:
        """Run a git command in a repository."""
        try:
            result = subprocess.run(
                ["git"] + command,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode == 0, result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    def _get_current_branch(self, repo_path: str) -> Optional[str]:
        """Get the current branch of a repository."""
        success, output = self._run_git_command(
            repo_path,
            ["rev-parse", "--abbrev-ref", "HEAD"]
        )
        return output if success else None
    
    def _get_local_commit(self, repo_path: str) -> Optional[str]:
        """Get the current local commit hash."""
        success, output = self._run_git_command(
            repo_path,
            ["rev-parse", "HEAD"]
        )
        return output if success else None
    
    def _get_remote_commit(self, repo_path: str, branch: str) -> Optional[str]:
        """Get the latest remote commit hash after fetching."""
        # First fetch
        success, _ = self._run_git_command(repo_path, ["fetch", "origin"])
        if not success:
            return None
        
        # Get remote commit
        success, output = self._run_git_command(
            repo_path,
            ["rev-parse", f"origin/{branch}"]
        )
        return output if success else None
    
    def _has_uncommitted_changes(self, repo_path: str) -> bool:
        """Check if the repository has uncommitted changes."""
        success, output = self._run_git_command(
            repo_path,
            ["status", "--porcelain"]
        )
        return bool(output.strip()) if success else True
    
    def _pull_updates(self, repo_path: str) -> Tuple[bool, str]:
        """Pull updates from the remote."""
        # Use --ff-only to avoid merge conflicts
        success, output = self._run_git_command(
            repo_path,
            ["pull", "--ff-only", "origin"]
        )
        return success, output
    
    def check_and_sync_repo(self, repo_path: str) -> Dict:
        """
        Check a repository for updates and sync if needed.
        
        Returns a dict with sync status and details.
        """
        result = {
            "path": repo_path,
            "synced": False,
            "status": "unknown",
            "message": ""
        }
        
        repo_info = self._repos.get(repo_path, {})
        if not repo_info.get("enabled", True):
            result["status"] = "disabled"
            result["message"] = "Repository sync is disabled"
            return result
        
        # Get current branch
        branch = self._get_current_branch(repo_path)
        if not branch:
            result["status"] = "error"
            result["message"] = "Could not determine current branch"
            return result
        
        # Check for uncommitted changes
        if self._has_uncommitted_changes(repo_path):
            result["status"] = "skipped"
            result["message"] = "Repository has uncommitted changes"
            return result
        
        # Get local and remote commits
        local_commit = self._get_local_commit(repo_path)
        remote_commit = self._get_remote_commit(repo_path, branch)
        
        if not local_commit or not remote_commit:
            result["status"] = "error"
            result["message"] = "Could not get commit information"
            return result
        
        # Check if update is needed
        if local_commit == remote_commit:
            result["status"] = "up-to-date"
            result["message"] = "Repository is already up to date"
            return result
        
        # Pull updates
        success, output = self._pull_updates(repo_path)
        
        if success:
            result["synced"] = True
            result["status"] = "synced"
            result["message"] = f"Updated from {local_commit[:8]} to {remote_commit[:8]}"
            
            # Update repo info
            self._repos[repo_path]["last_sync"] = datetime.now().isoformat()
            self._repos[repo_path]["last_commit"] = remote_commit
            self._save_config()
            
            logger.info(f"Synced {repo_path}: {result['message']}")
        else:
            result["status"] = "error"
            result["message"] = f"Pull failed: {output}"
            logger.error(f"Failed to sync {repo_path}: {output}")
        
        return result
    
    def sync_all_repos(self) -> List[Dict]:
        """Sync all discovered repositories."""
        results = []
        
        # Discover repos first
        self.discover_repos()
        
        for repo_path in self._repos:
            if Path(repo_path).exists():
                result = self.check_and_sync_repo(repo_path)
                results.append(result)
            else:
                logger.warning(f"Repository path no longer exists: {repo_path}")
        
        return results
    
    def trigger_rag_reindex(self, repo_path: str) -> bool:
        """
        Trigger RAG re-indexing for a synced repository.
        This calls the GitHub RAG integration API if available.
        """
        try:
            import requests
            
            # Try to call the local API
            response = requests.post(
                "http://127.0.0.1:3001/api/github-rag/repos/index",
                json={
                    "full_name": self._get_repo_full_name(repo_path),
                    "force": True
                },
                timeout=10
            )
            
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Could not trigger RAG reindex: {e}")
            return False
    
    def _get_repo_full_name(self, repo_path: str) -> Optional[str]:
        """Get the full name (owner/repo) from a local repository."""
        success, output = self._run_git_command(
            repo_path,
            ["remote", "get-url", "origin"]
        )
        
        if not success:
            return None
        
        # Parse owner/name from URL
        if "github.com" in output:
            if output.startswith("git@"):
                parts = output.split(":")[-1]
            else:
                parts = "/".join(output.split("/")[-2:])
            
            parts = parts.replace(".git", "")
            return parts
        
        return None
    
    def run_once(self) -> List[Dict]:
        """Run a single sync cycle."""
        logger.info("Starting sync cycle...")
        results = self.sync_all_repos()
        
        # Trigger RAG reindex for synced repos
        for result in results:
            if result.get("synced"):
                self.trigger_rag_reindex(result["path"])
        
        synced_count = sum(1 for r in results if r.get("synced"))
        logger.info(f"Sync cycle complete. {synced_count}/{len(results)} repos synced.")
        
        return results
    
    def run_daemon(self) -> None:
        """Run as a daemon, continuously checking for updates."""
        logger.info(f"Starting auto-sync daemon (interval: {self.check_interval}s)")
        
        while True:
            try:
                self.run_once()
            except Exception as e:
                logger.error(f"Error during sync cycle: {e}")
            
            logger.info(f"Sleeping for {self.check_interval} seconds...")
            time.sleep(self.check_interval)


def main():
    parser = argparse.ArgumentParser(
        description="GitHub Auto-Sync Service for JurisTech OpenHands"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Check interval in seconds (default: 300)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit"
    )
    
    args = parser.parse_args()
    
    sync = GitHubAutoSync(check_interval=args.interval)
    
    if args.once:
        results = sync.run_once()
        for r in results:
            print(f"{r['status']:12} {r['path']}: {r['message']}")
    else:
        sync.run_daemon()


if __name__ == "__main__":
    main()
