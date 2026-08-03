"""Tests for trace maintenance alert evaluation."""

from pathlib import Path

from app.schemas.agent_trace_maintenance import (
    AgentTraceMaintenanceError,
    AgentTraceMaintenanceResult,
    AgentTraceMaintenanceStage,
    AgentTraceMaintenanceStatus,
)
from app.schemas.agent_trace_maintenance_alert import (
    AgentTraceMaintenanceAlertCode,
    AgentTraceMaintenanceAlertSeverity,
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
from app.tracing.agent_trace_maintenance_alert_evaluator import (
    AgentTraceMaintenanceAlertEvaluator,
)


def archive_result() -> AgentTracePolicyArchiveResult:
    """Return one successful archive stage."""

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
        scanned_file_count=0,
        eligible_file_count=0,
        deleted_file_count=0,
        retained_file_count=0,
        dry_run=False,
        eligible_paths=[],
        deleted_paths=[],
    )


def error(
    stage: AgentTraceMaintenanceStage,
) -> AgentTraceMaintenanceError:
    """Return one stage error."""

    return AgentTraceMaintenanceError(
        stage=stage,
        error_type="RuntimeError",
        message="Stage failed.",
    )


def test_success_requires_no_alert(
    tmp_path: Path,
) -> None:
    alert = (
        AgentTraceMaintenanceAlertEvaluator()
        .evaluate(
            AgentTraceMaintenanceResult(
                trace_id="trace-001",
                status=(
                    AgentTraceMaintenanceStatus.SUCCESS
                ),
                archive=archive_result(),
                retention=retention_result(tmp_path),
                errors=[],
            )
        )
    )

    assert alert.required is False
    assert alert.severity is (
        AgentTraceMaintenanceAlertSeverity.NONE
    )


def test_partial_failure_creates_warning(
    tmp_path: Path,
) -> None:
    alert = (
        AgentTraceMaintenanceAlertEvaluator()
        .evaluate(
            AgentTraceMaintenanceResult(
                trace_id="trace-001",
                status=(
                    AgentTraceMaintenanceStatus
                    .PARTIAL_SUCCESS
                ),
                archive=None,
                retention=retention_result(tmp_path),
                errors=[
                    error(
                        AgentTraceMaintenanceStage.ARCHIVE
                    )
                ],
            )
        )
    )

    assert alert.required is True
    assert alert.severity is (
        AgentTraceMaintenanceAlertSeverity.WARNING
    )
    assert alert.codes == [
        (
            AgentTraceMaintenanceAlertCode
            .ARCHIVE_STAGE_FAILED
        )
    ]


def test_full_failure_creates_critical_alert() -> None:
    alert = (
        AgentTraceMaintenanceAlertEvaluator()
        .evaluate(
            AgentTraceMaintenanceResult(
                trace_id="trace-001",
                status=(
                    AgentTraceMaintenanceStatus.FAILED
                ),
                archive=None,
                retention=None,
                errors=[
                    error(
                        AgentTraceMaintenanceStage.ARCHIVE
                    ),
                    error(
                        AgentTraceMaintenanceStage.RETENTION
                    ),
                ],
            )
        )
    )

    assert alert.severity is (
        AgentTraceMaintenanceAlertSeverity.CRITICAL
    )
    assert alert.codes == [
        (
            AgentTraceMaintenanceAlertCode
            .MULTIPLE_STAGES_FAILED
        ),
        (
            AgentTraceMaintenanceAlertCode
            .ARCHIVE_STAGE_FAILED
        ),
        (
            AgentTraceMaintenanceAlertCode
            .RETENTION_STAGE_FAILED
        ),
    ]
