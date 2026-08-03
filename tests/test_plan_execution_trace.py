"""Tests for step- and tool-level execution tracing."""

from __future__ import annotations

from app.schemas.agent_trace import AgentTraceEventType
from app.tracing.agent_trace_session import AgentTraceSession
from app.tracing.in_memory_trace_recorder import (
    InMemoryTraceRecorder,
)
from tests.test_planning_agent_pipeline import (
    FakePlannerClient,
    pipeline,
    request,
)


def test_pipeline_records_step_and_tool_events() -> None:
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
        attempt_number=1,
    )

    events = recorder.get_trace("trace-001")

    assert [
        event.event_type
        for event in events
    ] == [
        AgentTraceEventType.PLANNING_STARTED,
        AgentTraceEventType.PLANNING_COMPLETED,
        AgentTraceEventType.PLAN_STARTED,
        AgentTraceEventType.STEP_STARTED,
        AgentTraceEventType.TOOL_STARTED,
        AgentTraceEventType.TOOL_COMPLETED,
        AgentTraceEventType.STEP_COMPLETED,
        AgentTraceEventType.STEP_STARTED,
        AgentTraceEventType.TOOL_STARTED,
        AgentTraceEventType.TOOL_COMPLETED,
        AgentTraceEventType.STEP_COMPLETED,
        AgentTraceEventType.PLAN_COMPLETED,
        AgentTraceEventType.EVALUATION_COMPLETED,
    ]


def test_step_events_include_plan_and_step_ids() -> None:
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

    step_events = [
        event
        for event in recorder.get_trace("trace-001")
        if event.event_type
        in {
            AgentTraceEventType.STEP_STARTED,
            AgentTraceEventType.STEP_COMPLETED,
        }
    ]

    assert [
        event.step_id
        for event in step_events
    ] == [
        "step-1",
        "step-1",
        "step-2",
        "step-2",
    ]

    assert all(
        event.plan_id == result.run.plan.plan_id
        for event in step_events
    )

    assert all(
        event.tool_name == "python"
        for event in step_events
    )


def test_tool_events_include_attempt_number() -> None:
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
        attempt_number=3,
    )

    tool_events = [
        event
        for event in recorder.get_trace("trace-001")
        if event.event_type
        in {
            AgentTraceEventType.TOOL_STARTED,
            AgentTraceEventType.TOOL_COMPLETED,
        }
    ]

    assert len(tool_events) == 4
    assert all(
        event.attempt_number == 3
        for event in tool_events
    )
