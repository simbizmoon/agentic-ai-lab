"""Interfaces for structured planning-agent trace storage."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.agent_trace import AgentTraceEvent
from app.schemas.agent_trace_query import AgentTraceQuery


class TraceRecorder(ABC):
    """Abstract storage for planning-agent trace events."""

    @abstractmethod
    def record(
        self,
        event: AgentTraceEvent,
    ) -> None:
        """Persist one trace event."""

    @abstractmethod
    def query(
        self,
        query: AgentTraceQuery,
    ) -> list[AgentTraceEvent]:
        """Return matching trace events in sequence order."""

    @abstractmethod
    def get_trace(
        self,
        trace_id: str,
    ) -> list[AgentTraceEvent]:
        """Return all events for one trace."""

    @abstractmethod
    def clear(
        self,
        *,
        trace_id: str | None = None,
    ) -> int:
        """Remove events and return the removed count."""
