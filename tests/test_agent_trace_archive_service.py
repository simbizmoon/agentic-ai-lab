"""Tests for exporting and archiving agent traces."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.schemas.agent_trace import (
    AgentTraceEvent,
    AgentTraceEventType,
)
from app.schemas.agent_trace_export import (
    AgentTraceExportFormat,
)
from app.tracing.agent_trace_archive_service import (
    AgentTraceArchiveService,
)
from app.tracing.agent_trace_export_service import (
    AgentTraceExportService,
)
from app.tracing.agent_trace_file_writer import (
    AgentTraceFileWriter,
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
    6,
    0,
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


def test_archive_service_writes_markdown(
    tmp_path: Path,
) -> None:
    service = AgentTraceArchiveService(
        export_service=AgentTraceExportService(
            read_service=AgentTraceReadService(
                recorder=recorder()
            )
        ),
        file_writer=AgentTraceFileWriter(
            output_directory=tmp_path
        ),
    )

    result = service.archive(
        trace_id="trace-001",
        format=AgentTraceExportFormat.MARKDOWN,
    )

    assert result.path.name == "trace-001.md"
    assert result.path.exists()
    assert "# Agent Trace" in result.path.read_text(
        encoding="utf-8"
    )
