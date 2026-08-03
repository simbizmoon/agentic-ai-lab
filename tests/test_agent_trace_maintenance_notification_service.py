"""Tests for maintenance operations notification."""

from pathlib import Path

import pytest

from app.schemas.agent_trace_alert_notification import (
    AgentTraceAlertNotificationStatus,
)
from app.schemas.agent_trace_retention import (
    AgentTraceRetentionPolicy,
)
from app.tracing.agent_trace_maintenance_notification_service import (
    AgentTraceMaintenanceNotificationService,
)
from app.tracing.agent_trace_maintenance_operations_service import (
    AgentTraceMaintenanceOperationsService,
)
from app.tracing.in_memory_agent_trace_alert_notifier import (
    InMemoryAgentTraceAlertNotifier,
)
from tests.test_agent_trace_maintenance_service import (
    maintenance_service,
)


def service(
    tmp_path: Path,
) -> AgentTraceMaintenanceNotificationService:
    """Return one successful maintenance notification service."""

    return AgentTraceMaintenanceNotificationService(
        operations_service=(
            AgentTraceMaintenanceOperationsService(
                maintenance_service=maintenance_service(
                    tmp_path,
                    retention_policy=(
                        AgentTraceRetentionPolicy(
                            maximum_file_count=10
                        )
                    ),
                )
            )
        ),
        notifier=InMemoryAgentTraceAlertNotifier(),
        channel="memory",
        destination="operations",
        metadata={"environment": "test"},
    )


def test_successful_operations_skip_notification(
    tmp_path: Path,
) -> None:
    result = service(tmp_path).run("trace-001")

    assert result.operations.alert.required is False
    assert result.notification.status is (
        AgentTraceAlertNotificationStatus.SKIPPED
    )
    assert result.notification.notification_id is None


def test_service_records_skipped_attempt(
    tmp_path: Path,
) -> None:
    value = service(tmp_path)

    value.run("trace-001")

    notifier = value.notifier

    assert isinstance(
        notifier,
        InMemoryAgentTraceAlertNotifier,
    )
    assert len(notifier.requests()) == 1
    assert len(notifier.results()) == 1


def test_service_rejects_blank_channel(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="channel must not be blank",
    ):
        AgentTraceMaintenanceNotificationService(
            operations_service=(
                AgentTraceMaintenanceOperationsService(
                    maintenance_service=maintenance_service(
                        tmp_path,
                        retention_policy=(
                            AgentTraceRetentionPolicy(
                                maximum_file_count=10
                            )
                        ),
                    )
                )
            ),
            notifier=InMemoryAgentTraceAlertNotifier(),
            channel=" ",
            destination="operations",
        )


def test_service_rejects_blank_trace_id(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="trace_id must not be blank",
    ):
        service(tmp_path).run(" ")
