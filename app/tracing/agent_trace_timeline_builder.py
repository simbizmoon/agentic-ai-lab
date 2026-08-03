"""Build readable timelines from structured agent trace events."""

from __future__ import annotations

from datetime import datetime

from app.schemas.agent_trace import AgentTraceEvent
from app.schemas.agent_trace_timeline import (
    AgentTraceTimeline,
    AgentTraceTimelineItem,
)


class AgentTraceTimelineBuilderError(RuntimeError):
    """Raised when a timeline cannot be built."""


class AgentTraceTimelineBuilder:
    """Convert trace events into one readable timeline."""

    def build(
        self,
        events: list[AgentTraceEvent],
    ) -> AgentTraceTimeline:
        """Build an ordered timeline from one trace."""

        if not events:
            raise AgentTraceTimelineBuilderError(
                "cannot build timeline from empty events"
            )

        ordered_events = sorted(
            events,
            key=lambda event: event.sequence,
        )

        trace_ids = {
            event.trace_id
            for event in ordered_events
        }

        if len(trace_ids) != 1:
            raise AgentTraceTimelineBuilderError(
                "timeline events must share one trace_id"
            )

        sequences = [
            event.sequence
            for event in ordered_events
        ]

        if sequences != list(
            range(1, len(ordered_events) + 1)
        ):
            raise AgentTraceTimelineBuilderError(
                "timeline event sequences must be contiguous"
            )

        started_at = ordered_events[0].occurred_at
        ended_at = ordered_events[-1].occurred_at

        items = [
            AgentTraceTimelineItem(
                sequence=event.sequence,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                elapsed_ms=self._elapsed_ms(
                    started_at=started_at,
                    occurred_at=event.occurred_at,
                ),
                message=event.message,
                plan_id=event.plan_id,
                step_id=event.step_id,
                tool_name=event.tool_name,
                attempt_number=event.attempt_number,
                metadata=dict(event.metadata),
            )
            for event in ordered_events
        ]

        return AgentTraceTimeline(
            trace_id=ordered_events[0].trace_id,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=self._elapsed_ms(
                started_at=started_at,
                occurred_at=ended_at,
            ),
            items=items,
        )

    @staticmethod
    def _elapsed_ms(
        *,
        started_at: datetime,
        occurred_at: datetime,
    ) -> int:
        """Return elapsed milliseconds between timestamps."""

        elapsed = occurred_at - started_at

        if elapsed.total_seconds() < 0:
            raise AgentTraceTimelineBuilderError(
                "trace event timestamps must be chronological"
            )

        return int(elapsed.total_seconds() * 1_000)
