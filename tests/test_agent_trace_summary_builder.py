"""Tests for planning-agent trace summary building."""

from datetime import UTC, datetime, timedelta

from app.schemas.agent_trace import (
    AgentTraceEvent,
    AgentTraceEventType,
)
from app.schemas.agent_trace_summary import (
    AgentTraceOutcome,
)
from app.tracing.agent_trace_summary_builder import (
    AgentTraceSummaryBuilder,
)

STARTED = datetime(
    2026,
    8,
    4,
    4,
    0,
    tzinfo=UTC,
)


def event(
    *,
    sequence: int,
    seconds: int,
    event_type: AgentTraceEventType,
    plan_id: str | None = None,
    attempt_number: int | None = None,
) -> AgentTraceEvent:
    """Return one trace event."""

    return AgentTraceEvent(
        trace_id="trace-001",
        sequence=sequence,
        event_type=event_type,
        occurred_at=STARTED + timedelta(
            seconds=seconds
        ),
        message=f"Recorded {event_type.value}.",
        plan_id=plan_id,
        attempt_number=attempt_number,
    )


def test_builder_aggregates_completed_trace() -> None:
    summary = AgentTraceSummaryBuilder().build(
        [
            event(
                sequence=1,
                seconds=0,
                event_type=(
                    AgentTraceEventType.AGENT_STARTED
                ),
                attempt_number=1,
            ),
            event(
                sequence=2,
                seconds=1,
                event_type=(
                    AgentTraceEventType.PLANNING_STARTED
                ),
                attempt_number=1,
            ),
            event(
                sequence=3,
                seconds=2,
                event_type=(
                    AgentTraceEventType.STEP_STARTED
                ),
                plan_id="plan-001",
                attempt_number=1,
            ),
            event(
                sequence=4,
                seconds=3,
                event_type=(
                    AgentTraceEventType.TOOL_STARTED
                ),
                plan_id="plan-001",
                attempt_number=1,
            ),
            event(
                sequence=5,
                seconds=4,
                event_type=(
                    AgentTraceEventType.TOOL_COMPLETED
                ),
                plan_id="plan-001",
                attempt_number=1,
            ),
            event(
                sequence=6,
                seconds=5,
                event_type=(
                    AgentTraceEventType.STEP_COMPLETED
                ),
                plan_id="plan-001",
                attempt_number=1,
            ),
            event(
                sequence=7,
                seconds=6,
                event_type=(
                    AgentTraceEventType.AGENT_COMPLETED
                ),
                plan_id="plan-001",
                attempt_number=1,
            ),
        ]
    )

    assert summary.outcome is (
        AgentTraceOutcome.COMPLETED
    )
    assert summary.duration_ms == 6_000
    assert summary.event_count == 7
    assert summary.attempt_count == 1
    assert summary.plan_count == 1
    assert summary.step_completed_count == 1
    assert summary.tool_completed_count == 1
    assert summary.final_plan_id == "plan-001"


def test_builder_marks_failed_trace() -> None:
    summary = AgentTraceSummaryBuilder().build(
        [
            event(
                sequence=1,
                seconds=0,
                event_type=(
                    AgentTraceEventType.AGENT_STARTED
                ),
            ),
            event(
                sequence=2,
                seconds=1,
                event_type=(
                    AgentTraceEventType.AGENT_FAILED
                ),
                plan_id="plan-001",
            ),
        ]
    )

    assert summary.outcome is AgentTraceOutcome.FAILED


def test_builder_marks_nonterminal_trace_incomplete() -> None:
    summary = AgentTraceSummaryBuilder().build(
        [
            event(
                sequence=1,
                seconds=0,
                event_type=(
                    AgentTraceEventType.AGENT_STARTED
                ),
            )
        ]
    )

    assert summary.outcome is (
        AgentTraceOutcome.INCOMPLETE
    )
