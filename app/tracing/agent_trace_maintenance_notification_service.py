"""Run trace maintenance operations and deliver alerts."""

from __future__ import annotations

from app.schemas.agent_trace_alert_notification import (
    AgentTraceAlertNotificationRequest,
)
from app.schemas.agent_trace_maintenance_notification import (
    AgentTraceMaintenanceNotificationResult,
)
from app.tracing.agent_trace_alert_notifier import (
    AgentTraceAlertNotifier,
)
from app.tracing.agent_trace_maintenance_operations_service import (
    AgentTraceMaintenanceOperationsService,
)


class AgentTraceMaintenanceNotificationService:
    """Run maintenance operations and notify their alert."""

    def __init__(
        self,
        *,
        operations_service: (
            AgentTraceMaintenanceOperationsService
        ),
        notifier: AgentTraceAlertNotifier,
        channel: str,
        destination: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        if not channel.strip():
            raise ValueError(
                "channel must not be blank"
            )

        if not destination.strip():
            raise ValueError(
                "destination must not be blank"
            )

        self._operations_service = operations_service
        self._notifier = notifier
        self._channel = channel
        self._destination = destination
        self._metadata = dict(metadata or {})

    @property
    def operations_service(
        self,
    ) -> AgentTraceMaintenanceOperationsService:
        """Return the configured operations service."""

        return self._operations_service

    @property
    def notifier(self) -> AgentTraceAlertNotifier:
        """Return the configured notifier."""

        return self._notifier

    @property
    def channel(self) -> str:
        """Return the configured notification channel."""

        return self._channel

    @property
    def destination(self) -> str:
        """Return the configured notification destination."""

        return self._destination

    def run(
        self,
        trace_id: str,
    ) -> AgentTraceMaintenanceNotificationResult:
        """Run maintenance operations and notify the result."""

        if not trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        operations = self.operations_service.run(
            trace_id
        )

        notification = self.notifier.notify(
            AgentTraceAlertNotificationRequest(
                alert=operations.alert,
                channel=self.channel,
                destination=self.destination,
                metadata=dict(self._metadata),
            )
        )

        return AgentTraceMaintenanceNotificationResult(
            trace_id=trace_id,
            operations=operations,
            notification=notification,
        )
