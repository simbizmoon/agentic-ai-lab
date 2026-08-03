"""Tests for agent trace archive maintenance."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.memory.clock import Clock
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
from app.schemas.agent_trace_maintenance import (
    AgentTraceMaintenanceStatus,
)
from app.schemas.agent_trace_retention import (
    AgentTraceRetentionPolicy,
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
from app.tracing.agent_trace_maintenance_service import (
    AgentTraceMaintenanceService,
)
from app.tracing.agent_trace_policy_archive_service import (
    AgentTracePolicyArchiveService,
)
from app.tracing.agent_trace_read_service import (
    AgentTraceReadService,
)
from app.tracing.agent_trace_retention_service import (
    AgentTraceRetentionService,
)
from app.tracing.in_memory_trace_recorder import (
    InMemoryTraceRecorder,
)

NOW = datetime(
    2026,
    8,
    4,
    0,
    0,
    tzinfo=UTC,
)


class FixedClock(Clock):
    """Return one fixed maintenance timestamp."""

    def now(self) -> datetime:
        return NOW


def recorder() -> InMemoryTraceRecorder:
    """Return one completed recorded trace."""

    value = InMemoryTraceRecorder()

    value.record(
        AgentTraceEvent(
            trace_id="trace-001",
            sequence=1,
            event_type=(
                AgentTraceEventType.AGENT_STARTED
            ),
            occurred_at=NOW,
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
            occurred_at=NOW + timedelta(seconds=1),
            message="Agent completed.",
            plan_id="plan-001",
            attempt_number=1,
        )
    )

    return value


def maintenance_service(
    tmp_path: Path,
    *,
    retention_policy: AgentTraceRetentionPolicy,
) -> AgentTraceMaintenanceService:
    """Return one configured maintenance service."""

    trace_recorder = recorder()
    read_service = AgentTraceReadService(
        recorder=trace_recorder
    )
    file_writer = AgentTraceFileWriter(
        output_directory=tmp_path
    )

    archive_service = AgentTracePolicyArchiveService(
        read_service=read_service,
        archive_service=AgentTraceArchiveService(
            export_service=AgentTraceExportService(
                read_service=read_service
            ),
            file_writer=file_writer,
        ),
        policy=AgentTraceArchivePolicy(
            formats=[
                AgentTraceExportFormat.JSON,
                AgentTraceExportFormat.MARKDOWN,
            ],
            archive_completed=True,
        ),
    )

    return AgentTraceMaintenanceService(
        archive_service=archive_service,
        retention_service=AgentTraceRetentionService(
            output_directory=tmp_path,
            clock=FixedClock(),
        ),
        retention_policy=retention_policy,
    )


def test_service_archives_then_applies_retention(
    tmp_path: Path,
) -> None:
    result = maintenance_service(
        tmp_path,
        retention_policy=AgentTraceRetentionPolicy(
            maximum_file_count=10
        ),
    ).maintain("trace-001")

    assert result.status is (
        AgentTraceMaintenanceStatus.SUCCESS
    )
    assert result.archive is not None
    assert result.retention is not None
    assert result.archive.archived is True
    assert len(result.archive.files) == 2
    assert result.retention.scanned_file_count == 2
    assert result.retention.deleted_file_count == 0

    assert (tmp_path / "trace-001.json").exists()
    assert (tmp_path / "trace-001.md").exists()


def test_service_removes_old_file_after_archive(
    tmp_path: Path,
) -> None:
    old_file = tmp_path / "old-trace.json"
    old_file.write_text(
        "{}",
        encoding="utf-8",
    )

    old_time = (
        NOW - timedelta(days=100)
    ).timestamp()
    os.utime(
        old_file,
        (old_time, old_time),
    )

    result = maintenance_service(
        tmp_path,
        retention_policy=AgentTraceRetentionPolicy(
            maximum_age_days=30
        ),
    ).maintain("trace-001")

    assert result.archive.archived is True
    assert old_file.resolve() in (
        result.retention.deleted_paths
    )
    assert not old_file.exists()


def test_service_enforces_file_count_after_archive(
    tmp_path: Path,
) -> None:
    first = tmp_path / "old-1.json"
    second = tmp_path / "old-2.json"

    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")

    first_time = (
        NOW - timedelta(days=2)
    ).timestamp()
    second_time = (
        NOW - timedelta(days=1)
    ).timestamp()

    os.utime(first, (first_time, first_time))
    os.utime(second, (second_time, second_time))

    result = maintenance_service(
        tmp_path,
        retention_policy=AgentTraceRetentionPolicy(
            maximum_file_count=2
        ),
    ).maintain("trace-001")

    assert result.retention.scanned_file_count == 4
    assert result.retention.deleted_file_count == 2
    assert result.retention.retained_file_count == 2


def test_service_supports_retention_dry_run(
    tmp_path: Path,
) -> None:
    old_file = tmp_path / "old-trace.json"
    old_file.write_text(
        "{}",
        encoding="utf-8",
    )

    old_time = (
        NOW - timedelta(days=100)
    ).timestamp()
    os.utime(
        old_file,
        (old_time, old_time),
    )

    result = maintenance_service(
        tmp_path,
        retention_policy=AgentTraceRetentionPolicy(
            maximum_age_days=30,
            dry_run=True,
        ),
    ).maintain("trace-001")

    assert result.retention.eligible_file_count == 1
    assert result.retention.deleted_file_count == 0
    assert old_file.exists()


def test_service_rejects_blank_trace_id(
    tmp_path: Path,
) -> None:
    service = maintenance_service(
        tmp_path,
        retention_policy=AgentTraceRetentionPolicy(
            maximum_file_count=10
        ),
    )

    with pytest.raises(
        ValueError,
        match="trace_id must not be blank",
    ):
        service.maintain(" ")
