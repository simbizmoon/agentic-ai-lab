"""Tests for readable agent trace timeline building."""

from datetime import UTC, datetime, timedelta

import pytest

from app.schemas.agent_trace import (
    AgentTraceEvent,
    AgentTraceEventType,
)
from app.tracing.agent_trace_timeline_builder import (
    AgentTraceTimelineBuilder,
    AgentTraceTimelineBuilderError,
)

STARTED = datetime(
    2026,
    8,
    4,
    3,
    30,
    tzinfo=UTC,
)


def event(
    *,
    trace_id: str = "trace-001",
    sequence: int,
    seconds: int,
    event_type: AgentTraceEventType,
) -> AgentTraceEvent:
    """Return one trace event."""

    return AgentTraceEvent(
        trace_id=trace_id,
        sequence=sequence,
        event_type=event_type,
        occurred_at=STARTED + timedelta(
            seconds=seconds
        ),
        message=f"Recorded {event_type.value}.",
    )


def test_builder_creates_elapsed_timeline() -> None:
    timeline = AgentTraceTimelineBuilder().build(
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
                seconds=2,
                event_type=(
                    AgentTraceEventType.PLANNING_STARTED
                ),
            ),
            event(
                sequence=3,
                seconds=5,
                event_type=(
                    AgentTraceEventType.AGENT_COMPLETED
                ),
            ),
        ]
    )

    assert timeline.duration_ms == 5_000
    assert [
        item.elapsed_ms
        for item in timeline.items
    ] == [
        0,
        2_000,
        5_000,
    ]


def test_builder_orders_events_by_sequence() -> None:
    timeline = AgentTraceTimelineBuilder().build(
        [
            event(
                sequence=2,
                seconds=2,
                event_type=(
                    AgentTraceEventType.PLANNING_STARTED
                ),
            ),
            event(
                sequence=1,
                seconds=0,
                event_type=(
                    AgentTraceEventType.AGENT_STARTED
                ),
            ),
        ]
    )

    assert [
        item.sequence
        for item in timeline.items
    ] == [1, 2]


def test_builder_rejects_empty_events() -> None:
    with pytest.raises(
        AgentTraceTimelineBuilderError,
        match="empty events",
    ):
        AgentTraceTimelineBuilder().build([])


def test_builder_rejects_multiple_trace_ids() -> None:
    with pytest.raises(
        AgentTraceTimelineBuilderError,
        match="one trace_id",
    ):
        AgentTraceTimelineBuilder().build(
            [
                event(
                    sequence=1,
                    seconds=0,
                    event_type=(
                        AgentTraceEventType.AGENT_STARTED
                    ),
                ),
                event(
                    trace_id="trace-002",
                    sequence=2,
                    seconds=1,
                    event_type=(
                        AgentTraceEventType.AGENT_COMPLETED
                    ),
                ),
            ]
        )
