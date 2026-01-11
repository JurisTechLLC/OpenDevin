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


class DevinIntegrationService:
    """Service for integrating with Devin.ai for automatic error reporting and repair.
    
    Features:
    - Automatic error sanitization to remove sensitive data
    - Rate limiting to prevent API abuse
    - Error deduplication to avoid duplicate reports
    - Environment variable toggle to disable the feature
    """
    
    def __init__(self):
        self._request_counts: dict[str, int] = {}
        self._last_request_reset: float = time.time()
        self._recent_error_hashes: dict[str, float] = {}  # hash -> timestamp
        
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
