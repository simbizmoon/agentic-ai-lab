"""In-memory notifier for trace maintenance alerts."""

from __future__ import annotations

from threading import RLock

from app.schemas.agent_trace_alert_notification import (
    AgentTraceAlertNotificationRequest,
    AgentTraceAlertNotificationResult,
    AgentTraceAlertNotificationStatus,
)
from app.tracing.agent_trace_alert_notifier import (
    AgentTraceAlertNotifier,
)
from app.tracing.notification_id_generator import (
    NotificationIdGenerator,
    UUIDNotificationIdGenerator,
)


class InMemoryAgentTraceAlertNotifier(
    AgentTraceAlertNotifier
):
    """Record delivered alert notifications in memory."""

    def __init__(
        self,
        *,
        id_generator: NotificationIdGenerator | None = None,
    ) -> None:
        self._id_generator = (
            id_generator or UUIDNotificationIdGenerator()
        )
        self._requests: list[
            AgentTraceAlertNotificationRequest
        ] = []
        self._results: list[
            AgentTraceAlertNotificationResult
        ] = []
        self._lock = RLock()

    @property
    def id_generator(self) -> NotificationIdGenerator:
        """Return the configured identifier generator."""

        return self._id_generator

    def notify(
        self,
        request: AgentTraceAlertNotificationRequest,
    ) -> AgentTraceAlertNotificationResult:
        """Record a required alert or skip a non-alert."""

        if not request.alert.required:
            result = AgentTraceAlertNotificationResult(
                trace_id=request.alert.trace_id,
                status=(
                    AgentTraceAlertNotificationStatus.SKIPPED
                ),
                channel=request.channel,
                destination=request.destination,
                message=(
                    "Notification skipped because the alert "
                    "is not required."
                ),
                notification_id=None,
            )

            with self._lock:
                self._requests.append(
                    request.model_copy(deep=True)
                )
                self._results.append(
                    result.model_copy(deep=True)
                )

            return result

        result = AgentTraceAlertNotificationResult(
            trace_id=request.alert.trace_id,
            status=AgentTraceAlertNotificationStatus.SENT,
            channel=request.channel,
            destination=request.destination,
            message=request.alert.message,
            notification_id=(
                self.id_generator.generate()
            ),
        )

        with self._lock:
            self._requests.append(
                request.model_copy(deep=True)
            )
            self._results.append(
                result.model_copy(deep=True)
            )

        return result

    def requests(
        self,
    ) -> list[AgentTraceAlertNotificationRequest]:
        """Return defensive copies of notification requests."""

        with self._lock:
            return [
                request.model_copy(deep=True)
                for request in self._requests
            ]

    def results(
        self,
    ) -> list[AgentTraceAlertNotificationResult]:
        """Return defensive copies of notification results."""

        with self._lock:
            return [
                result.model_copy(deep=True)
                for result in self._results
            ]

    def clear(self) -> None:
        """Remove all recorded notification attempts."""

        with self._lock:
            self._requests.clear()
            self._results.clear()
