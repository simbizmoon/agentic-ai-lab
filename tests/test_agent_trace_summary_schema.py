"""Tests for agent trace summary schemas."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.agent_trace_summary import (
    AgentTraceOutcome,
    AgentTraceSummary,
)

STARTED = datetime(
    2026,
    8,
    4,
    3,
    0,
    tzinfo=UTC,
)
ENDED = STARTED + timedelta(seconds=1)


def summary(
    **overrides: object,
) -> AgentTraceSummary:
    """Return one valid trace summary."""

    values: dict[str, object] = {
        "trace_id": "trace-001",
        "outcome": AgentTraceOutcome.COMPLETED,
        "started_at": STARTED,
        "ended_at": ENDED,
        "duration_ms": 1_000,
        "event_count": 10,
        "attempt_count": 1,
        "plan_count": 1,
        "planning_count": 1,
        "replanning_count": 0,
        "step_started_count": 1,
        "step_completed_count": 1,
        "step_failed_count": 0,
        "step_skipped_count": 0,
        "tool_started_count": 1,
        "tool_completed_count": 1,
        "tool_failed_count": 0,
        "final_plan_id": "plan-001",
        "final_message": "Agent completed.",
    }
    values.update(overrides)

    return AgentTraceSummary(**values)


def test_summary_accepts_consistent_values() -> None:
    value = summary()

    assert value.outcome is AgentTraceOutcome.COMPLETED


def test_summary_rejects_inconsistent_duration() -> None:
    with pytest.raises(
        ValidationError,
        match="duration_ms is inconsistent",
    ):
        summary(duration_ms=999)


def test_summary_rejects_too_many_finished_steps() -> None:
    with pytest.raises(
        ValidationError,
        match="finished step count must not exceed",
    ):
        summary(
            step_started_count=1,
            step_completed_count=1,
            step_failed_count=1,
        )


def test_summary_rejects_too_many_finished_tools() -> None:
    with pytest.raises(
        ValidationError,
        match="finished tool count must not exceed",
    ):
        summary(
            tool_started_count=1,
            tool_completed_count=1,
            tool_failed_count=1,
        )
