"""Trace identifier generation for planning agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import uuid4


class TraceIdGenerator(ABC):
    """Generate unique trace identifiers."""

    @abstractmethod
    def generate(self) -> str:
        """Return one new trace identifier."""


class UUIDTraceIdGenerator(TraceIdGenerator):
    """Generate trace identifiers using UUID4."""

    def generate(self) -> str:
        """Return one UUID-backed trace identifier."""

        return f"trace-{uuid4()}"
