"""Tests for policy-driven agent trace archiving."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.schemas.agent_trace import (
    AgentTraceEvent,
    AgentTraceEventType,
)
from app.schemas.agent_trace_archive_policy import (
    AgentTraceArchivePolicy,
)
from app.schemas.agent_trace_export import (
    AgentTraceExportFormat,
)
from app.schemas.agent_trace_summary import (
    AgentTraceOutcome,
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
from app.tracing.agent_trace_policy_archive_service import (
    AgentTracePolicyArchiveService,
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
    30,
    tzinfo=UTC,
)


def recorder(
    *,
    terminal_event: AgentTraceEventType | None,
) -> InMemoryTraceRecorder:
    """Return a recorder with one configurable trace."""

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

    if terminal_event is not None:
        value.record(
            AgentTraceEvent(
                trace_id="trace-001",
                sequence=2,
                event_type=terminal_event,
                occurred_at=(
                    STARTED + timedelta(seconds=1)
                ),
                message="Agent ended.",
                plan_id="plan-001",
                attempt_number=1,
            )
        )

    return value


def service(
    *,
    tmp_path: Path,
    terminal_event: AgentTraceEventType | None,
    policy: AgentTraceArchivePolicy,
) -> AgentTracePolicyArchiveService:
    """Return one configured policy archive service."""

    trace_recorder = recorder(
        terminal_event=terminal_event
    )
    read_service = AgentTraceReadService(
        recorder=trace_recorder
    )

    return AgentTracePolicyArchiveService(
        read_service=read_service,
        archive_service=AgentTraceArchiveService(
            export_service=AgentTraceExportService(
                read_service=read_service
            ),
            file_writer=AgentTraceFileWriter(
                output_directory=tmp_path
            ),
        ),
        policy=policy,
    )


def test_service_archives_multiple_formats(
    tmp_path: Path,
) -> None:
    result = service(
        tmp_path=tmp_path,
        terminal_event=(
            AgentTraceEventType.AGENT_COMPLETED
        ),
        policy=AgentTraceArchivePolicy(
            formats=[
                AgentTraceExportFormat.JSON,
                AgentTraceExportFormat.MARKDOWN,
            ]
        ),
    ).archive("trace-001")

    assert result.archived is True
    assert result.outcome is (
        AgentTraceOutcome.COMPLETED
    )
    assert {
        file.path.suffix
        for file in result.files
    } == {
        ".json",
        ".md",
    }


def test_service_skips_disabled_incomplete_trace(
    tmp_path: Path,
) -> None:
    result = service(
        tmp_path=tmp_path,
        terminal_event=None,
        policy=AgentTraceArchivePolicy(
            formats=[AgentTraceExportFormat.JSON],
            archive_incomplete=False,
        ),
    ).archive("trace-001")

    assert result.archived is False
    assert result.outcome is (
        AgentTraceOutcome.INCOMPLETE
    )
    assert result.files == []


def test_service_archives_failed_trace(
    tmp_path: Path,
) -> None:
    result = service(
        tmp_path=tmp_path,
        terminal_event=(
            AgentTraceEventType.AGENT_FAILED
        ),
        policy=AgentTraceArchivePolicy(
            formats=[AgentTraceExportFormat.TEXT],
            archive_failed=True,
        ),
    ).archive("trace-001")

    assert result.archived is True
    assert result.outcome is AgentTraceOutcome.FAILED
    assert result.files[0].path.suffix == ".txt"


def test_service_can_skip_failed_trace(
    tmp_path: Path,
) -> None:
    result = service(
        tmp_path=tmp_path,
        terminal_event=(
            AgentTraceEventType.AGENT_FAILED
        ),
        policy=AgentTraceArchivePolicy(
            formats=[AgentTraceExportFormat.JSON],
            archive_completed=True,
            archive_failed=False,
        ),
    ).archive("trace-001")

    assert result.archived is False
