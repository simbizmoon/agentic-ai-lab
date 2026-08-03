"""Tests for trace alert notification schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.agent_trace_alert_notification import (
    AgentTraceAlertNotificationRequest,
    AgentTraceAlertNotificationResult,
    AgentTraceAlertNotificationStatus,
)
from app.schemas.agent_trace_maintenance_alert import (
    AgentTraceMaintenanceAlert,
    AgentTraceMaintenanceAlertCode,
    AgentTraceMaintenanceAlertSeverity,
)


def alert(
    *,
    required: bool = True,
) -> AgentTraceMaintenanceAlert:
    """Return one valid maintenance alert."""

    if required:
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
            message="Archive requires attention.",
        )

    return AgentTraceMaintenanceAlert(
        trace_id="trace-001",
        required=False,
        severity=AgentTraceMaintenanceAlertSeverity.NONE,
        codes=[],
        message="No alert required.",
    )


def test_request_accepts_valid_target() -> None:
    request = AgentTraceAlertNotificationRequest(
        alert=alert(),
        channel="memory",
        destination="operations",
        metadata={"environment": "test"},
    )

    assert request.destination == "operations"


def test_request_rejects_blank_channel() -> None:
    with pytest.raises(
        ValidationError,
        match="channel must not be blank",
    ):
        AgentTraceAlertNotificationRequest(
            alert=alert(),
            channel=" ",
            destination="operations",
        )


def test_sent_result_requires_notification_id() -> None:
    with pytest.raises(
        ValidationError,
        match="requires notification_id",
    ):
        AgentTraceAlertNotificationResult(
            trace_id="trace-001",
            status=AgentTraceAlertNotificationStatus.SENT,
            channel="memory",
            destination="operations",
            message="Alert sent.",
            notification_id=None,
        )


def test_skipped_result_rejects_notification_id() -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain notification_id",
    ):
        AgentTraceAlertNotificationResult(
            trace_id="trace-001",
            status=(
                AgentTraceAlertNotificationStatus.SKIPPED
            ),
            channel="memory",
            destination="operations",
            message="Alert skipped.",
            notification_id="notification-001",
        )
