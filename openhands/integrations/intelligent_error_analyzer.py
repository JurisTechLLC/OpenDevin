"""Intelligent Error Analyzer Service for OpenHands.

Uses AI (Claude) to intelligently analyze errors and determine if they should be sent for repair.
This replaces the brittle pattern-matching approach with true AI-based analysis.

Key features:
1. Uses Claude to analyze error root causes
2. Checks against active Devin sessions (currently being worked on)
3. Checks against open, unmerged PRs (pending human review)
4. Only sends errors that are NOT duplicates of active work

The AI determines if a new error shares the same ROOT CAUSE as existing work,
not just literal text matching. If an error keeps happening after a fix was
merged, it should be reported again since the fix didn't address the root cause.

This is a Python port of the IntelligentErrorAnalyzerService from chatuserinterface,
adapted for OpenHands' architecture.
"""

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional

import httpx

from openhands.core.logger import openhands_logger as logger
from openhands.integrations.devin_integration import devin_integration

# Default repository for OpenHands
DEFAULT_REPO = "JurisTechLLC/OpenDevin"


@dataclass
class ErrorToAnalyze:
    """Error context to be analyzed."""

    category: str
    event: str
    message: str
    stack_trace: Optional[str] = None
    code_location: Optional[str] = None
    context: Optional[dict[str, Any]] = None
    severity: str = "ERROR"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    source_repo: Optional[str] = None


@dataclass
class ActiveWork:
    """Represents active work item (Devin session or open PR)."""

    type: Literal["devin_session", "open_pr"]
    id: str
    title: str
    description: str
    root_cause_summary: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class RootCauseAnalysis:
    """Result of AI root cause analysis."""

    root_cause: str
    category: (
        str  # SECURITY, FUNCTIONAL, DATA_INTEGRITY, USER_EXPERIENCE, PERFORMANCE, OTHER
    )
    severity: str  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    affected_components: list[str] = field(default_factory=list)
    suggested_action: str = ""
    is_duplicate_of_active_work: bool = False
    matching_active_work: Optional[ActiveWork] = None
    confidence: float = 0.5
    reasoning: str = ""


# System prompt for the IT Manager AI that analyzes errors
ROOT_CAUSE_ANALYSIS_PROMPT = """You are an experienced IT Manager responsible for analyzing runtime errors in a legal technology software platform. Your job is to:

1. IDENTIFY THE ROOT CAUSE: Analyze the error and determine the underlying root cause, not just the surface-level symptom.

2. COMPARE WITH ACTIVE WORK: You will be given a list of currently active work items (Devin sessions and open PRs). Determine if this error's root cause is ALREADY being addressed by any of these active work items.

3. MAKE A DECISION: Should this error be sent for repair, or is it already being worked on?

IMPORTANT RULES:
- Focus on ROOT CAUSE, not literal text matching. Two errors with different messages can have the same root cause.
- If an error's root cause is being addressed by active work, mark it as a duplicate.
- If an error keeps happening after a fix was merged (not in active work), it should be reported as NEW.
- Only consider ACTIVE work (open sessions, open unmerged PRs). Closed/merged work should be ignored.

Output your analysis as JSON with these fields:
{
  "rootCause": "Clear description of the underlying root cause",
  "category": "SECURITY|FUNCTIONAL|DATA_INTEGRITY|USER_EXPERIENCE|PERFORMANCE|OTHER",
  "severity": "CRITICAL|ERROR|WARNING|INFO|DEBUG",
  "affectedComponents": ["list", "of", "affected", "components"],
  "suggestedAction": "Recommended fix or investigation steps",
  "isDuplicateOfActiveWork": true/false,
  "matchingActiveWorkId": "ID of matching active work if duplicate, null otherwise",
  "confidence": 0.0-1.0,
  "reasoning": "Explanation of your analysis and decision"
}"""


class IntelligentErrorAnalyzerService:
    """Service for intelligent AI-based error analysis.

    Uses Claude to analyze errors and determine if they should be sent for repair,
    checking against active Devin sessions and open PRs to avoid duplicates.
    """

    def __init__(self):
        self._github_token = os.getenv("GITHUB_TOKEN")

    def _get_anthropic_api_key(self) -> Optional[str]:
        """Get the Anthropic API key from environment variables."""
        return os.getenv("ANTHROPIC_API_KEY")

    async def _get_active_devin_sessions(self) -> list[ActiveWork]:
        """Fetch active Devin sessions that are currently being worked on.

        Uses the in-memory tracking from DevinIntegrationService.
        """
        active_work: list[ActiveWork] = []

        # Get active sessions from the devin_integration singleton
        for error_hash, session_id in devin_integration._active_sessions.items():
            active_work.append(
                ActiveWork(
                    type="devin_session",
                    id=session_id,
                    title=f"Devin session {session_id}",
                    description=f"Active session for error hash {error_hash[:16]}...",
                    url=f"https://app.devin.ai/sessions/{session_id}",
                    created_at=datetime.now(),
                )
            )

        return active_work

    async def _get_open_unmerged_prs(self, repo: str) -> list[ActiveWork]:
        """Fetch open, unmerged PRs from GitHub.

        Only returns PRs that are OPEN (not closed, not merged).
        """
        if not self._github_token:
            logger.warning(
                "[IntelligentErrorAnalyzer] GitHub token not configured, skipping PR check"
            )
            return []

        try:
            parts = repo.split("/")
            if len(parts) != 2:
                logger.warning(
                    "[IntelligentErrorAnalyzer] Invalid repo format, expected owner/repo"
                )
                return []

            owner, repo_name = parts

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo_name}/pulls",
                    headers={
                        "Authorization": f"token {self._github_token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                    params={
                        "state": "open",
                        "sort": "created",
                        "direction": "desc",
                        "per_page": 50,
                    },
                )

                if response.status_code != 200:
                    logger.error(
                        f"[IntelligentErrorAnalyzer] GitHub API error: {response.status_code}"
                    )
                    return []

                prs = response.json()
                return [
                    ActiveWork(
                        type="open_pr",
                        id=str(pr["number"]),
                        title=pr["title"],
                        description=pr.get("body") or "",
                        url=pr["html_url"],
                        created_at=datetime.fromisoformat(
                            pr["created_at"].replace("Z", "+00:00")
                        ),
                    )
                    for pr in prs
                ]

        except Exception as e:
            logger.error(f"[IntelligentErrorAnalyzer] Failed to fetch open PRs: {e}")
            return []

    def _format_error_for_analysis(self, error: ErrorToAnalyze) -> str:
        """Format error for AI analysis."""
        formatted = f"""Category: {error.category}
Event: {error.event}
Message: {error.message}
Severity: {error.severity}"""

        if error.code_location:
            formatted += f"\nCode Location: {error.code_location}"

        if error.stack_trace:
            formatted += f"\nStack Trace:\n{error.stack_trace}"

        if error.context:
            formatted += f"\nContext: {json.dumps(error.context, indent=2)}"

        return formatted

    def _format_active_work_for_analysis(self, active_work: list[ActiveWork]) -> str:
        """Format active work items for AI analysis."""
        if not active_work:
            return ""

        formatted_items = []
        for i, work in enumerate(active_work):
            item = f"""[{i + 1}] {"Devin Session" if work.type == "devin_session" else "Open PR"}
ID: {work.id}
Title: {work.title}
Description: {work.description[:500]}{"..." if len(work.description) > 500 else ""}"""
            if work.created_at:
                item += f"\nCreated: {work.created_at.isoformat()}"
            formatted_items.append(item)

        return "\n\n".join(formatted_items)

    def _validate_category(
        self, category: str
    ) -> Literal[
        "SECURITY",
        "FUNCTIONAL",
        "DATA_INTEGRITY",
        "USER_EXPERIENCE",
        "PERFORMANCE",
        "OTHER",
    ]:
        """Validate and normalize category."""
        valid_categories = [
            "SECURITY",
            "FUNCTIONAL",
            "DATA_INTEGRITY",
            "USER_EXPERIENCE",
            "PERFORMANCE",
            "OTHER",
        ]
        normalized = category.upper() if category else "OTHER"
        return normalized if normalized in valid_categories else "OTHER"

    def _validate_severity(
        self, severity: str
    ) -> Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        """Validate and normalize severity."""
        valid_severities = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        normalized = severity.upper() if severity else "ERROR"
        return normalized if normalized in valid_severities else "ERROR"

    def _parse_analysis_response(
        self, response_text: str, active_work: list[ActiveWork]
    ) -> RootCauseAnalysis:
        """Parse the AI analysis response."""
        try:
            # Extract JSON from the response (handle markdown code blocks)
            json_text = response_text
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response_text)
            if json_match:
                json_text = json_match.group(1).strip()

            parsed = json.loads(json_text)

            # Find matching active work if specified
            matching_active_work: Optional[ActiveWork] = None
            if parsed.get("matchingActiveWorkId") and parsed.get(
                "isDuplicateOfActiveWork"
            ):
                matching_active_work = next(
                    (w for w in active_work if w.id == parsed["matchingActiveWorkId"]),
                    None,
                )

            return RootCauseAnalysis(
                root_cause=parsed.get("rootCause", "Unknown root cause"),
                category=self._validate_category(parsed.get("category", "OTHER")),
                severity=self._validate_severity(parsed.get("severity", "ERROR")),
                affected_components=parsed.get("affectedComponents", [])
                if isinstance(parsed.get("affectedComponents"), list)
                else [],
                suggested_action=parsed.get(
                    "suggestedAction", "Manual review required"
                ),
                is_duplicate_of_active_work=bool(parsed.get("isDuplicateOfActiveWork")),
                matching_active_work=matching_active_work,
                confidence=float(parsed.get("confidence", 0.5))
                if isinstance(parsed.get("confidence"), (int, float))
                else 0.5,
                reasoning=parsed.get("reasoning", "No reasoning provided"),
            )

        except Exception as e:
            logger.error(f"[IntelligentErrorAnalyzer] Failed to parse AI response: {e}")
            return RootCauseAnalysis(
                root_cause="Failed to parse AI analysis",
                category="OTHER",
                severity="ERROR",
                suggested_action="Manual review required",
                is_duplicate_of_active_work=False,
                confidence=0,
                reasoning=f"Parse error: {e}",
            )

    async def analyze_error(self, error: ErrorToAnalyze) -> RootCauseAnalysis:
        """Use AI to analyze the error and determine if it's a duplicate of active work.

        Args:
            error: The error to analyze

        Returns:
            RootCauseAnalysis with the AI's analysis
        """
        api_key = self._get_anthropic_api_key()
        if not api_key:
            logger.warning(
                "[IntelligentErrorAnalyzer] No Anthropic API key configured, "
                "defaulting to allow error reporting"
            )
            return RootCauseAnalysis(
                root_cause="API key not configured",
                category="OTHER",
                severity="ERROR",
                suggested_action="Manual review required",
                is_duplicate_of_active_work=False,
                confidence=0,
                reasoning="Anthropic API key not configured, defaulting to allow error reporting",
            )

        # Fetch all active work
        repo = error.source_repo or DEFAULT_REPO
        active_sessions, open_prs = await asyncio.gather(
            self._get_active_devin_sessions(),
            self._get_open_unmerged_prs(repo),
            return_exceptions=True,
        )

        # Handle exceptions from gather
        if isinstance(active_sessions, Exception):
            logger.error(
                f"[IntelligentErrorAnalyzer] Failed to fetch active sessions: {active_sessions}"
            )
            active_sessions = []
        if isinstance(open_prs, Exception):
            logger.error(
                f"[IntelligentErrorAnalyzer] Failed to fetch open PRs: {open_prs}"
            )
            open_prs = []

        all_active_work = list(active_sessions) + list(open_prs)

        # Build the prompt for AI analysis
        error_description = self._format_error_for_analysis(error)
        active_work_description = self._format_active_work_for_analysis(all_active_work)

        user_prompt = f"""Please analyze this error and determine if it should be sent for repair:

**ERROR TO ANALYZE:**
{error_description}

**CURRENTLY ACTIVE WORK (Devin sessions and open PRs):**
{active_work_description or "No active work items found."}

Analyze the error's root cause and determine if it's already being addressed by any active work item. Output your analysis as JSON."""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": "claude-3-5-haiku-latest",
                        "max_tokens": 2048,
                        "system": ROOT_CAUSE_ANALYSIS_PROMPT,
                        "messages": [{"role": "user", "content": user_prompt}],
                    },
                )

                if response.status_code != 200:
                    raise Exception(f"AI analysis failed: {response.status_code}")

                data = response.json()
                analysis_text = data.get("content", [{}])[0].get("text", "{}")

                # Parse the AI response
                return self._parse_analysis_response(analysis_text, all_active_work)

        except Exception as e:
            logger.error(f"[IntelligentErrorAnalyzer] AI analysis failed: {e}")
            # Return a default analysis that allows the error to be reported
            return RootCauseAnalysis(
                root_cause=f"Analysis failed: {e}",
                category="OTHER",
                severity="ERROR",
                suggested_action="Manual review required",
                is_duplicate_of_active_work=False,
                confidence=0,
                reasoning="AI analysis failed, defaulting to allow error reporting",
            )

    async def should_send_for_repair(
        self, error: ErrorToAnalyze
    ) -> tuple[bool, RootCauseAnalysis]:
        """Analyze error and determine if it should be sent for repair.

        Returns:
            Tuple of (should_send, analysis)
            - should_send: True if the error should be sent, False if it's a duplicate
            - analysis: The full RootCauseAnalysis
        """
        analysis = await self.analyze_error(error)

        if analysis.is_duplicate_of_active_work:
            logger.info(
                f"[IntelligentErrorAnalyzer] Error identified as duplicate of active work: "
                f"{analysis.matching_active_work.title if analysis.matching_active_work else 'Unknown'}"
            )
            logger.info(f"[IntelligentErrorAnalyzer] Reasoning: {analysis.reasoning}")
            return False, analysis

        logger.info(
            "[IntelligentErrorAnalyzer] Error is NOT a duplicate, should be sent for repair"
        )
        logger.info(f"[IntelligentErrorAnalyzer] Root cause: {analysis.root_cause}")
        return True, analysis


# Global singleton instance
intelligent_error_analyzer = IntelligentErrorAnalyzerService()
