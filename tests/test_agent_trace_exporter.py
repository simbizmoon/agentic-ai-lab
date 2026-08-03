"""Tests for planning-agent trace exporting."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.schemas.agent_trace import AgentTraceEventType
from app.schemas.agent_trace_export import (
    AgentTraceExportFormat,
)
from app.schemas.agent_trace_summary import (
    AgentTraceOutcome,
    AgentTraceSummary,
)
from app.schemas.agent_trace_timeline import (
    AgentTraceTimeline,
    AgentTraceTimelineItem,
)
from app.tracing.agent_trace_exporter import (
    AgentTraceExporter,
)

STARTED = datetime(
    2026,
    8,
    4,
    5,
    0,
    tzinfo=UTC,
)
ENDED = STARTED + timedelta(seconds=1)


def timeline(
    *,
    trace_id: str = "trace-001",
) -> AgentTraceTimeline:
    """Return one readable trace timeline."""

    return AgentTraceTimeline(
        trace_id=trace_id,
        started_at=STARTED,
        ended_at=ENDED,
        duration_ms=1_000,
        items=[
            AgentTraceTimelineItem(
                sequence=1,
                event_type=(
                    AgentTraceEventType.AGENT_STARTED
                ),
                occurred_at=STARTED,
                elapsed_ms=0,
                message="Agent started.",
                attempt_number=1,
            ),
            AgentTraceTimelineItem(
                sequence=2,
                event_type=(
                    AgentTraceEventType.AGENT_COMPLETED
                ),
                occurred_at=ENDED,
                elapsed_ms=1_000,
                message="Agent completed.",
                plan_id="plan-001",
                attempt_number=1,
            ),
        ],
    )


def summary(
    *,
    trace_id: str = "trace-001",
) -> AgentTraceSummary:
    """Return one readable trace summary."""

    return AgentTraceSummary(
        trace_id=trace_id,
        outcome=AgentTraceOutcome.COMPLETED,
        started_at=STARTED,
        ended_at=ENDED,
        duration_ms=1_000,
        event_count=2,
        attempt_count=1,
        plan_count=1,
        planning_count=0,
        replanning_count=0,
        step_started_count=0,
        step_completed_count=0,
        step_failed_count=0,
        step_skipped_count=0,
        tool_started_count=0,
        tool_completed_count=0,
        tool_failed_count=0,
        final_plan_id="plan-001",
        final_message="Agent completed.",
    )


def test_exporter_creates_json() -> None:
    result = AgentTraceExporter().export(
        timeline=timeline(),
        summary=summary(),
        format=AgentTraceExportFormat.JSON,
    )

    payload = json.loads(result.content)

    assert result.media_type == "application/json"
    assert result.file_extension == ".json"
    assert payload["summary"]["trace_id"] == (
        "trace-001"
    )
    assert len(payload["timeline"]["items"]) == 2


def test_exporter_creates_plain_text() -> None:
    result = AgentTraceExporter().export(
        timeline=timeline(),
        summary=summary(),
        format=AgentTraceExportFormat.TEXT,
    )

    assert result.media_type == "text/plain"
    assert "Outcome: completed" in result.content
    assert "agent_started" in result.content
    assert "agent_completed" in result.content


def test_exporter_creates_markdown() -> None:
    result = AgentTraceExporter().export(
        timeline=timeline(),
        summary=summary(),
        format=AgentTraceExportFormat.MARKDOWN,
    )

    assert result.media_type == "text/markdown"
    assert "# Agent Trace `trace-001`" in result.content
    assert "## Summary" in result.content
    assert "## Timeline" in result.content
    assert "| Seq | Elapsed |" in result.content


def test_exporter_rejects_mismatched_trace_ids() -> None:
    with pytest.raises(
        ValueError,
        match="trace IDs must match",
    ):
        AgentTraceExporter().export(
            timeline=timeline(
                trace_id="trace-001"
            ),
            summary=summary(
                trace_id="trace-002"
            ),
            format=AgentTraceExportFormat.JSON,
        )
