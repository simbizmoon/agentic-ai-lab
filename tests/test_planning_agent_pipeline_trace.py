"""Tests for high-level planning-pipeline tracing."""

from __future__ import annotations

from app.schemas.agent_trace import AgentTraceEventType
from app.tracing.agent_trace_session import (
    AgentTraceSession,
)
from app.tracing.in_memory_trace_recorder import (
    InMemoryTraceRecorder,
)
from tests.test_planning_agent_pipeline import (
    FakePlannerClient,
    pipeline,
    request,
)


def test_pipeline_records_high_level_events() -> None:
    recorder = InMemoryTraceRecorder()
    trace_session = AgentTraceSession(
        recorder=recorder,
        trace_id="trace-001",
    )

    result = pipeline(
        FakePlannerClient()
    ).run(
        request(),
        trace_session=trace_session,
        attempt_number=1,
    )

    events = recorder.get_trace("trace-001")

    high_level_event_types = {
        AgentTraceEventType.PLANNING_STARTED,
        AgentTraceEventType.PLANNING_COMPLETED,
        AgentTraceEventType.PLAN_STARTED,
        AgentTraceEventType.PLAN_COMPLETED,
        AgentTraceEventType.PLAN_FAILED,
        AgentTraceEventType.PLAN_CANCELLED,
        AgentTraceEventType.PLAN_BLOCKED,
        AgentTraceEventType.EVALUATION_COMPLETED,
    }
    high_level_events = [
        event
        for event in events
        if event.event_type in high_level_event_types
    ]

    assert [
        event.event_type
        for event in high_level_events
    ] == [
        AgentTraceEventType.PLANNING_STARTED,
        AgentTraceEventType.PLANNING_COMPLETED,
        AgentTraceEventType.PLAN_STARTED,
        AgentTraceEventType.PLAN_COMPLETED,
        AgentTraceEventType.EVALUATION_COMPLETED,
    ]

    assert all(
        event.attempt_number == 1
        for event in events
    )
    assert high_level_events[1].plan_id == (
        result.run.plan.plan_id
    )


def test_pipeline_operates_without_trace_session() -> None:
    result = pipeline(
        FakePlannerClient()
    ).run(request())

    assert result.run.plan.status.value == "completed"


def test_pipeline_records_evaluation_decision() -> None:
    recorder = InMemoryTraceRecorder()
    trace_session = AgentTraceSession(
        recorder=recorder,
        trace_id="trace-001",
    )

    pipeline(
        FakePlannerClient()
    ).run(
        request(),
        trace_session=trace_session,
    )

    event = recorder.get_trace("trace-001")[-1]

    assert event.event_type is (
        AgentTraceEventType.EVALUATION_COMPLETED
    )
    assert event.metadata["decision"] == (
        "goal_achieved"
    )
