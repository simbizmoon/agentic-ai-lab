"""Tests for in-memory planning-agent trace storage."""

from datetime import UTC, datetime, timedelta

import pytest

from app.schemas.agent_trace import (
    AgentTraceEvent,
    AgentTraceEventType,
)
from app.schemas.agent_trace_query import AgentTraceQuery
from app.tracing.in_memory_trace_recorder import (
    InMemoryTraceRecorder,
    TraceRecorderError,
)

NOW = datetime(
    2026,
    8,
    4,
    1,
    30,
    tzinfo=UTC,
)


def event(
    *,
    trace_id: str = "trace-001",
    sequence: int,
    event_type: AgentTraceEventType,
    plan_id: str | None = None,
    step_id: str | None = None,
    tool_name: str | None = None,
    attempt_number: int | None = 1,
) -> AgentTraceEvent:
    """Return one trace event."""

    return AgentTraceEvent(
        trace_id=trace_id,
        sequence=sequence,
        event_type=event_type,
        occurred_at=NOW + timedelta(
            seconds=sequence
        ),
        message=f"Recorded {event_type.value}.",
        plan_id=plan_id,
        step_id=step_id,
        tool_name=tool_name,
        attempt_number=attempt_number,
    )


def populated_recorder() -> InMemoryTraceRecorder:
    """Return a recorder containing two traces."""

    recorder = InMemoryTraceRecorder()

    recorder.record(
        event(
            sequence=1,
            event_type=(
                AgentTraceEventType.AGENT_STARTED
            ),
        )
    )
    recorder.record(
        event(
            sequence=2,
            event_type=(
                AgentTraceEventType.STEP_STARTED
            ),
            plan_id="plan-001",
            step_id="step-1",
            tool_name="python",
        )
    )
    recorder.record(
        event(
            sequence=3,
            event_type=(
                AgentTraceEventType.STEP_COMPLETED
            ),
            plan_id="plan-001",
            step_id="step-1",
            tool_name="python",
        )
    )

    recorder.record(
        event(
            trace_id="trace-002",
            sequence=1,
            event_type=(
                AgentTraceEventType.AGENT_STARTED
            ),
            attempt_number=1,
        )
    )

    return recorder


def test_recorder_returns_trace_in_sequence_order() -> None:
    result = populated_recorder().get_trace(
        "trace-001"
    )

    assert [
        item.sequence
        for item in result
    ] == [1, 2, 3]


def test_recorder_rejects_sequence_gap() -> None:
    recorder = InMemoryTraceRecorder()

    with pytest.raises(
        TraceRecorderError,
        match="expected 1, received 2",
    ):
        recorder.record(
            event(
                sequence=2,
                event_type=(
                    AgentTraceEventType.AGENT_STARTED
                ),
            )
        )


def test_recorder_filters_by_event_type() -> None:
    recorder = populated_recorder()

    result = recorder.query(
        AgentTraceQuery(
            trace_id="trace-001",
            event_types=[
                AgentTraceEventType.STEP_STARTED
            ],
        )
    )

    assert len(result) == 1
    assert result[0].event_type is (
        AgentTraceEventType.STEP_STARTED
    )


def test_recorder_filters_by_step_and_tool() -> None:
    result = populated_recorder().query(
        AgentTraceQuery(
            step_id="step-1",
            tool_name="python",
        )
    )

    assert len(result) == 2


def test_recorder_applies_limit() -> None:
    result = populated_recorder().query(
        AgentTraceQuery(
            trace_id="trace-001",
            limit=2,
        )
    )

    assert len(result) == 2
    assert [
        item.sequence
        for item in result
    ] == [1, 2]


def test_recorder_returns_defensive_copies() -> None:
    recorder = populated_recorder()

    first = recorder.get_trace("trace-001")
    second = recorder.get_trace("trace-001")

    assert first == second
    assert first is not second
    assert first[0] is not second[0]


def test_clear_removes_one_trace() -> None:
    recorder = populated_recorder()

    removed = recorder.clear(
        trace_id="trace-001"
    )

    assert removed == 3
    assert recorder.get_trace("trace-001") == []
    assert len(recorder.get_trace("trace-002")) == 1


def test_clear_without_trace_id_removes_everything() -> None:
    recorder = populated_recorder()

    removed = recorder.clear()

    assert removed == 4
    assert recorder.query(AgentTraceQuery()) == []
