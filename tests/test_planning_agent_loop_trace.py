"""Tests for automatic-replanning loop tracing."""

from app.schemas.agent_trace import AgentTraceEventType
from app.schemas.planning_agent_loop import (
    PlanningAgentLoopStatus,
)
from app.schemas.tool_execution import ToolExecutionStatus
from app.tracing.agent_trace_session import AgentTraceSession
from app.tracing.in_memory_trace_recorder import (
    InMemoryTraceRecorder,
)
from tests.test_planning_agent_loop import (
    SequencedPlannerClient,
    SequencedTool,
    build_loop,
    loop_request,
    planner_output,
)


def test_loop_records_replanning_and_completion() -> None:
    planner_client = SequencedPlannerClient(
        outputs=[
            planner_output(title="Original approach"),
            planner_output(title="Replacement approach"),
        ]
    )
    tool = SequencedTool(
        statuses=[
            ToolExecutionStatus.FAILED,
            ToolExecutionStatus.SUCCEEDED,
        ]
    )
    recorder = InMemoryTraceRecorder()
    session = AgentTraceSession(
        recorder=recorder,
        trace_id="trace-001",
    )

    result = build_loop(
        planner_client=planner_client,
        tool=tool,
    ).run(
        loop_request(),
        trace_session=session,
    )

    event_types = [
        event.event_type
        for event in recorder.get_trace("trace-001")
    ]

    assert result.status is (
        PlanningAgentLoopStatus.GOAL_ACHIEVED
    )
    assert result.trace_id == "trace-001"
    assert event_types[0] is (
        AgentTraceEventType.AGENT_STARTED
    )
    assert (
        AgentTraceEventType.REPLANNING_STARTED
        in event_types
    )
    assert (
        AgentTraceEventType.REPLANNING_COMPLETED
        in event_types
    )
    assert event_types[-1] is (
        AgentTraceEventType.AGENT_COMPLETED
    )


def test_loop_uses_sequential_attempt_numbers() -> None:
    recorder = InMemoryTraceRecorder()
    session = AgentTraceSession(
        recorder=recorder,
        trace_id="trace-001",
    )

    build_loop(
        planner_client=SequencedPlannerClient(
            outputs=[
                planner_output(title="Original"),
                planner_output(title="Replacement"),
            ]
        ),
        tool=SequencedTool(
            statuses=[
                ToolExecutionStatus.FAILED,
                ToolExecutionStatus.SUCCEEDED,
            ]
        ),
    ).run(
        loop_request(),
        trace_session=session,
    )

    events = recorder.get_trace("trace-001")

    first_attempt_events = [
        event
        for event in events
        if event.attempt_number == 1
    ]
    second_attempt_events = [
        event
        for event in events
        if event.attempt_number == 2
    ]

    assert first_attempt_events
    assert second_attempt_events
    assert any(
        event.event_type
        is AgentTraceEventType.REPLANNING_STARTED
        for event in second_attempt_events
    )


def test_loop_records_replan_limit() -> None:
    recorder = InMemoryTraceRecorder()
    session = AgentTraceSession(
        recorder=recorder,
        trace_id="trace-001",
    )

    result = build_loop(
        planner_client=SequencedPlannerClient(
            outputs=[
                planner_output(title="Failing approach")
            ]
        ),
        tool=SequencedTool(
            statuses=[ToolExecutionStatus.FAILED]
        ),
    ).run(
        loop_request(maximum_replans=0),
        trace_session=session,
    )

    event_types = [
        event.event_type
        for event in recorder.get_trace("trace-001")
    ]

    assert result.status is (
        PlanningAgentLoopStatus.REPLAN_LIMIT_REACHED
    )
    assert event_types[-2:] == [
        AgentTraceEventType.REPLAN_LIMIT_REACHED,
        AgentTraceEventType.AGENT_FAILED,
    ]


def test_loop_operates_without_trace_session() -> None:
    result = build_loop(
        planner_client=SequencedPlannerClient(
            outputs=[
                planner_output(title="Successful approach")
            ]
        ),
        tool=SequencedTool(
            statuses=[ToolExecutionStatus.SUCCEEDED]
        ),
    ).run(loop_request())

    assert result.status is (
        PlanningAgentLoopStatus.GOAL_ACHIEVED
    )
    assert result.trace_id is None
