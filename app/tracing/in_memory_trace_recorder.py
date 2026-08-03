"""In-memory implementation of planning-agent trace storage."""

from __future__ import annotations

from threading import RLock

from app.schemas.agent_trace import AgentTraceEvent
from app.schemas.agent_trace_query import AgentTraceQuery
from app.tracing.trace_recorder import TraceRecorder


class TraceRecorderError(RuntimeError):
    """Raised when an invalid trace event is recorded."""


class InMemoryTraceRecorder(TraceRecorder):
    """Store trace events deterministically in process memory."""

    def __init__(self) -> None:
        self._events: list[AgentTraceEvent] = []
        self._lock = RLock()

    def record(
        self,
        event: AgentTraceEvent,
    ) -> None:
        """Record one event after sequence validation."""

        with self._lock:
            trace_events = [
                existing
                for existing in self._events
                if existing.trace_id == event.trace_id
            ]

            expected_sequence = len(trace_events) + 1

            if event.sequence != expected_sequence:
                raise TraceRecorderError(
                    "trace event sequence must be contiguous; "
                    f"expected {expected_sequence}, "
                    f"received {event.sequence}"
                )

            self._events.append(
                event.model_copy(deep=True)
            )

    def query(
        self,
        query: AgentTraceQuery,
    ) -> list[AgentTraceEvent]:
        """Return events matching all supplied filters."""

        with self._lock:
            events = [
                event.model_copy(deep=True)
                for event in self._events
                if self._matches(
                    event=event,
                    query=query,
                )
            ]

        events.sort(
            key=lambda event: (
                event.trace_id,
                event.sequence,
            )
        )

        if query.limit is not None:
            return events[: query.limit]

        return events

    def get_trace(
        self,
        trace_id: str,
    ) -> list[AgentTraceEvent]:
        """Return one trace in sequence order."""

        if not trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        return self.query(
            AgentTraceQuery(trace_id=trace_id)
        )

    def clear(
        self,
        *,
        trace_id: str | None = None,
    ) -> int:
        """Remove all events or events for one trace."""

        if trace_id is not None and not trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        with self._lock:
            if trace_id is None:
                removed_count = len(self._events)
                self._events.clear()
                return removed_count

            remaining = [
                event
                for event in self._events
                if event.trace_id != trace_id
            ]
            removed_count = (
                len(self._events) - len(remaining)
            )
            self._events = remaining

        return removed_count

    @staticmethod
    def _matches(
        *,
        event: AgentTraceEvent,
        query: AgentTraceQuery,
    ) -> bool:
        """Return whether one event matches a query."""

        if (
            query.trace_id is not None
            and event.trace_id != query.trace_id
        ):
            return False

        if (
            query.event_types
            and event.event_type
            not in set(query.event_types)
        ):
            return False

        if (
            query.plan_id is not None
            and event.plan_id != query.plan_id
        ):
            return False

        if (
            query.step_id is not None
            and event.step_id != query.step_id
        ):
            return False

        if (
            query.tool_name is not None
            and event.tool_name != query.tool_name
        ):
            return False

        return not (
            query.attempt_number is not None
            and event.attempt_number
            != query.attempt_number
        )
