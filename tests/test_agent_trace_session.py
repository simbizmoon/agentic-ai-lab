"""Tests for planning-agent trace sessions."""

from datetime import UTC, datetime

import pytest

from app.memory.clock import Clock
from app.schemas.agent_trace import AgentTraceEventType
from app.tracing.agent_trace_session import (
    AgentTraceSession,
)
from app.tracing.in_memory_trace_recorder import (
    InMemoryTraceRecorder,
)
from app.tracing.trace_id_generator import (
    TraceIdGenerator,
)

NOW = datetime(
    2026,
    8,
    4,
    2,
    0,
    tzinfo=UTC,
)


class FixedClock(Clock):
    """Return one fixed timestamp."""

    def now(self) -> datetime:
        return NOW


class FixedTraceIdGenerator(TraceIdGenerator):
    """Return one fixed trace identifier."""

    def generate(self) -> str:
        return "trace-001"


def session(
    recorder: InMemoryTraceRecorder | None = None,
) -> AgentTraceSession:
    """Return one deterministic trace session."""

    return AgentTraceSession(
        recorder=recorder or InMemoryTraceRecorder(),
        clock=FixedClock(),
        id_generator=FixedTraceIdGenerator(),
    )


def test_session_generates_trace_id() -> None:
    value = session()

    assert value.trace_id == "trace-001"
    assert value.sequence == 0


def test_session_emits_sequential_events() -> None:
    value = session()

    first = value.emit(
        event_type=AgentTraceEventType.AGENT_STARTED,
        message="Agent started.",
    )
    second = value.emit(
        event_type=AgentTraceEventType.PLANNING_STARTED,
        message="Planning started.",
        attempt_number=1,
    )

    assert first.sequence == 1
    assert second.sequence == 2
    assert value.sequence == 2


def test_session_records_event_metadata() -> None:
    recorder = InMemoryTraceRecorder()
    value = session(recorder)

    value.emit(
        event_type=AgentTraceEventType.PLAN_STARTED,
        message="Plan started.",
        plan_id="plan-001",
        attempt_number=1,
        metadata={"source": "initial"},
    )

    event = recorder.get_trace("trace-001")[0]

    assert event.plan_id == "plan-001"
    assert event.metadata == {"source": "initial"}


def test_session_resumes_existing_trace_sequence() -> None:
    recorder = InMemoryTraceRecorder()

    first_session = session(recorder)
    first_session.emit(
        event_type=AgentTraceEventType.AGENT_STARTED,
        message="Agent started.",
    )

    second_session = session(recorder)
    event = second_session.emit(
        event_type=AgentTraceEventType.AGENT_COMPLETED,
        message="Agent completed.",
    )

    assert event.sequence == 2


def test_session_rejects_blank_explicit_trace_id() -> None:
    with pytest.raises(
        ValueError,
        match="trace_id must not be blank",
    ):
        AgentTraceSession(
            recorder=InMemoryTraceRecorder(),
            trace_id=" ",
            clock=FixedClock(),
        )
