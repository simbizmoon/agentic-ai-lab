"""Tests for agent trace maintenance results."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.agent_trace_maintenance import (
    AgentTraceMaintenanceResult,
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
            archive=archive_result(
                trace_id=" "
            ),
            retention=retention_result(tmp_path),
        )
