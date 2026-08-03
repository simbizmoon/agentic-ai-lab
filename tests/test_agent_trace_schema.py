"""Tests for structured planning-agent trace schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.agent_trace import (
    AgentTraceEvent,
    AgentTraceEventType,
)

NOW = datetime(
    2026,
    8,
    4,
    1,
    0,
    tzinfo=UTC,
)


def event(
    **overrides: object,
) -> AgentTraceEvent:
    """Return one valid trace event."""

    values: dict[str, object] = {
        "trace_id": "trace-001",
        "sequence": 1,
        "event_type": (
            AgentTraceEventType.AGENT_STARTED
        ),
        "occurred_at": NOW,
        "message": "Agent execution started.",
        "attempt_number": 1,
    }
    values.update(overrides)

    return AgentTraceEvent(**values)


def test_event_accepts_valid_values() -> None:
    value = event()

    assert value.trace_id == "trace-001"
    assert value.sequence == 1


@pytest.mark.parametrize(
    "field",
    [
        "trace_id",
        "message",
    ],
)
def test_event_rejects_blank_required_text(
    field: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match=f"{field} must not be blank",
    ):
        event(**{field: " "})


@pytest.mark.parametrize(
    "field",
    [
        "plan_id",
        "step_id",
        "tool_name",
    ],
)
def test_event_rejects_blank_optional_text(
    field: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match=f"{field} must not be blank",
    ):
        event(**{field: " "})


def test_event_requires_timezone_aware_datetime() -> None:
    with pytest.raises(
        ValidationError,
        match="must be timezone-aware",
    ):
        event(
            occurred_at=datetime(  # noqa: DTZ001
                2026,
                8,
                4,
                1,
                0,
            )
        )


def test_event_is_immutable() -> None:
    value = event()

    with pytest.raises(ValidationError):
        value.message = "Changed."
