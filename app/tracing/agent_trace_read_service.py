"""Read-service facade for planning-agent trace views."""

from __future__ import annotations

from app.schemas.agent_trace import AgentTraceEvent
from app.schemas.agent_trace_summary import (
    AgentTraceSummary,
)
from app.schemas.agent_trace_timeline import (
    AgentTraceTimeline,
)
from app.tracing.agent_trace_summary_builder import (
    AgentTraceSummaryBuilder,
)
from app.tracing.agent_trace_timeline_builder import (
    AgentTraceTimelineBuilder,
)
from app.tracing.trace_recorder import TraceRecorder


class AgentTraceNotFoundError(LookupError):
    """Raised when a requested trace does not exist."""


class AgentTraceReadService:
    """Build readable trace views from a recorder."""

    def __init__(
        self,
        *,
        recorder: TraceRecorder,
        timeline_builder: (
            AgentTraceTimelineBuilder | None
        ) = None,
        summary_builder: (
            AgentTraceSummaryBuilder | None
        ) = None,
    ) -> None:
        self._recorder = recorder
        self._timeline_builder = (
            timeline_builder
            or AgentTraceTimelineBuilder()
        )
        self._summary_builder = (
            summary_builder
            or AgentTraceSummaryBuilder()
        )

    @property
    def recorder(self) -> TraceRecorder:
        """Return the configured recorder."""

        return self._recorder

    def timeline(
        self,
        trace_id: str,
    ) -> AgentTraceTimeline:
        """Return a readable timeline for one trace."""

        events = self._events(trace_id)

        return self._timeline_builder.build(events)

    def summary(
        self,
        trace_id: str,
    ) -> AgentTraceSummary:
        """Return an aggregated summary for one trace."""

        events = self._events(trace_id)

        return self._summary_builder.build(events)

    def _events(
        self,
        trace_id: str,
    ) -> list[AgentTraceEvent]:
        """Return events or raise a not-found error."""

        if not trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        events = self.recorder.get_trace(trace_id)

        if not events:
            raise AgentTraceNotFoundError(
                f"trace not found: {trace_id}"
            )

        return events
