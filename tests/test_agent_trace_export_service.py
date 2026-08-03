"""Tests for recorded planning-agent trace exports."""

from datetime import UTC, datetime, timedelta

from app.schemas.agent_trace import (
    AgentTraceEvent,
    AgentTraceEventType,
)
from app.schemas.agent_trace_export import (
    AgentTraceExportFormat,
)
from app.tracing.agent_trace_export_service import (
    AgentTraceExportService,
)
from app.tracing.agent_trace_read_service import (
    AgentTraceReadService,
)
from app.tracing.in_memory_trace_recorder import (
    InMemoryTraceRecorder,
)

STARTED = datetime(
    2026,
    8,
    4,
    5,
    30,
    tzinfo=UTC,
)


def recorder() -> InMemoryTraceRecorder:
    """Return one recorder with a completed trace."""

    value = InMemoryTraceRecorder()

    value.record(
        AgentTraceEvent(
            trace_id="trace-001",
            sequence=1,
            event_type=(
                AgentTraceEventType.AGENT_STARTED
            ),
            occurred_at=STARTED,
            message="Agent started.",
            attempt_number=1,
        )
    )
    value.record(
        AgentTraceEvent(
            trace_id="trace-001",
            sequence=2,
            event_type=(
                AgentTraceEventType.AGENT_COMPLETED
            ),
            occurred_at=STARTED
            + timedelta(seconds=1),
            message="Agent completed.",
            plan_id="plan-001",
            attempt_number=1,
        )
    )

    return value


def service() -> AgentTraceExportService:
    """Return one configured export service."""

    return AgentTraceExportService(
        read_service=AgentTraceReadService(
            recorder=recorder()
        )
    )


def test_service_exports_json_trace() -> None:
    result = service().export(
        trace_id="trace-001",
        format=AgentTraceExportFormat.JSON,
    )

    assert result.trace_id == "trace-001"
    assert result.file_extension == ".json"


def test_service_exports_markdown_trace() -> None:
    result = service().export(
        trace_id="trace-001",
        format=AgentTraceExportFormat.MARKDOWN,
    )

    assert "# Agent Trace" in result.content
    assert result.file_extension == ".md"
