"""Tests for policy-driven trace archive results."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.agent_trace_export import (
    AgentTraceExportFormat,
)
from app.schemas.agent_trace_file import (
    AgentTraceFileWriteResult,
)
from app.schemas.agent_trace_policy_archive import (
    AgentTracePolicyArchiveResult,
)
from app.schemas.agent_trace_summary import (
    AgentTraceOutcome,
)


def written_file(
    tmp_path: Path,
) -> AgentTraceFileWriteResult:
    """Return one valid written-file result."""

    return AgentTraceFileWriteResult(
        trace_id="trace-001",
        format=AgentTraceExportFormat.JSON,
        path=(tmp_path / "trace-001.json").resolve(),
        byte_count=100,
        overwritten=False,
    )


def test_result_accepts_archived_files(
    tmp_path: Path,
) -> None:
    result = AgentTracePolicyArchiveResult(
        trace_id="trace-001",
        outcome=AgentTraceOutcome.COMPLETED,
        archived=True,
        files=[written_file(tmp_path)],
        reason="Trace archived.",
    )

    assert result.archived is True


def test_archived_result_requires_files() -> None:
    with pytest.raises(
        ValidationError,
        match="must contain files",
    ):
        AgentTracePolicyArchiveResult(
            trace_id="trace-001",
            outcome=AgentTraceOutcome.COMPLETED,
            archived=True,
            files=[],
            reason="Trace archived.",
        )


def test_non_archived_result_rejects_files(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain files",
    ):
        AgentTracePolicyArchiveResult(
            trace_id="trace-001",
            outcome=AgentTraceOutcome.INCOMPLETE,
            archived=False,
            files=[written_file(tmp_path)],
            reason="Trace skipped.",
        )
