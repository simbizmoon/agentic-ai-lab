"""Tests for agent trace file schemas."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.agent_trace_export import (
    AgentTraceExportFormat,
)
from app.schemas.agent_trace_file import (
    AgentTraceFileWriteRequest,
    AgentTraceFileWriteResult,
)


def test_write_request_accepts_default_values() -> None:
    request = AgentTraceFileWriteRequest()

    assert request.file_name is None
    assert request.overwrite is False


def test_write_request_rejects_blank_file_name() -> None:
    with pytest.raises(
        ValidationError,
        match="file_name must not be blank",
    ):
        AgentTraceFileWriteRequest(
            file_name=" "
        )


def test_write_result_requires_absolute_path() -> None:
    with pytest.raises(
        ValidationError,
        match="path must be absolute",
    ):
        AgentTraceFileWriteResult(
            trace_id="trace-001",
            format=AgentTraceExportFormat.JSON,
            path=Path("trace.json"),
            byte_count=10,
            overwritten=False,
        )


def test_write_result_accepts_absolute_path(
    tmp_path: Path,
) -> None:
    result = AgentTraceFileWriteResult(
        trace_id="trace-001",
        format=AgentTraceExportFormat.JSON,
        path=(tmp_path / "trace.json").resolve(),
        byte_count=10,
        overwritten=False,
    )

    assert result.byte_count == 10
