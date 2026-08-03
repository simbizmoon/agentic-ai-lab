"""Tests for trace maintenance operations results."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.agent_trace_maintenance import (
    AgentTraceMaintenanceResult,
    AgentTraceMaintenanceStatus,
)
from app.schemas.agent_trace_maintenance_alert import (
    AgentTraceMaintenanceAlert,
    AgentTraceMaintenanceAlertCode,
    AgentTraceMaintenanceAlertSeverity,
)
from app.schemas.agent_trace_maintenance_operations import (
    AgentTraceMaintenanceOperationsResult,
)
from app.schemas.agent_trace_maintenance_report import (
    AgentTraceMaintenanceReport,
)
from app.schemas.agent_trace_policy_archive import (
    AgentTracePolicyArchiveResult,
)
from app.schemas.agent_trace_retention import (
    AgentTraceRetentionResult,
)
from app.schemas.agent_trace_summary import (
    AgentTraceOutcome,
)


def maintenance(
    tmp_path: Path,
    *,
    trace_id: str = "trace-001",
) -> AgentTraceMaintenanceResult:
    """Return one successful maintenance result."""

    return AgentTraceMaintenanceResult(
        trace_id=trace_id,
        status=AgentTraceMaintenanceStatus.SUCCESS,
        archive=AgentTracePolicyArchiveResult(
            trace_id=trace_id,
            outcome=AgentTraceOutcome.INCOMPLETE,
            archived=False,
            files=[],
            reason="Skipped by policy.",
        ),
        retention=AgentTraceRetentionResult(
            output_directory=tmp_path.resolve(),
            scanned_file_count=0,
            eligible_file_count=0,
            deleted_file_count=0,
            retained_file_count=0,
            dry_run=False,
            eligible_paths=[],
            deleted_paths=[],
        ),
        errors=[],
    )


def report(
    *,
    trace_id: str = "trace-001",
) -> AgentTraceMaintenanceReport:
    """Return one successful operations report."""

    return AgentTraceMaintenanceReport(
        trace_id=trace_id,
        status=AgentTraceMaintenanceStatus.SUCCESS,
        headline="Maintenance completed.",
        details=["Maintenance completed normally."],
        archived_file_count=0,
        scanned_file_count=0,
        deleted_file_count=0,
        error_count=0,
    )


def alert(
    *,
    trace_id: str = "trace-001",
) -> AgentTraceMaintenanceAlert:
    """Return one no-alert decision."""

    return AgentTraceMaintenanceAlert(
        trace_id=trace_id,
        required=False,
        severity=AgentTraceMaintenanceAlertSeverity.NONE,
        codes=[],
        message="No alert required.",
    )


def test_operations_result_accepts_consistent_views(
    tmp_path: Path,
) -> None:
    result = AgentTraceMaintenanceOperationsResult(
        trace_id="trace-001",
        maintenance=maintenance(tmp_path),
        report=report(),
        alert=alert(),
    )

    assert result.alert.required is False


def test_operations_result_rejects_trace_mismatch(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValidationError,
        match="trace IDs must match",
    ):
        AgentTraceMaintenanceOperationsResult(
            trace_id="trace-001",
            maintenance=maintenance(tmp_path),
            report=report(trace_id="trace-002"),
            alert=alert(),
        )


def test_operations_result_rejects_status_mismatch(
    tmp_path: Path,
) -> None:
    mismatched_report = report().model_copy(
        update={
            "status": (
                AgentTraceMaintenanceStatus
                .PARTIAL_SUCCESS
            )
        }
    )

    with pytest.raises(
        ValidationError,
        match="report status must match",
    ):
        AgentTraceMaintenanceOperationsResult(
            trace_id="trace-001",
            maintenance=maintenance(tmp_path),
            report=mismatched_report,
            alert=alert(),
        )


def test_success_rejects_required_alert(
    tmp_path: Path,
) -> None:
    required_alert = AgentTraceMaintenanceAlert(
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
        message="Attention required.",
    )

    with pytest.raises(ValidationError):
        AgentTraceMaintenanceOperationsResult(
            trace_id="trace-001",
            maintenance=maintenance(tmp_path),
            report=report(),
            alert=required_alert,
        )
