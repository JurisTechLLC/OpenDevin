"""Devin Integration Service for OpenHands.

Handles automatic error reporting to Devin.ai for review and repair.
Sanitizes logs before sending to remove sensitive data.

This is a Python port of the DevinIntegrationService from chatuserinterface,
adapted for OpenHands' architecture.
"""

import hashlib
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

from openhands.core.logger import openhands_logger as logger

# Devin API configuration
DEVIN_API_BASE_URL = "https://api.devin.ai/v1"
DEVIN_REPO = "JurisTechLLC/OpenDevin"

# ChatUserInterface API configuration for external error reporting
# This allows OpenHands to submit errors to the centralized error tracking system
CHATUSERINTERFACE_API_URL = os.getenv(
    "CHATUSERINTERFACE_API_URL",
    "https://ottomasion.ai/api/external-error-reports"
)

# Rate limiting configuration
MAX_REQUESTS_PER_HOUR = 10
DEDUPLICATION_WINDOW_SECONDS = 3600  # 1 hour


@dataclass
class ErrorContext:
    """Context for an error to be reported to Devin."""
    category: str
    event: str
    message: str
    stack_trace: Optional[str] = None
    code_location: Optional[str] = None
    context: Optional[dict[str, Any]] = None
    severity: str = "ERROR"  # DEBUG, INFO, WARNING, ERROR, CRITICAL


@dataclass
class SanitizedError:
    """Sanitized error data safe to send to external services."""
    category: str
    event: str
    message: str
    stack_trace: Optional[str] = None
    code_location: Optional[str] = None
    context: Optional[dict[str, Any]] = None


@dataclass
class DevinSessionResponse:
    """Response from creating a Devin session."""
    session_id: str
    url: str
    status: str


@dataclass
class ReportResult:
    """Result of reporting an error to Devin."""
    success: bool
    notification_id: Optional[str] = None
    devin_session_id: Optional[str] = None
    devin_session_url: Optional[str] = None
    error: Optional[str] = None
    skipped_reason: Optional[str] = None
    in_cooldown: bool = False
    cooldown_ends_at: Optional[datetime] = None
    has_historical_context: bool = False


@dataclass
class HistoricalAttempt:
    """Record of a previous fix attempt for an error."""
    session_id: str
    session_url: str
    pr_url: Optional[str]
    status: str
    created_at: datetime
    resolved_at: Optional[datetime]
    resolution_notes: Optional[str]


@dataclass
class ErrorHistory:
    """Historical context for a recurring error."""
    has_history: bool
    previous_attempts: list[HistoricalAttempt] = field(default_factory=list)
    total_occurrences: int = 0
    first_seen: Optional[datetime] = None


class DevinIntegrationService:
    """Service for integrating with Devin.ai for automatic error reporting and repair.
    
    Features:
    - Automatic error sanitization to remove sensitive data
    - Rate limiting to prevent API abuse
    - Error deduplication to avoid duplicate reports
    - PR merge cooldown (5 minutes after PR merge before allowing new sessions)
    - Historical context injection for recurring errors
    - Environment variable toggle to disable the feature
    """
    
    # PR merge cooldown period in seconds (5 minutes)
    PR_MERGE_COOLDOWN_SECONDS = 5 * 60
    
    def __init__(self):
        self._request_counts: dict[str, int] = {}
        self._last_request_reset: float = time.time()
        self._recent_error_hashes: dict[str, float] = {}  # hash -> timestamp
        
        # In-memory tracking for PR merge cooldown and historical context
        # In production, this should be backed by a database
        self._resolved_errors: dict[str, dict[str, Any]] = {}  # hash -> {resolved_at, pr_url, session_id}
        self._error_history: dict[str, list[dict[str, Any]]] = {}  # hash -> list of attempts
        self._active_sessions: dict[str, str] = {}  # hash -> session_id (for deduplication)
        
    def is_enabled(self) -> bool:
        """Check if Devin auto-review is enabled.
        
        Set DISABLE_DEVIN_AUTO_REVIEW=true to disable automatic error reporting to Devin.
        This is useful for temporarily pausing the feature without code changes.
        """
        disabled = os.getenv("DISABLE_DEVIN_AUTO_REVIEW", "").lower()
        if disabled in ("true", "1", "yes"):
            logger.info("[DevinIntegration] Devin auto-review is DISABLED via DISABLE_DEVIN_AUTO_REVIEW environment variable")
            return False
        return True
    
    def _get_api_key(self) -> Optional[str]:
        """Get the Devin API key from environment variables."""
        api_key = os.getenv("DEVIN_API_KEY")
        if not api_key:
            logger.warning(
                "[DevinIntegration] No Devin API key found. "
                "Set DEVIN_API_KEY environment variable to enable automatic error reporting."
            )
        return api_key
    
    def _generate_error_hash(self, error: ErrorContext) -> str:
        """Generate a hash for error deduplication."""
        hash_input = f"{error.category}:{error.event}:{error.message}:{error.code_location or ''}"
        return hashlib.sha256(hash_input.encode()).hexdigest()
    
    def _sanitize_string(self, s: str) -> str:
        """Sanitize a string to remove sensitive patterns."""
        sanitized = s
        
        # Remove API keys (various formats)
        sanitized = re.sub(r'sk-ant-[a-zA-Z0-9\-_]+', '[ANTHROPIC_KEY]', sanitized)
        sanitized = re.sub(r'sk-[a-zA-Z0-9\-_]{20,}', '[OPENAI_KEY]', sanitized)
        sanitized = re.sub(r'pckey_[a-zA-Z0-9\-_]+', '[PINECONE_KEY]', sanitized)
        sanitized = re.sub(r'pa-[a-zA-Z0-9\-_]+', '[VOYAGE_KEY]', sanitized)
        
        # Remove UUIDs that might be user/session IDs
        sanitized = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '[UUID]',
            sanitized,
            flags=re.IGNORECASE
        )
        
        # Remove email addresses
        sanitized = re.sub(
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            '[EMAIL]',
            sanitized
        )
        
        # Remove JWT tokens
        sanitized = re.sub(
            r'eyJ[a-zA-Z0-9\-_]+\.eyJ[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+',
            '[JWT_TOKEN]',
            sanitized
        )
        
        # Remove bearer tokens
        sanitized = re.sub(
            r'Bearer\s+[a-zA-Z0-9\-_\.]+',
            'Bearer [TOKEN]',
            sanitized,
            flags=re.IGNORECASE
        )
        
        # Remove database connection strings
        sanitized = re.sub(
            r'postgres(ql)?://[^\s]+',
            '[DATABASE_URL]',
            sanitized,
            flags=re.IGNORECASE
        )
        
        # Remove IP addresses
        sanitized = re.sub(
            r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
            '[IP_ADDRESS]',
            sanitized
        )
        
        return sanitized
    
    def _sanitize_stack_trace(self, stack_trace: str) -> str:
        """Sanitize stack trace while preserving useful debugging info."""
        lines = stack_trace.split('\n')
        sanitized_lines = []
        
        for line in lines:
            sanitized = self._sanitize_string(line)
            # Remove absolute paths, keep relative paths
            sanitized = re.sub(r'/[^\s]*/OpenDevin/', 'OpenDevin/', sanitized)
            sanitized = re.sub(r'/home/[^\s/]+/', '~/', sanitized)
            sanitized_lines.append(sanitized)
        
        return '\n'.join(sanitized_lines)
    
    def _sanitize_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Sanitize context object recursively."""
        sensitive_fields = [
            'password', 'secret', 'token', 'api_key', 'apiKey',
            'authorization', 'cookie', 'session', 'user_id', 'userId',
            'email', 'phone', 'ssn', 'credit_card', 'creditCard'
        ]
        
        sanitized: dict[str, Any] = {}
        
        for key, value in context.items():
            # Skip sensitive fields entirely
            if any(field.lower() in key.lower() for field in sensitive_fields):
                sanitized[key] = '[REDACTED]'
                continue
            
            if isinstance(value, str):
                sanitized[key] = self._sanitize_string(value)
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_context(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_string(item) if isinstance(item, str)
                    else self._sanitize_context(item) if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _sanitize_error(self, error: ErrorContext) -> SanitizedError:
        """Sanitize error data to remove sensitive information."""
        return SanitizedError(
            category=error.category,
            event=error.event,
            message=self._sanitize_string(error.message),
            stack_trace=self._sanitize_stack_trace(error.stack_trace) if error.stack_trace else None,
            code_location=error.code_location,
            context=self._sanitize_context(error.context) if error.context else None
        )
    
    def _check_rate_limit(self) -> bool:
        """Check if we should rate limit requests."""
        now = time.time()
        
        # Reset counter every hour
        if now - self._last_request_reset > 3600:
            self._request_counts.clear()
            self._last_request_reset = now
        
        current_hour = str(int(now / 3600))
        count = self._request_counts.get(current_hour, 0)
        
        if count >= MAX_REQUESTS_PER_HOUR:
            logger.warning(
                f"[DevinIntegration] Rate limit reached: {count}/{MAX_REQUESTS_PER_HOUR} requests this hour"
            )
            return False
        
        self._request_counts[current_hour] = count + 1
        return True
    
    def _check_duplicate(self, error_hash: str) -> bool:
        """Check if this error is a duplicate within the deduplication window."""
        now = time.time()
        cutoff_time = now - DEDUPLICATION_WINDOW_SECONDS
        
        # Clean up old entries
        self._recent_error_hashes = {
            h: t for h, t in self._recent_error_hashes.items()
            if t > cutoff_time
        }
        
        if error_hash in self._recent_error_hashes:
            logger.info(f"[DevinIntegration] Duplicate error detected, skipping: {error_hash[:16]}...")
            return True
        
        self._recent_error_hashes[error_hash] = now
        return False
    
    def _build_devin_prompt(self, error: SanitizedError) -> str:
        """Build a prompt for Devin to analyze and fix the error."""
        prompt = f"""Please analyze and fix the following runtime error in the OpenDevin repository:

**Error Category:** {error.category}
**Event:** {error.event}
**Message:** {error.message}
"""
        
        if error.code_location:
            prompt += f"**Code Location:** {error.code_location}\n"
        
        if error.stack_trace:
            prompt += f"""
**Stack Trace:**
```
{error.stack_trace}
```
"""
        
        if error.context:
            import json
            prompt += f"""
**Additional Context:**
```json
{json.dumps(error.context, indent=2)}
```
"""
        
        prompt += """
**Instructions:**
1. Analyze the error and identify the root cause
2. Implement a fix that addresses the issue
3. Ensure the fix doesn't introduce new bugs or break existing functionality
4. Add appropriate error handling if needed
5. Create a PR with the fix

Please focus on creating a robust, production-ready fix."""
        
        return prompt
    
    async def _call_devin_api(
        self,
        api_key: str,
        sanitized_error: SanitizedError
    ) -> Optional[DevinSessionResponse]:
        """Call the Devin API to request a review session."""
        try:
            prompt = self._build_devin_prompt(sanitized_error)
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{DEVIN_API_BASE_URL}/sessions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}"
                    },
                    json={
                        "prompt": prompt,
                        "repo": DEVIN_REPO
                    }
                )
                
                if response.status_code != 200:
                    logger.error(
                        f"[DevinIntegration] Devin API error: {response.status_code} - {response.text}"
                    )
                    return None
                
                data = response.json()
                return DevinSessionResponse(
                    session_id=data.get("session_id", ""),
                    url=data.get("url", f"https://app.devin.ai/sessions/{data.get('session_id', '')}"),
                    status=data.get("status", "created")
                )
                
        except Exception as e:
            logger.error(f"[DevinIntegration] Failed to call Devin API: {e}")
            return None
    
    async def report_error(self, error: ErrorContext) -> ReportResult:
        """Report an error to Devin for automatic review and repair.
        
        Args:
            error: The error context to report
            
        Returns:
            ReportResult with success status and session details
        """
        # Check if feature is enabled
        if not self.is_enabled():
            return ReportResult(
                success=False,
                skipped_reason="Devin auto-review is disabled via DISABLE_DEVIN_AUTO_REVIEW"
            )
        
        # Get API key
        api_key = self._get_api_key()
        if not api_key:
            return ReportResult(
                success=False,
                error="No Devin API key configured"
            )
        
        # Generate error hash for deduplication
        error_hash = self._generate_error_hash(error)
        
        # Check for duplicates
        if self._check_duplicate(error_hash):
            return ReportResult(
                success=False,
                skipped_reason="Duplicate error within deduplication window"
            )
        
        # Check rate limit
        if not self._check_rate_limit():
            return ReportResult(
                success=False,
                skipped_reason="Rate limit exceeded"
            )
        
        # Sanitize error
        sanitized_error = self._sanitize_error(error)
        
        logger.info(
            f"[DevinIntegration] Reporting error to Devin: {error.message[:100]}..."
        )
        
        # Call Devin API
        session = await self._call_devin_api(api_key, sanitized_error)
        
        if session:
            logger.info(
                f"[DevinIntegration] Devin review session created: {session.url}"
            )
            return ReportResult(
                success=True,
                devin_session_id=session.session_id,
                devin_session_url=session.url
            )
        else:
            return ReportResult(
                success=False,
                error="Failed to create Devin session"
            )
    
    def report_error_sync(self, error: ErrorContext) -> ReportResult:
        """Synchronous wrapper for report_error.
        
        Use this when you need to report an error from synchronous code.
        """
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, create a new task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.report_error(error)
                    )
                    return future.result(timeout=60)
            else:
                return loop.run_until_complete(self.report_error(error))
        except Exception as e:
            logger.error(f"[DevinIntegration] Error in sync wrapper: {e}")
            return ReportResult(success=False, error=str(e))

    # ===== PR MERGE COOLDOWN AND HISTORICAL CONTEXT =====
    
    def _check_pr_merge_cooldown(self, error_hash: str) -> tuple[bool, Optional[datetime], Optional[str]]:
        """Check if an error is in the PR merge cooldown period.
        
        Returns:
            Tuple of (in_cooldown, cooldown_ends_at, merged_pr_url)
        """
        if error_hash not in self._resolved_errors:
            return False, None, None
        
        resolved = self._resolved_errors[error_hash]
        resolved_at = resolved.get("resolved_at")
        
        if resolved_at:
            cooldown_ends_at = resolved_at + timedelta(seconds=self.PR_MERGE_COOLDOWN_SECONDS)
            if datetime.now() < cooldown_ends_at:
                logger.info(
                    f"[DevinIntegration] Error {error_hash[:16]}... is in PR merge cooldown "
                    f"until {cooldown_ends_at.isoformat()}"
                )
                return True, cooldown_ends_at, resolved.get("pr_url")
        
        return False, None, None
    
    def _check_active_session(self, error_hash: str) -> Optional[str]:
        """Check if there's already an active session for this error.
        
        Returns:
            Session ID if active session exists, None otherwise
        """
        return self._active_sessions.get(error_hash)
    
    def _get_historical_context(self, error_hash: str) -> ErrorHistory:
        """Get historical context for a recurring error."""
        if error_hash not in self._error_history:
            return ErrorHistory(has_history=False)
        
        attempts = self._error_history[error_hash]
        if not attempts:
            return ErrorHistory(has_history=False)
        
        # Convert stored dicts to HistoricalAttempt objects
        previous_attempts = [
            HistoricalAttempt(
                session_id=a.get("session_id", ""),
                session_url=a.get("session_url", ""),
                pr_url=a.get("pr_url"),
                status=a.get("status", "unknown"),
                created_at=a.get("created_at", datetime.now()),
                resolved_at=a.get("resolved_at"),
                resolution_notes=a.get("resolution_notes")
            )
            for a in attempts
        ]
        
        # Calculate total occurrences
        total_occurrences = sum(a.get("occurrence_count", 1) for a in attempts)
        
        # Find first seen date
        first_seen = min(
            (a.get("created_at") for a in attempts if a.get("created_at")),
            default=None
        )
        
        return ErrorHistory(
            has_history=True,
            previous_attempts=previous_attempts,
            total_occurrences=total_occurrences,
            first_seen=first_seen
        )
    
    def _build_prompt_with_historical_context(
        self,
        error: SanitizedError,
        history: ErrorHistory
    ) -> str:
        """Build a prompt with historical context for recurring errors."""
        prompt = self._build_devin_prompt(error)
        
        # Add historical context section
        prompt += f"\n\n## WARNING: RECURRING ERROR - HISTORICAL CONTEXT\n"
        prompt += f"This error has occurred **{history.total_occurrences} times** "
        if history.first_seen:
            prompt += f"since {history.first_seen.strftime('%Y-%m-%d')}.\n\n"
        else:
            prompt += "previously.\n\n"
        
        if history.previous_attempts:
            prompt += "### Previous Fix Attempts\n"
            prompt += "The following Devin sessions have attempted to fix this error:\n\n"
            
            for attempt in history.previous_attempts[:5]:
                prompt += f"**Session:** {attempt.session_url}\n"
                prompt += f"- Status: {attempt.status}\n"
                if attempt.pr_url:
                    prompt += f"- PR: {attempt.pr_url}\n"
                if attempt.resolved_at:
                    prompt += f"- Resolved: {attempt.resolved_at.strftime('%Y-%m-%d')}\n"
                if attempt.resolution_notes:
                    prompt += f"- Notes: {attempt.resolution_notes}\n"
                prompt += "\n"
            
            prompt += "### IMPORTANT INSTRUCTIONS\n"
            prompt += "1. **Review the previous sessions** linked above to understand what was tried before\n"
            prompt += "2. **Do NOT repeat the same approach** if it didn't work\n"
            prompt += "3. **Try a different strategy** - the previous fix may have been incomplete\n"
            prompt += "4. **Consider deeper investigation** - this recurring error may indicate a fundamental issue\n"
            prompt += "5. **Document your approach** in the PR description so future sessions can learn from it\n"
        
        return prompt
    
    def _record_attempt(
        self,
        error_hash: str,
        session_id: str,
        session_url: str
    ) -> None:
        """Record a fix attempt for historical tracking."""
        if error_hash not in self._error_history:
            self._error_history[error_hash] = []
        
        self._error_history[error_hash].append({
            "session_id": session_id,
            "session_url": session_url,
            "pr_url": None,
            "status": "in_progress",
            "created_at": datetime.now(),
            "resolved_at": None,
            "resolution_notes": None,
            "occurrence_count": 1
        })
        
        # Track active session
        self._active_sessions[error_hash] = session_id
    
    async def report_error_with_cooldown_and_history(
        self,
        error: ErrorContext
    ) -> ReportResult:
        """Report an error with PR merge cooldown and historical context.
        
        This is the recommended method for production use. It includes:
        - PR merge cooldown (5 minutes after PR merge before allowing new sessions)
        - Historical context injection for recurring errors
        - Active session deduplication
        
        Args:
            error: The error context to report
            
        Returns:
            ReportResult with success status and session details
        """
        # Check if feature is enabled
        if not self.is_enabled():
            return ReportResult(
                success=False,
                skipped_reason="Devin auto-review is disabled via DISABLE_DEVIN_AUTO_REVIEW"
            )
        
        # Get API key
        api_key = self._get_api_key()
        if not api_key:
            return ReportResult(
                success=False,
                error="No Devin API key configured"
            )
        
        # Generate error hash
        error_hash = self._generate_error_hash(error)
        
        # Check PR merge cooldown
        in_cooldown, cooldown_ends_at, merged_pr_url = self._check_pr_merge_cooldown(error_hash)
        if in_cooldown:
            return ReportResult(
                success=True,
                skipped_reason=f"PR merge cooldown active until {cooldown_ends_at.isoformat() if cooldown_ends_at else 'unknown'}. "
                              f"A fix was recently merged ({merged_pr_url or 'PR URL not available'}). "
                              "Waiting for production deployment to complete.",
                in_cooldown=True,
                cooldown_ends_at=cooldown_ends_at
            )
        
        # Check for active session
        active_session_id = self._check_active_session(error_hash)
        if active_session_id:
            return ReportResult(
                success=True,
                devin_session_id=active_session_id,
                devin_session_url=f"https://app.devin.ai/sessions/{active_session_id}",
                skipped_reason=f"Active session {active_session_id} already working on this error"
            )
        
        # Check for duplicates (basic deduplication)
        if self._check_duplicate(error_hash):
            return ReportResult(
                success=False,
                skipped_reason="Duplicate error within deduplication window"
            )
        
        # Check rate limit
        if not self._check_rate_limit():
            return ReportResult(
                success=False,
                skipped_reason="Rate limit exceeded"
            )
        
        # Get historical context
        history = self._get_historical_context(error_hash)
        
        # Sanitize error
        sanitized_error = self._sanitize_error(error)
        
        # Build prompt with or without historical context
        if history.has_history and history.previous_attempts:
            prompt = self._build_prompt_with_historical_context(sanitized_error, history)
            logger.info(
                f"[DevinIntegration] Building prompt with historical context "
                f"({len(history.previous_attempts)} previous attempts)"
            )
        else:
            prompt = self._build_devin_prompt(sanitized_error)
        
        logger.info(
            f"[DevinIntegration] Reporting error to Devin: {error.message[:100]}..."
        )
        
        # Call Devin API with the enhanced prompt
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{DEVIN_API_BASE_URL}/sessions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}"
                    },
                    json={
                        "prompt": prompt,
                        "repo": DEVIN_REPO
                    }
                )
                
                if response.status_code != 200:
                    logger.error(
                        f"[DevinIntegration] Devin API error: {response.status_code} - {response.text}"
                    )
                    return ReportResult(
                        success=False,
                        error=f"Devin API error: {response.status_code}"
                    )
                
                data = response.json()
                session_id = data.get("session_id", "")
                session_url = data.get("url", f"https://app.devin.ai/sessions/{session_id}")
                
                # Record the attempt for historical tracking
                self._record_attempt(error_hash, session_id, session_url)
                
                logger.info(
                    f"[DevinIntegration] Devin review session created: {session_url}"
                    + (" (with historical context)" if history.has_history else "")
                )
                
                return ReportResult(
                    success=True,
                    devin_session_id=session_id,
                    devin_session_url=session_url,
                    has_historical_context=history.has_history and len(history.previous_attempts) > 0
                )
                
        except Exception as e:
            logger.error(f"[DevinIntegration] Failed to call Devin API: {e}")
            return ReportResult(success=False, error=str(e))
    
    def mark_pr_merged(
        self,
        error_hash: str,
        pr_url: str,
        session_id: str,
        notes: Optional[str] = None
    ) -> None:
        """Mark a PR as merged, starting the cooldown period.
        
        Args:
            error_hash: Hash of the error that was fixed
            pr_url: URL of the merged PR
            session_id: Devin session ID that created the PR
            notes: Optional resolution notes
        """
        # Record the resolution
        self._resolved_errors[error_hash] = {
            "resolved_at": datetime.now(),
            "pr_url": pr_url,
            "session_id": session_id,
            "notes": notes
        }
        
        # Update historical record
        if error_hash in self._error_history:
            for attempt in self._error_history[error_hash]:
                if attempt.get("session_id") == session_id:
                    attempt["status"] = "resolved"
                    attempt["resolved_at"] = datetime.now()
                    attempt["pr_url"] = pr_url
                    attempt["resolution_notes"] = notes
                    break
        
        # Remove from active sessions
        if error_hash in self._active_sessions:
            del self._active_sessions[error_hash]
        
        logger.info(
            f"[DevinIntegration] Marked error {error_hash[:16]}... as resolved (PR merged). "
            f"Cooldown period of {self.PR_MERGE_COOLDOWN_SECONDS // 60} minutes started."
        )
    
    def clear_active_session(self, error_hash: str) -> None:
        """Clear an active session (e.g., if it failed or was cancelled)."""
        if error_hash in self._active_sessions:
            del self._active_sessions[error_hash]
            logger.info(f"[DevinIntegration] Cleared active session for error {error_hash[:16]}...")

    # ===== CHATUSERINTERFACE API INTEGRATION =====
    
    def _get_external_api_key(self) -> Optional[str]:
        """Get the API key for the chatuserinterface external error reports endpoint."""
        api_key = os.getenv("CHATUSERINTERFACE_ERROR_REPORTS_API_KEY")
        if not api_key:
            logger.warning(
                "[DevinIntegration] No chatuserinterface API key found. "
                "Set CHATUSERINTERFACE_ERROR_REPORTS_API_KEY environment variable to enable "
                "centralized error reporting."
            )
        return api_key
    
    async def report_error_to_chatuserinterface(
        self,
        error: ErrorContext,
        repository: Optional[str] = None
    ) -> ReportResult:
        """Report an error to the chatuserinterface centralized error tracking system.
        
        This method sends errors to the chatuserinterface API endpoint, which handles:
        - PR merge cooldown (5 minutes after PR merge before allowing new sessions)
        - Historical context injection for recurring errors
        - Active session deduplication
        - Routing to Devin.ai for automatic fixes
        
        This is the recommended method for production use when you want centralized
        error tracking across multiple services.
        
        Args:
            error: The error context to report
            repository: Optional repository name (defaults to DEVIN_REPO)
            
        Returns:
            ReportResult with success status and session details
        """
        # Check if feature is enabled
        if not self.is_enabled():
            return ReportResult(
                success=False,
                skipped_reason="Devin auto-review is disabled via DISABLE_DEVIN_AUTO_REVIEW"
            )
        
        # Get API key for chatuserinterface
        api_key = self._get_external_api_key()
        if not api_key:
            # Fall back to direct Devin API if no chatuserinterface key
            logger.info(
                "[DevinIntegration] No chatuserinterface API key, falling back to direct Devin API"
            )
            return await self.report_error_with_cooldown_and_history(error)
        
        # Check rate limit
        if not self._check_rate_limit():
            return ReportResult(
                success=False,
                skipped_reason="Rate limit exceeded"
            )
        
        # Sanitize error
        sanitized_error = self._sanitize_error(error)
        
        logger.info(
            f"[DevinIntegration] Reporting error to chatuserinterface: {error.message[:100]}..."
        )
        
        # Build payload for chatuserinterface API
        payload = {
            "source": "openhands",
            "category": sanitized_error.category,
            "message": sanitized_error.message,
            "stackTrace": sanitized_error.stack_trace,
            "codeLocation": sanitized_error.code_location,
            "severity": error.severity,
            "context": sanitized_error.context or {},
            "repository": repository or DEVIN_REPO
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    CHATUSERINTERFACE_API_URL,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}"
                    },
                    json=payload
                )
                
                if response.status_code == 401:
                    logger.error(
                        "[DevinIntegration] Unauthorized - invalid API key for chatuserinterface"
                    )
                    return ReportResult(
                        success=False,
                        error="Unauthorized - invalid API key"
                    )
                
                if response.status_code == 429:
                    logger.warning(
                        "[DevinIntegration] Rate limit exceeded on chatuserinterface API"
                    )
                    return ReportResult(
                        success=False,
                        skipped_reason="Rate limit exceeded on chatuserinterface API"
                    )
                
                if response.status_code != 200:
                    logger.error(
                        f"[DevinIntegration] chatuserinterface API error: "
                        f"{response.status_code} - {response.text}"
                    )
                    return ReportResult(
                        success=False,
                        error=f"API error: {response.status_code}"
                    )
                
                data = response.json()
                
                if data.get("success"):
                    logger.info(
                        f"[DevinIntegration] Error reported to chatuserinterface: "
                        f"notification={data.get('notificationId')}, "
                        f"session={data.get('devinSessionUrl')}"
                    )
                    return ReportResult(
                        success=True,
                        notification_id=data.get("notificationId"),
                        devin_session_id=data.get("devinSessionId"),
                        devin_session_url=data.get("devinSessionUrl"),
                        in_cooldown=data.get("action") == "cooldown",
                        has_historical_context=data.get("action") == "historical_context"
                    )
                else:
                    return ReportResult(
                        success=False,
                        error=data.get("error"),
                        skipped_reason=data.get("message")
                    )
                    
        except httpx.TimeoutException:
            logger.error("[DevinIntegration] Timeout calling chatuserinterface API")
            return ReportResult(success=False, error="Request timeout")
        except Exception as e:
            logger.error(f"[DevinIntegration] Failed to call chatuserinterface API: {e}")
            return ReportResult(success=False, error=str(e))
    
    def report_error_to_chatuserinterface_sync(
        self,
        error: ErrorContext,
        repository: Optional[str] = None
    ) -> ReportResult:
        """Synchronous wrapper for report_error_to_chatuserinterface.
        
        Use this when you need to report an error from synchronous code.
        """
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.report_error_to_chatuserinterface(error, repository)
                    )
                    return future.result(timeout=60)
            else:
                return loop.run_until_complete(
                    self.report_error_to_chatuserinterface(error, repository)
                )
        except Exception as e:
            logger.error(f"[DevinIntegration] Error in sync wrapper: {e}")
            return ReportResult(success=False, error=str(e))


# Global singleton instance
devin_integration = DevinIntegrationService()


def report_error_to_devin(
    error: Exception,
    category: str = "runtime_error",
    event: str = "exception",
    context: Optional[dict[str, Any]] = None
) -> ReportResult:
    """Convenience function to report an exception to Devin.
    
    Args:
        error: The exception to report
        category: Error category (e.g., "runtime_error", "api_error")
        event: Event type (e.g., "exception", "timeout")
        context: Additional context information
        
    Returns:
        ReportResult with success status and session details
        
    Example:
        try:
            # ... code that might fail
        except Exception as e:
            report_error_to_devin(e, category="agent_error", context={"agent_id": "123"})
            raise
    """
    import traceback
    
    # Extract code location from traceback
    code_location = None
    tb = traceback.extract_tb(error.__traceback__)
    if tb:
        last_frame = tb[-1]
        code_location = f"{last_frame.filename}:{last_frame.lineno}"
    
    error_context = ErrorContext(
        category=category,
        event=event,
        message=str(error),
        stack_trace=traceback.format_exc(),
        code_location=code_location,
        context=context,
        severity="ERROR"
    )
    
    return devin_integration.report_error_sync(error_context)
