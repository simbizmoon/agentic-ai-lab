"""Tests for agent trace export schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.agent_trace_export import (
    AgentTraceExportFormat,
    AgentTraceExportResult,
)


def test_export_result_accepts_valid_values() -> None:
    result = AgentTraceExportResult(
        trace_id="trace-001",
        format=AgentTraceExportFormat.JSON,
        content='{"trace_id": "trace-001"}',
        media_type="application/json",
        file_extension=".json",
    )

    assert result.file_extension == ".json"


def test_export_result_rejects_blank_content() -> None:
    with pytest.raises(
        ValidationError,
        match="content must not be blank",
    ):
        AgentTraceExportResult(
            trace_id="trace-001",
            format=AgentTraceExportFormat.TEXT,
            content=" ",
            media_type="text/plain",
            file_extension=".txt",
        )


def test_export_result_requires_extension_dot() -> None:
    with pytest.raises(
        ValidationError,
        match="must start with a dot",
    ):
        AgentTraceExportResult(
            trace_id="trace-001",
            format=AgentTraceExportFormat.TEXT,
            content="Trace content.",
            media_type="text/plain",
            file_extension="txt",
        )
