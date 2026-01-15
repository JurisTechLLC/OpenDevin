"""Error Router Service for OpenHands.

Provides unified error routing to Devin.ai using INTELLIGENT AI-BASED ANALYSIS
instead of pattern matching.

The service uses Claude to:
1. Analyze the root cause of errors
2. Check against active Devin sessions
3. Check against open, unmerged PRs
4. Only send errors that are NOT duplicates of active work

This replaces the brittle pattern-matching approach with true AI analysis.

Note: Unlike the chatuserinterface version which can route to both Devin and OpenHands,
this OpenHands version ONLY routes to Devin.ai since OpenHands cannot send repairs to itself.

This is a Python port of the ErrorRouterService from chatuserinterface,
adapted for OpenHands' architecture.
"""

from dataclasses import dataclass
from typing import Any, Literal, Optional

from openhands.core.logger import openhands_logger as logger
from openhands.integrations.devin_integration import (
    DevinIntegrationService,
    ErrorContext,
    ReportResult,
    devin_integration,
)
from openhands.integrations.intelligent_error_analyzer import (
    ErrorToAnalyze,
    IntelligentErrorAnalyzerService,
    RootCauseAnalysis,
    intelligent_error_analyzer,
)

# Error router type - for OpenHands, only 'devin' is supported
ErrorRouter = Literal["devin"]


@dataclass
class ErrorReport:
    """Error report to be routed."""

    category: str
    event: str
    message: str
    stack_trace: Optional[str] = None
    code_location: Optional[str] = None
    context: Optional[dict[str, Any]] = None
    severity: str = "ERROR"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    source_repo: Optional[str] = None


@dataclass
class RoutingResult:
    """Result of routing an error."""

    success: bool
    router: str = "devin"
    notification_id: Optional[str] = None
    devin_session_id: Optional[str] = None
    devin_session_url: Optional[str] = None
    linked_to_existing: bool = False
    error: Optional[str] = None
    skipped_reason: Optional[str] = None
    # AI analysis results
    ai_analysis: Optional[RootCauseAnalysis] = None


@dataclass
class ErrorRouterConfig:
    """Configuration for the error router."""

    # Enable/disable Devin integration
    enable_devin: bool = True
    # Minimum severity to report
    min_severity: str = "ERROR"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    # Enable AI-based analysis
    enable_ai_analysis: bool = True


# Severity levels for comparison
SEVERITY_LEVELS: dict[str, int] = {
    "DEBUG": 0,
    "INFO": 1,
    "WARNING": 2,
    "ERROR": 3,
    "CRITICAL": 4,
}


class ErrorRouterService:
    """Service for routing errors to Devin.ai using intelligent AI-based analysis.

    This service:
    1. Uses Claude to analyze the error's root cause
    2. Checks against active Devin sessions
    3. Checks against open, unmerged PRs
    4. Only sends errors that are NOT duplicates of active work

    Note: Unlike the chatuserinterface version which can route to both Devin and OpenHands,
    this OpenHands version ONLY routes to Devin.ai.
    """

    def __init__(
        self,
        config: Optional[ErrorRouterConfig] = None,
        devin_service: Optional[DevinIntegrationService] = None,
        analyzer_service: Optional[IntelligentErrorAnalyzerService] = None,
    ):
        """Initialize the ErrorRouterService.

        Args:
            config: Optional configuration. Uses defaults if not provided.
            devin_service: Optional DevinIntegrationService instance.
                          If not provided, uses the global singleton.
            analyzer_service: Optional IntelligentErrorAnalyzerService instance.
                             If not provided, uses the global singleton.
        """
        self._config = config or ErrorRouterConfig()
        self._devin_service = devin_service or devin_integration
        self._analyzer_service = analyzer_service or intelligent_error_analyzer

    def _meets_min_severity(self, severity: str) -> bool:
        """Check if error severity meets minimum threshold."""
        error_level = SEVERITY_LEVELS.get(severity.upper(), SEVERITY_LEVELS["ERROR"])
        min_level = SEVERITY_LEVELS.get(
            self._config.min_severity.upper(), SEVERITY_LEVELS["ERROR"]
        )
        return error_level >= min_level

    async def route_error(self, error: ErrorReport) -> RoutingResult:
        """Route an error to Devin.ai using INTELLIGENT AI-BASED ANALYSIS.

        This method:
        1. Uses Claude to analyze the error's root cause
        2. Checks against active Devin sessions
        3. Checks against open, unmerged PRs
        4. Only sends errors that are NOT duplicates of active work

        Args:
            error: The error report to route

        Returns:
            RoutingResult with success status and session details
        """
        # Check severity threshold
        severity = error.severity or "ERROR"
        if not self._meets_min_severity(severity):
            logger.info(
                f"[ErrorRouter] Skipping error with severity {severity} "
                f"(below threshold {self._config.min_severity})"
            )
            return RoutingResult(
                success=False,
                error=f"Severity {severity} below threshold {self._config.min_severity}",
            )

        # Check if Devin is enabled
        if not self._config.enable_devin:
            logger.info("[ErrorRouter] Devin is disabled, skipping")
            return RoutingResult(
                success=False,
                error="Devin integration is disabled",
            )

        # Use intelligent AI-based analysis if enabled
        if self._config.enable_ai_analysis:
            try:
                logger.info(
                    f'[ErrorRouter] Using AI to analyze error: "{error.message[:50]}..."'
                )

                error_to_analyze = ErrorToAnalyze(
                    category=error.category,
                    event=error.event,
                    message=error.message,
                    stack_trace=error.stack_trace,
                    code_location=error.code_location,
                    context=error.context,
                    severity=error.severity,
                    source_repo=error.source_repo,
                )

                (
                    should_send,
                    analysis,
                ) = await self._analyzer_service.should_send_for_repair(
                    error_to_analyze
                )

                if not should_send:
                    logger.info(
                        f"[ErrorRouter] AI determined error is duplicate of active work: "
                        f"{analysis.matching_active_work.title if analysis.matching_active_work else 'Unknown'}"
                    )
                    logger.info(f"[ErrorRouter] Reasoning: {analysis.reasoning}")
                    return RoutingResult(
                        success=False,
                        linked_to_existing=True,
                        error=f"Duplicate of active work: "
                        f"{analysis.matching_active_work.title if analysis.matching_active_work else 'Active work item'}. "
                        f"Reasoning: {analysis.reasoning}",
                        ai_analysis=analysis,
                    )

                logger.info(
                    f"[ErrorRouter] AI determined error should be sent for repair. "
                    f"Root cause: {analysis.root_cause}"
                )

                # Add AI analysis to context for the repair service
                enriched_context = {
                    **(error.context or {}),
                    "ai_analysis": {
                        "root_cause": analysis.root_cause,
                        "category": analysis.category,
                        "severity": analysis.severity,
                        "affected_components": analysis.affected_components,
                        "suggested_action": analysis.suggested_action,
                        "confidence": analysis.confidence,
                    },
                }

                # Route to Devin with enriched context
                return await self._route_to_devin(
                    ErrorReport(
                        category=error.category,
                        event=error.event,
                        message=error.message,
                        stack_trace=error.stack_trace,
                        code_location=error.code_location,
                        context=enriched_context,
                        severity=error.severity,
                        source_repo=error.source_repo,
                    ),
                    analysis,
                )

            except Exception as ai_error:
                logger.error(
                    f"[ErrorRouter] AI analysis failed, falling back to default routing: {ai_error}"
                )
                # Fall through to default routing if AI fails

        # Fallback: If AI analysis is disabled or fails, route directly to Devin
        logger.info(
            f'[ErrorRouter] Using fallback routing for: "{error.message[:50]}..."'
        )
        return await self._route_to_devin(error, None)

    async def _route_to_devin(
        self, error: ErrorReport, analysis: Optional[RootCauseAnalysis]
    ) -> RoutingResult:
        """Route error to Devin.

        Args:
            error: The error report to route
            analysis: Optional AI analysis results

        Returns:
            RoutingResult with success status and session details
        """
        try:
            error_context = ErrorContext(
                category=error.category,
                event=error.event,
                message=error.message,
                stack_trace=error.stack_trace,
                code_location=error.code_location,
                context=error.context,
                severity=error.severity,
            )

            # Use the enhanced method with cooldown and history
            result = await self._devin_service.report_error_with_cooldown_and_history(
                error_context
            )

            return RoutingResult(
                success=result.success,
                notification_id=result.notification_id,
                devin_session_id=result.devin_session_id,
                devin_session_url=result.devin_session_url,
                linked_to_existing=False,
                error=result.error,
                skipped_reason=result.skipped_reason,
                ai_analysis=analysis,
            )

        except Exception as e:
            logger.error(f"[ErrorRouter] Error routing to Devin: {e}")
            return RoutingResult(
                success=False,
                error=str(e),
                ai_analysis=analysis,
            )

    def route_error_sync(self, error: ErrorReport) -> RoutingResult:
        """Synchronous wrapper for route_error.

        Use this when you need to route an error from synchronous code.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.route_error(error))
                    return future.result(timeout=120)
            else:
                return loop.run_until_complete(self.route_error(error))
        except Exception as e:
            logger.error(f"[ErrorRouter] Error in sync wrapper: {e}")
            return RoutingResult(success=False, error=str(e))

    def update_config(self, config: ErrorRouterConfig) -> None:
        """Update configuration.

        Args:
            config: New configuration to apply
        """
        self._config = config
        logger.info(
            f"[ErrorRouter] Configuration updated: "
            f"enable_devin={self._config.enable_devin}, "
            f"min_severity={self._config.min_severity}, "
            f"enable_ai_analysis={self._config.enable_ai_analysis}"
        )

    def get_config(self) -> ErrorRouterConfig:
        """Get current configuration."""
        return self._config

    def get_routing_stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        return {
            "devin_enabled": self._config.enable_devin,
            "min_severity": self._config.min_severity,
            "ai_analysis_enabled": self._config.enable_ai_analysis,
        }


# Global singleton instance
error_router = ErrorRouterService()


def route_error_to_devin(
    error: Exception,
    category: str = "runtime_error",
    event: str = "exception",
    context: Optional[dict[str, Any]] = None,
    source_repo: Optional[str] = None,
) -> RoutingResult:
    """Convenience function to route an exception to Devin.

    This function uses the intelligent error router which:
    1. Analyzes the error's root cause using AI
    2. Checks against active Devin sessions and open PRs
    3. Only sends errors that are NOT duplicates of active work

    Args:
        error: The exception to route
        category: Error category (e.g., "runtime_error", "api_error")
        event: Event type (e.g., "exception", "timeout")
        context: Additional context information
        source_repo: Source repository (defaults to JurisTechLLC/OpenDevin)

    Returns:
        RoutingResult with success status and session details

    Example:
        try:
            # ... code that might fail
        except Exception as e:
            route_error_to_devin(e, category="agent_error", context={"agent_id": "123"})
            raise
    """
    import traceback

    # Extract code location from traceback
    code_location = None
    tb = traceback.extract_tb(error.__traceback__)
    if tb:
        last_frame = tb[-1]
        code_location = f"{last_frame.filename}:{last_frame.lineno}"

    error_report = ErrorReport(
        category=category,
        event=event,
        message=str(error),
        stack_trace=traceback.format_exc(),
        code_location=code_location,
        context=context,
        severity="ERROR",
        source_repo=source_repo,
    )

    return error_router.route_error_sync(error_report)
