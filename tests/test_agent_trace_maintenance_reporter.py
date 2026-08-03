"""Tests for trace maintenance operational reporting."""

from pathlib import Path

from app.schemas.agent_trace_maintenance import (
    AgentTraceMaintenanceError,
    AgentTraceMaintenanceResult,
    AgentTraceMaintenanceStage,
    AgentTraceMaintenanceStatus,
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
from app.tracing.agent_trace_maintenance_reporter import (
    AgentTraceMaintenanceReporter,
)


def archive_result() -> AgentTracePolicyArchiveResult:
    """Return one skipped but successful archive stage."""

    return AgentTracePolicyArchiveResult(
        trace_id="trace-001",
        outcome=AgentTraceOutcome.INCOMPLETE,
        archived=False,
        files=[],
        reason="Skipped by policy.",
    )


def retention_result(
    tmp_path: Path,
) -> AgentTraceRetentionResult:
    """Return one successful retention stage."""

    return AgentTraceRetentionResult(
        output_directory=tmp_path.resolve(),
        scanned_file_count=3,
        eligible_file_count=1,
        deleted_file_count=1,
        retained_file_count=2,
        dry_run=False,
        eligible_paths=[
            (tmp_path / "old.json").resolve()
        ],
        deleted_paths=[
            (tmp_path / "old.json").resolve()
        ],
    )


def test_reporter_builds_success_report(
    tmp_path: Path,
) -> None:
    report = AgentTraceMaintenanceReporter().build(
        AgentTraceMaintenanceResult(
            trace_id="trace-001",
            status=AgentTraceMaintenanceStatus.SUCCESS,
            archive=archive_result(),
            retention=retention_result(tmp_path),
            errors=[],
        )
    )

    assert report.error_count == 0
    assert report.scanned_file_count == 3
    assert report.deleted_file_count == 1
    assert "successfully" in report.headline


def test_reporter_includes_stage_error(
    tmp_path: Path,
) -> None:
    report = AgentTraceMaintenanceReporter().build(
        AgentTraceMaintenanceResult(
            trace_id="trace-001",
            status=(
                AgentTraceMaintenanceStatus
                .PARTIAL_SUCCESS
            ),
            archive=None,
            retention=retention_result(tmp_path),
            errors=[
                AgentTraceMaintenanceError(
                    stage=(
                        AgentTraceMaintenanceStage.ARCHIVE
                    ),
                    error_type="RuntimeError",
                    message="Archive unavailable.",
                )
            ],
        )
    )

    assert report.error_count == 1
    assert any(
        "Archive unavailable."
        in detail
        for detail in report.details
    )
