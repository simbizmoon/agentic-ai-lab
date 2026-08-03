"""Tests for readable agent trace access."""

from datetime import UTC, datetime, timedelta

import pytest

from app.schemas.agent_trace import (
    AgentTraceEvent,
    AgentTraceEventType,
)
from app.tracing.agent_trace_read_service import (
    AgentTraceNotFoundError,
    AgentTraceReadService,
)
from app.tracing.in_memory_trace_recorder import (
    InMemoryTraceRecorder,
)

STARTED = datetime(
    2026,
    8,
    4,
    4,
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
        )
    )

    return value


def test_service_returns_timeline() -> None:
    result = AgentTraceReadService(
        recorder=recorder()
    ).timeline("trace-001")

    assert result.trace_id == "trace-001"
    assert len(result.items) == 2


def test_service_returns_summary() -> None:
    result = AgentTraceReadService(
        recorder=recorder()
    ).summary("trace-001")

    assert result.event_count == 2
    assert result.final_plan_id == "plan-001"


def test_service_rejects_missing_trace() -> None:
    with pytest.raises(
        AgentTraceNotFoundError,
        match="trace not found",
    ):
        AgentTraceReadService(
            recorder=recorder()
        ).summary("trace-missing")
