"""Tests for delivering failed maintenance alerts."""

from pathlib import Path

from app.schemas.agent_trace_alert_notification import (
    AgentTraceAlertNotificationStatus,
)
from app.schemas.agent_trace_maintenance_alert import (
    AgentTraceMaintenanceAlertSeverity,
)
from app.tracing.agent_trace_maintenance_notification_service import (
    AgentTraceMaintenanceNotificationService,
)
from app.tracing.agent_trace_maintenance_operations_service import (
    AgentTraceMaintenanceOperationsService,
)
from app.tracing.agent_trace_maintenance_service import (
    AgentTraceMaintenanceService,
)
from app.tracing.in_memory_agent_trace_alert_notifier import (
    InMemoryAgentTraceAlertNotifier,
)
from tests.test_agent_trace_maintenance_failure import (
    FailingArchiveService,
    SuccessfulRetentionService,
    policy,
)
from tests.test_in_memory_agent_trace_alert_notifier import (
    FixedNotificationIdGenerator,
)


def test_partial_failure_sends_warning(
    tmp_path: Path,
) -> None:
    notifier = InMemoryAgentTraceAlertNotifier(
        id_generator=FixedNotificationIdGenerator()
    )

    service = AgentTraceMaintenanceNotificationService(
        operations_service=(
            AgentTraceMaintenanceOperationsService(
                maintenance_service=(
                    AgentTraceMaintenanceService(
                        archive_service=(
                            FailingArchiveService()
                        ),
                        retention_service=(
                            SuccessfulRetentionService(
                                tmp_path
                            )
                        ),
                        retention_policy=policy(),
                    )
                )
            )
        ),
        notifier=notifier,
        channel="memory",
        destination="operations",
    )

    result = service.run("trace-001")

    assert result.operations.alert.required is True
    assert result.operations.alert.severity is (
        AgentTraceMaintenanceAlertSeverity.WARNING
    )
    assert result.notification.status is (
        AgentTraceAlertNotificationStatus.SENT
    )
    assert result.notification.notification_id == (
        "notification-001"
    )
    assert len(notifier.results()) == 1
