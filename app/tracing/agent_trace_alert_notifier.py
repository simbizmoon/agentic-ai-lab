"""Notification port for agent trace maintenance alerts."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.agent_trace_alert_notification import (
    AgentTraceAlertNotificationRequest,
    AgentTraceAlertNotificationResult,
)


class AgentTraceAlertNotifier(ABC):
    """Deliver maintenance alerts through one channel."""

    @abstractmethod
    def notify(
        self,
        request: AgentTraceAlertNotificationRequest,
    ) -> AgentTraceAlertNotificationResult:
        """Deliver or skip one alert notification."""
