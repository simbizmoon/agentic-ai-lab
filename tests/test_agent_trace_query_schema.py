"""Tests for planning-agent trace query schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.agent_trace import AgentTraceEventType
from app.schemas.agent_trace_query import AgentTraceQuery


def test_query_accepts_filters() -> None:
    query = AgentTraceQuery(
        trace_id="trace-001",
        event_types=[
            AgentTraceEventType.STEP_STARTED
        ],
        plan_id="plan-001",
        attempt_number=1,
        limit=10,
    )

    assert query.limit == 10


def test_query_rejects_duplicate_event_types() -> None:
    with pytest.raises(
        ValidationError,
        match="event types must be unique",
    ):
        AgentTraceQuery(
            event_types=[
                AgentTraceEventType.STEP_STARTED,
                AgentTraceEventType.STEP_STARTED,
            ]
        )


@pytest.mark.parametrize(
    "field",
    [
        "trace_id",
        "plan_id",
        "step_id",
        "tool_name",
    ],
)
def test_query_rejects_blank_optional_text(
    field: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match=f"{field} must not be blank",
    ):
        AgentTraceQuery(**{field: " "})
