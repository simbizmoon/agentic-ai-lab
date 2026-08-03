"""Tests for failed step and tool execution traces."""

from app.schemas.agent_trace import AgentTraceEventType
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


def test_failed_pipeline_records_tool_and_step_failure() -> None:
    planner_client = SequencedPlannerClient(
        outputs=[
            planner_output(
                title="Use failing approach"
            )
        ]
    )
    tool = SequencedTool(
        statuses=[
            ToolExecutionStatus.FAILED
        ]
    )
    loop = build_loop(
        planner_client=planner_client,
        tool=tool,
    )

    recorder = InMemoryTraceRecorder()
    trace_session = AgentTraceSession(
        recorder=recorder,
        trace_id="trace-001",
    )

    initial_result = loop.pipeline.run(
        loop_request(
            maximum_replans=0
        ).initial,
        trace_session=trace_session,
        attempt_number=1,
    )

    events = recorder.get_trace("trace-001")
    event_types = [
        event.event_type
        for event in events
    ]

    assert initial_result.run.plan.status.value == "failed"
    assert AgentTraceEventType.TOOL_FAILED in event_types
    assert AgentTraceEventType.STEP_FAILED in event_types
    assert AgentTraceEventType.PLAN_FAILED in event_types

    failed_tool_event = next(
        event
        for event in events
        if event.event_type
        is AgentTraceEventType.TOOL_FAILED
    )

    assert failed_tool_event.step_id == "step-1"
    assert failed_tool_event.tool_name == "worker"
    assert (
        "Execution failed for step-1."
        in failed_tool_event.metadata["error_message"]
    )
