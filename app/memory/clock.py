"""Clock abstractions for deterministic memory operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime


class Clock(ABC):
    """Abstract source of UTC timestamps."""

    @abstractmethod
    def now(self) -> datetime:
        """Return the current UTC datetime."""


class SystemClock(Clock):
    """Return the actual current UTC time."""

    def now(self) -> datetime:
        """Return the current UTC datetime."""

        return datetime.now(UTC)
