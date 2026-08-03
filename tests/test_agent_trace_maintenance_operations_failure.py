"""Tests for failed trace maintenance operations views."""

from pathlib import Path

from app.schemas.agent_trace_maintenance import (
    AgentTraceMaintenanceStatus,
)
from app.schemas.agent_trace_maintenance_alert import (
    AgentTraceMaintenanceAlertCode,
    AgentTraceMaintenanceAlertSeverity,
)
from app.tracing.agent_trace_maintenance_operations_service import (
    AgentTraceMaintenanceOperationsService,
)
from app.tracing.agent_trace_maintenance_service import (
    AgentTraceMaintenanceService,
)
from tests.test_agent_trace_maintenance_failure import (
    FailingArchiveService,
    FailingRetentionService,
    SuccessfulRetentionService,
    policy,
)


def test_partial_failure_returns_warning_report(
    tmp_path: Path,
) -> None:
    result = AgentTraceMaintenanceOperationsService(
        maintenance_service=AgentTraceMaintenanceService(
            archive_service=FailingArchiveService(),
            retention_service=SuccessfulRetentionService(
                tmp_path
            ),
            retention_policy=policy(),
        )
    ).run("trace-001")

    assert result.maintenance.status is (
        AgentTraceMaintenanceStatus.PARTIAL_SUCCESS
    )
    assert result.report.error_count == 1
    assert result.alert.required is True
    assert result.alert.severity is (
        AgentTraceMaintenanceAlertSeverity.WARNING
    )
    assert result.alert.codes == [
        (
            AgentTraceMaintenanceAlertCode
            .ARCHIVE_STAGE_FAILED
        )
    ]


def test_complete_failure_returns_critical_report() -> None:
    result = AgentTraceMaintenanceOperationsService(
        maintenance_service=AgentTraceMaintenanceService(
            archive_service=FailingArchiveService(),
            retention_service=FailingRetentionService(),
            retention_policy=policy(),
        )
    ).run("trace-001")

    assert result.maintenance.status is (
        AgentTraceMaintenanceStatus.FAILED
    )
    assert result.report.error_count == 2
    assert result.alert.required is True
    assert result.alert.severity is (
        AgentTraceMaintenanceAlertSeverity.CRITICAL
    )
    assert (
        AgentTraceMaintenanceAlertCode
        .MULTIPLE_STAGES_FAILED
        in result.alert.codes
    )
