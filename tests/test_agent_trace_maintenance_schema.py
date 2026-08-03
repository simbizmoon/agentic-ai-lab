"""Tests for agent trace maintenance results."""

from pathlib import Path

import pytest
from pydantic import ValidationError

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


def archive_result(
    *,
    trace_id: str = "trace-001",
) -> AgentTracePolicyArchiveResult:
    """Return one skipped archive result."""

    return AgentTracePolicyArchiveResult(
        trace_id=trace_id,
        outcome=AgentTraceOutcome.INCOMPLETE,
        archived=False,
        files=[],
        reason="Trace skipped.",
    )


def retention_result(
    tmp_path: Path,
) -> AgentTraceRetentionResult:
    """Return one empty retention result."""

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


def test_result_accepts_matching_trace_id(
    tmp_path: Path,
) -> None:
    result = AgentTraceMaintenanceResult(
        trace_id="trace-001",
        status=AgentTraceMaintenanceStatus.SUCCESS,
        archive=archive_result(),
        retention=retention_result(tmp_path),
    )

    assert result.trace_id == "trace-001"


def test_result_rejects_mismatched_trace_id(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValidationError,
        match="archive trace_id must match",
    ):
        AgentTraceMaintenanceResult(
            trace_id="trace-001",
            status=AgentTraceMaintenanceStatus.SUCCESS,
            archive=archive_result(
                trace_id="trace-002"
            ),
            retention=retention_result(tmp_path),
        )


def test_result_rejects_blank_trace_id(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValidationError,
        match="trace_id must not be blank",
    ):
        AgentTraceMaintenanceResult(
            trace_id=" ",
            status=AgentTraceMaintenanceStatus.SUCCESS,
            archive=archive_result(
                trace_id=" "
            ),
            retention=retention_result(tmp_path),
        )


def maintenance_error(
    stage: AgentTraceMaintenanceStage,
) -> AgentTraceMaintenanceError:
    """Return one structured maintenance error."""

    return AgentTraceMaintenanceError(
        stage=stage,
        error_type="RuntimeError",
        message="Stage failed.",
    )


def test_result_accepts_archive_only_partial_success() -> None:
    result = AgentTraceMaintenanceResult(
        trace_id="trace-001",
        status=(
            AgentTraceMaintenanceStatus.PARTIAL_SUCCESS
        ),
        archive=archive_result(),
        retention=None,
        errors=[
            maintenance_error(
                AgentTraceMaintenanceStage.RETENTION
            )
        ],
    )

    assert result.archive is not None
    assert result.retention is None


def test_result_accepts_failed_maintenance() -> None:
    result = AgentTraceMaintenanceResult(
        trace_id="trace-001",
        status=AgentTraceMaintenanceStatus.FAILED,
        archive=None,
        retention=None,
        errors=[
            maintenance_error(
                AgentTraceMaintenanceStage.ARCHIVE
            ),
            maintenance_error(
                AgentTraceMaintenanceStage.RETENTION
            ),
        ],
    )

    assert len(result.errors) == 2


def test_success_rejects_errors(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain errors",
    ):
        AgentTraceMaintenanceResult(
            trace_id="trace-001",
            status=AgentTraceMaintenanceStatus.SUCCESS,
            archive=archive_result(),
            retention=retention_result(tmp_path),
            errors=[
                maintenance_error(
                    AgentTraceMaintenanceStage.ARCHIVE
                )
            ],
        )


def test_partial_success_requires_one_stage(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValidationError,
        match="exactly one successful stage",
    ):
        AgentTraceMaintenanceResult(
            trace_id="trace-001",
            status=(
                AgentTraceMaintenanceStatus
                .PARTIAL_SUCCESS
            ),
            archive=archive_result(),
            retention=retention_result(tmp_path),
            errors=[
                maintenance_error(
                    AgentTraceMaintenanceStage.ARCHIVE
                )
            ],
        )
