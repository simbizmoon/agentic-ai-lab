"""Tests for the in-memory trace alert notifier."""

from app.schemas.agent_trace_alert_notification import (
    AgentTraceAlertNotificationRequest,
    AgentTraceAlertNotificationStatus,
)
from app.schemas.agent_trace_maintenance_alert import (
    AgentTraceMaintenanceAlert,
    AgentTraceMaintenanceAlertCode,
    AgentTraceMaintenanceAlertSeverity,
)
from app.tracing.in_memory_agent_trace_alert_notifier import (
    InMemoryAgentTraceAlertNotifier,
)
from app.tracing.notification_id_generator import (
    NotificationIdGenerator,
)


class FixedNotificationIdGenerator(
    NotificationIdGenerator
):
    """Return deterministic notification identifiers."""

    def __init__(self) -> None:
        self._number = 0

    def generate(self) -> str:
        self._number += 1
        return f"notification-{self._number:03d}"


def required_alert() -> AgentTraceMaintenanceAlert:
    """Return one alert requiring notification."""

    return AgentTraceMaintenanceAlert(
        trace_id="trace-001",
        required=True,
        severity=(
            AgentTraceMaintenanceAlertSeverity.WARNING
        ),
        codes=[
            (
                AgentTraceMaintenanceAlertCode
                .ARCHIVE_STAGE_FAILED
            )
        ],
        message="Archive stage failed.",
    )


def no_alert() -> AgentTraceMaintenanceAlert:
    """Return one non-required alert."""

    return AgentTraceMaintenanceAlert(
        trace_id="trace-001",
        required=False,
        severity=AgentTraceMaintenanceAlertSeverity.NONE,
        codes=[],
        message="No alert required.",
    )


def request(
    alert: AgentTraceMaintenanceAlert,
) -> AgentTraceAlertNotificationRequest:
    """Return one notification request."""

    return AgentTraceAlertNotificationRequest(
        alert=alert,
        channel="memory",
        destination="operations",
    )


def notifier() -> InMemoryAgentTraceAlertNotifier:
    """Return one deterministic notifier."""

    return InMemoryAgentTraceAlertNotifier(
        id_generator=FixedNotificationIdGenerator()
    )


def test_notifier_sends_required_alert() -> None:
    value = notifier()

    result = value.notify(
        request(required_alert())
    )

    assert result.status is (
        AgentTraceAlertNotificationStatus.SENT
    )
    assert result.notification_id == "notification-001"
    assert len(value.requests()) == 1
    assert len(value.results()) == 1


def test_notifier_skips_non_required_alert() -> None:
    value = notifier()

    result = value.notify(
        request(no_alert())
    )

    assert result.status is (
        AgentTraceAlertNotificationStatus.SKIPPED
    )
    assert result.notification_id is None
    assert len(value.requests()) == 1


def test_notifier_generates_sequential_ids() -> None:
    value = notifier()

    first = value.notify(request(required_alert()))
    second = value.notify(request(required_alert()))

    assert first.notification_id == "notification-001"
    assert second.notification_id == "notification-002"


def test_notifier_returns_defensive_copies() -> None:
    value = notifier()
    value.notify(request(required_alert()))

    first_results = value.results()
    first_results.clear()

    assert len(value.results()) == 1


def test_notifier_clear_removes_history() -> None:
    value = notifier()
    value.notify(request(required_alert()))

    value.clear()

    assert value.requests() == []
    assert value.results() == []
