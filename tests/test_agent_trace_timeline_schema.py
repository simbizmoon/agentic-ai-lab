"""Tests for readable agent trace timeline schemas."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.agent_trace import AgentTraceEventType
from app.schemas.agent_trace_timeline import (
    AgentTraceTimeline,
    AgentTraceTimelineItem,
)

STARTED = datetime(
    2026,
    8,
    4,
    2,
    30,
    tzinfo=UTC,
)
ENDED = STARTED + timedelta(seconds=2)


def item(
    *,
    sequence: int,
    occurred_at: datetime,
    elapsed_ms: int,
) -> AgentTraceTimelineItem:
    """Return one timeline item."""

    return AgentTraceTimelineItem(
        sequence=sequence,
        event_type=(
            AgentTraceEventType.AGENT_STARTED
        ),
        occurred_at=occurred_at,
        elapsed_ms=elapsed_ms,
        message="Recorded event.",
    )


def test_timeline_accepts_consistent_values() -> None:
    timeline = AgentTraceTimeline(
        trace_id="trace-001",
        started_at=STARTED,
        ended_at=ENDED,
        duration_ms=2_000,
        items=[
            item(
                sequence=1,
                occurred_at=STARTED,
                elapsed_ms=0,
            ),
            item(
                sequence=2,
                occurred_at=ENDED,
                elapsed_ms=2_000,
            ),
        ],
    )

    assert timeline.duration_ms == 2_000


def test_timeline_rejects_duplicate_sequences() -> None:
    with pytest.raises(
        ValidationError,
        match="sequences must be unique",
    ):
        AgentTraceTimeline(
            trace_id="trace-001",
            started_at=STARTED,
            ended_at=ENDED,
            duration_ms=2_000,
            items=[
                item(
                    sequence=1,
                    occurred_at=STARTED,
                    elapsed_ms=0,
                ),
                item(
                    sequence=1,
                    occurred_at=ENDED,
                    elapsed_ms=2_000,
                ),
            ],
        )


def test_timeline_rejects_inconsistent_duration() -> None:
    with pytest.raises(
        ValidationError,
        match="duration_ms is inconsistent",
    ):
        AgentTraceTimeline(
            trace_id="trace-001",
            started_at=STARTED,
            ended_at=ENDED,
            duration_ms=1,
            items=[
                item(
                    sequence=1,
                    occurred_at=STARTED,
                    elapsed_ms=0,
                ),
                item(
                    sequence=2,
                    occurred_at=ENDED,
                    elapsed_ms=2_000,
                ),
            ],
        )


def test_timeline_item_rejects_blank_message() -> None:
    with pytest.raises(
        ValidationError,
        match="message must not be blank",
    ):
        AgentTraceTimelineItem(
            sequence=1,
            event_type=(
                AgentTraceEventType.AGENT_STARTED
            ),
            occurred_at=STARTED,
            elapsed_ms=0,
            message=" ",
        )
