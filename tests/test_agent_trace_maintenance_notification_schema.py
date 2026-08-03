"""Tests for maintenance notification results."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.agent_trace_alert_notification import (
    AgentTraceAlertNotificationResult,
    AgentTraceAlertNotificationStatus,
)
from app.schemas.agent_trace_maintenance_notification import (
    AgentTraceMaintenanceNotificationResult,
)
from app.schemas.agent_trace_maintenance_operations import (
    AgentTraceMaintenanceOperationsResult,
)
from tests.test_agent_trace_maintenance_operations_schema import (
    alert,
    maintenance,
    report,
)


def operations(
    tmp_path: Path,
    *,
    trace_id: str = "trace-001",
) -> AgentTraceMaintenanceOperationsResult:
    """Return one successful operations result."""

    return AgentTraceMaintenanceOperationsResult(
        trace_id=trace_id,
        maintenance=maintenance(
            tmp_path,
            trace_id=trace_id,
        ),
        report=report(trace_id=trace_id),
        alert=alert(trace_id=trace_id),
    )


def notification(
    *,
    trace_id: str = "trace-001",
) -> AgentTraceAlertNotificationResult:
    """Return one skipped notification."""

    return AgentTraceAlertNotificationResult(
        trace_id=trace_id,
        status=AgentTraceAlertNotificationStatus.SKIPPED,
        channel="memory",
        destination="operations",
        message="Notification skipped.",
        notification_id=None,
    )


def test_result_accepts_matching_trace_ids(
    tmp_path: Path,
) -> None:
    result = AgentTraceMaintenanceNotificationResult(
        trace_id="trace-001",
        operations=operations(tmp_path),
        notification=notification(),
    )

    assert result.trace_id == "trace-001"


def test_result_rejects_mismatched_trace_ids(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValidationError,
        match="trace IDs must match",
    ):
        AgentTraceMaintenanceNotificationResult(
            trace_id="trace-001",
            operations=operations(tmp_path),
            notification=notification(
                trace_id="trace-002"
            ),
        )
