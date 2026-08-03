"""Build aggregated summaries from structured agent traces."""

from __future__ import annotations

from collections import Counter

from app.schemas.agent_trace import (
    AgentTraceEvent,
    AgentTraceEventType,
)
from app.schemas.agent_trace_summary import (
    AgentTraceOutcome,
    AgentTraceSummary,
)


class AgentTraceSummaryBuilderError(RuntimeError):
    """Raised when a trace summary cannot be built."""


class AgentTraceSummaryBuilder:
    """Aggregate one trace into operational statistics."""

    def build(
        self,
        events: list[AgentTraceEvent],
    ) -> AgentTraceSummary:
        """Build one summary from trace events."""

        if not events:
            raise AgentTraceSummaryBuilderError(
                "cannot build summary from empty events"
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
            raise AgentTraceSummaryBuilderError(
                "summary events must share one trace_id"
            )

        sequences = [
            event.sequence
            for event in ordered_events
        ]

        if sequences != list(
            range(1, len(ordered_events) + 1)
        ):
            raise AgentTraceSummaryBuilderError(
                "summary event sequences must be contiguous"
            )

        started_at = ordered_events[0].occurred_at
        ended_at = ordered_events[-1].occurred_at

        if ended_at < started_at:
            raise AgentTraceSummaryBuilderError(
                "summary timestamps must be chronological"
            )

        counts = Counter(
            event.event_type
            for event in ordered_events
        )

        attempts = {
            event.attempt_number
            for event in ordered_events
            if event.attempt_number is not None
        }
        plans = {
            event.plan_id
            for event in ordered_events
            if event.plan_id is not None
        }

        final_event = ordered_events[-1]

        return AgentTraceSummary(
            trace_id=ordered_events[0].trace_id,
            outcome=self._outcome(ordered_events),
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=int(
                (
                    ended_at - started_at
                ).total_seconds()
                * 1_000
            ),
            event_count=len(ordered_events),
            attempt_count=len(attempts),
            plan_count=len(plans),
            planning_count=counts[
                AgentTraceEventType.PLANNING_STARTED
            ],
            replanning_count=counts[
                AgentTraceEventType.REPLANNING_STARTED
            ],
            step_started_count=counts[
                AgentTraceEventType.STEP_STARTED
            ],
            step_completed_count=counts[
                AgentTraceEventType.STEP_COMPLETED
            ],
            step_failed_count=counts[
                AgentTraceEventType.STEP_FAILED
            ],
            step_skipped_count=counts[
                AgentTraceEventType.STEP_SKIPPED
            ],
            tool_started_count=counts[
                AgentTraceEventType.TOOL_STARTED
            ],
            tool_completed_count=counts[
                AgentTraceEventType.TOOL_COMPLETED
            ],
            tool_failed_count=counts[
                AgentTraceEventType.TOOL_FAILED
            ],
            final_plan_id=self._final_plan_id(
                ordered_events
            ),
            final_message=final_event.message,
        )

    @staticmethod
    def _outcome(
        events: list[AgentTraceEvent],
    ) -> AgentTraceOutcome:
        """Derive the high-level outcome from terminal events."""

        event_types = [
            event.event_type
            for event in events
        ]

        if (
            AgentTraceEventType.AGENT_COMPLETED
            in event_types
        ):
            return AgentTraceOutcome.COMPLETED

        if AgentTraceEventType.AGENT_FAILED in event_types:
            return AgentTraceOutcome.FAILED

        return AgentTraceOutcome.INCOMPLETE

    @staticmethod
    def _final_plan_id(
        events: list[AgentTraceEvent],
    ) -> str | None:
        """Return the latest recorded plan identifier."""

        for event in reversed(events):
            if event.plan_id is not None:
                return event.plan_id

        return None
