"""Tests for planning-agent trace retention."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.memory.clock import Clock
from app.schemas.agent_trace_retention import (
    AgentTraceRetentionPolicy,
)
from app.tracing.agent_trace_retention_service import (
    AgentTraceRetentionService,
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
    """Return one fixed retention timestamp."""

    def now(self) -> datetime:
        return NOW


def create_file(
    directory: Path,
    *,
    name: str,
    age_days: int,
) -> Path:
    """Create a file with a controlled modification time."""

    path = directory / name
    path.write_text(
        name,
        encoding="utf-8",
    )

    modified_at = NOW - timedelta(
        days=age_days
    )
    timestamp = modified_at.timestamp()

    os.utime(
        path,
        (timestamp, timestamp),
    )

    return path.resolve()


def service(
    tmp_path: Path,
) -> AgentTraceRetentionService:
    """Return one deterministic retention service."""

    return AgentTraceRetentionService(
        output_directory=tmp_path,
        clock=FixedClock(),
    )


def test_service_removes_files_older_than_limit(
    tmp_path: Path,
) -> None:
    old_file = create_file(
        tmp_path,
        name="old.json",
        age_days=31,
    )
    recent_file = create_file(
        tmp_path,
        name="recent.json",
        age_days=5,
    )

    result = service(tmp_path).apply(
        AgentTraceRetentionPolicy(
            maximum_age_days=30
        )
    )

    assert result.eligible_paths == [old_file]
    assert result.deleted_paths == [old_file]
    assert not old_file.exists()
    assert recent_file.exists()


def test_service_keeps_latest_file_count(
    tmp_path: Path,
) -> None:
    oldest = create_file(
        tmp_path,
        name="first.json",
        age_days=3,
    )
    middle = create_file(
        tmp_path,
        name="second.md",
        age_days=2,
    )
    newest = create_file(
        tmp_path,
        name="third.txt",
        age_days=1,
    )

    result = service(tmp_path).apply(
        AgentTraceRetentionPolicy(
            maximum_file_count=2
        )
    )

    assert result.deleted_paths == [oldest]
    assert not oldest.exists()
    assert middle.exists()
    assert newest.exists()


def test_service_combines_age_and_count_rules(
    tmp_path: Path,
) -> None:
    first = create_file(
        tmp_path,
        name="first.json",
        age_days=40,
    )
    second = create_file(
        tmp_path,
        name="second.json",
        age_days=20,
    )
    third = create_file(
        tmp_path,
        name="third.json",
        age_days=1,
    )

    result = service(tmp_path).apply(
        AgentTraceRetentionPolicy(
            maximum_age_days=30,
            maximum_file_count=1,
        )
    )

    assert result.deleted_paths == [
        first,
        second,
    ]
    assert third.exists()


def test_dry_run_does_not_delete_files(
    tmp_path: Path,
) -> None:
    old_file = create_file(
        tmp_path,
        name="old.json",
        age_days=100,
    )

    result = service(tmp_path).apply(
        AgentTraceRetentionPolicy(
            maximum_age_days=30,
            dry_run=True,
        )
    )

    assert result.eligible_paths == [old_file]
    assert result.deleted_paths == []
    assert result.deleted_file_count == 0
    assert result.retained_file_count == 1
    assert old_file.exists()


def test_service_ignores_unrecognized_files(
    tmp_path: Path,
) -> None:
    trace_file = create_file(
        tmp_path,
        name="trace.json",
        age_days=100,
    )
    unrelated_file = create_file(
        tmp_path,
        name="notes.log",
        age_days=100,
    )

    result = service(tmp_path).apply(
        AgentTraceRetentionPolicy(
            maximum_age_days=30
        )
    )

    assert result.scanned_file_count == 1
    assert not trace_file.exists()
    assert unrelated_file.exists()


def test_service_ignores_nested_files(
    tmp_path: Path,
) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()

    nested_file = create_file(
        nested,
        name="trace.json",
        age_days=100,
    )

    result = service(tmp_path).apply(
        AgentTraceRetentionPolicy(
            maximum_age_days=30
        )
    )

    assert result.scanned_file_count == 0
    assert nested_file.exists()


def test_missing_directory_is_empty_result(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing"

    result = service(missing).apply(
        AgentTraceRetentionPolicy(
            maximum_age_days=30
        )
    )

    assert result.scanned_file_count == 0
    assert result.deleted_file_count == 0
