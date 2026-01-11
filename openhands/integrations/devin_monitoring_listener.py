"""Devin Monitoring Listener for OpenHands.

A MonitoringListener implementation that reports errors to Devin.ai for automatic review and repair.
This integrates with OpenHands' existing monitoring infrastructure.
"""

import traceback
from typing import Optional

from openhands.core.config.openhands_config import OpenHandsConfig
from openhands.core.logger import openhands_logger as logger
from openhands.events.event import Event
from openhands.events.observation.error import ErrorObservation
from openhands.integrations.devin_integration import (
    DevinIntegrationService,
    ErrorContext,
    devin_integration,
)
from openhands.server.monitoring import MonitoringListener


class DevinMonitoringListener(MonitoringListener):
    """A MonitoringListener that reports errors to Devin.ai for automatic review and repair.
    
    This listener extends the base MonitoringListener to automatically report
    ErrorObservation events and agent session failures to Devin.
    
    To use this listener, set the server_config.monitoring_listener_class to:
    'openhands.integrations.devin_monitoring_listener.DevinMonitoringListener'
    
    Configuration via environment variables:
    - DEVIN_API_KEY: Required. Your Devin.ai API key.
    - DISABLE_DEVIN_AUTO_REVIEW: Set to 'true' to disable automatic error reporting.
    """
    
    def __init__(self, devin_service: Optional[DevinIntegrationService] = None):
        """Initialize the DevinMonitoringListener.
        
        Args:
            devin_service: Optional DevinIntegrationService instance. 
                          If not provided, uses the global singleton.
        """
        self._devin_service = devin_service or devin_integration
        
    def on_session_event(self, event: Event) -> None:
        """Track metrics about events being added to a Session's EventStream.
        
        Reports ErrorObservation events to Devin for automatic review.
        """
        if isinstance(event, ErrorObservation):
            self._report_error_observation(event)
    
    def on_agent_session_start(self, success: bool, duration: float) -> None:
        """Track an agent session start.
        
        Reports failed session starts to Devin for investigation.
        """
        if not success:
            error_context = ErrorContext(
                category="agent_session",
                event="start_failure",
                message=f"Agent session failed to start after {duration:.2f} seconds",
                context={
                    "duration_seconds": duration,
                    "success": success
                },
                severity="ERROR"
            )
            self._report_to_devin(error_context)
    
    def on_create_conversation(self) -> None:
        """Track the beginning of conversation creation."""
        # We don't report conversation creation to Devin
        # This is just a tracking event, not an error
        pass
    
    def _report_error_observation(self, error: ErrorObservation) -> None:
        """Report an ErrorObservation to Devin."""
        error_context = ErrorContext(
            category="agent_error",
            event="error_observation",
            message=error.content,
            context={
                "error_id": error.error_id,
                "observation_type": error.observation
            },
            severity="ERROR"
        )
        self._report_to_devin(error_context)
    
    def _report_to_devin(self, error_context: ErrorContext) -> None:
        """Report an error to Devin asynchronously.
        
        This method is non-blocking and will not raise exceptions.
        """
        try:
            if not self._devin_service.is_enabled():
                return
            
            result = self._devin_service.report_error_sync(error_context)
            
            if result.success:
                logger.info(
                    f"[DevinMonitoringListener] Error reported to Devin: {result.devin_session_url}"
                )
            elif result.skipped_reason:
                logger.debug(
                    f"[DevinMonitoringListener] Error report skipped: {result.skipped_reason}"
                )
            elif result.error:
                logger.warning(
                    f"[DevinMonitoringListener] Failed to report error to Devin: {result.error}"
                )
        except Exception as e:
            # Never let monitoring failures affect the main application
            logger.error(f"[DevinMonitoringListener] Unexpected error: {e}")
    
    @classmethod
    def get_instance(
        cls,
        config: OpenHandsConfig,
    ) -> 'DevinMonitoringListener':
        """Factory method to create a DevinMonitoringListener instance.
        
        This method is called by the OpenHands server to instantiate the listener.
        """
        return cls()
