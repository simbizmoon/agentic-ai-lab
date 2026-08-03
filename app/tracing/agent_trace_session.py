"""Trace-session management for planning-agent execution."""

from __future__ import annotations

from typing import Any

from app.memory.clock import Clock, SystemClock
from app.schemas.agent_trace import (
    AgentTraceEvent,
    AgentTraceEventType,
)
from app.tracing.trace_id_generator import (
    TraceIdGenerator,
    UUIDTraceIdGenerator,
)
from app.tracing.trace_recorder import TraceRecorder


class AgentTraceSession:
    """Create sequential events for one planning-agent trace."""

    def __init__(
        self,
        *,
        recorder: TraceRecorder,
        trace_id: str | None = None,
        clock: Clock | None = None,
        id_generator: TraceIdGenerator | None = None,
    ) -> None:
        generator = id_generator or UUIDTraceIdGenerator()
        resolved_trace_id = (
            trace_id
            if trace_id is not None
            else generator.generate()
        )

        if not resolved_trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        self._recorder = recorder
        self._trace_id = resolved_trace_id
        self._clock = clock or SystemClock()
        self._sequence = len(
            recorder.get_trace(resolved_trace_id)
        )

    @property
    def recorder(self) -> TraceRecorder:
        """Return the configured trace recorder."""

        return self._recorder

    @property
    def trace_id(self) -> str:
        """Return this session's trace identifier."""

        return self._trace_id

    @property
    def sequence(self) -> int:
        """Return the most recently emitted sequence."""

        return self._sequence

    def emit(
        self,
        *,
        event_type: AgentTraceEventType,
        message: str,
        plan_id: str | None = None,
        step_id: str | None = None,
        tool_name: str | None = None,
        attempt_number: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentTraceEvent:
        """Create and record one sequential trace event."""

        event = AgentTraceEvent(
            trace_id=self.trace_id,
            sequence=self._sequence + 1,
            event_type=event_type,
            occurred_at=self._clock.now(),
            message=message,
            plan_id=plan_id,
            step_id=step_id,
            tool_name=tool_name,
            attempt_number=attempt_number,
            metadata=dict(metadata or {}),
        )

        self.recorder.record(event)
        self._sequence = event.sequence

        return event
