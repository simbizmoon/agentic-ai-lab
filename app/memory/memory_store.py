"""Abstract storage interface for agent memories."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.schemas.memory_query import MemoryQuery
from app.schemas.memory_record import MemoryRecord
from app.schemas.memory_update import MemoryUpdate


class MemoryStoreError(RuntimeError):
    """Base error for memory storage operations."""


class DuplicateMemoryError(MemoryStoreError):
    """Raised when a memory ID already exists."""


class MemoryNotFoundError(MemoryStoreError):
    """Raised when a requested memory does not exist."""


class MemoryStore(ABC):
    """Abstract persistence interface for memory records."""

    @abstractmethod
    def add(self, memory: MemoryRecord) -> MemoryRecord:
        """Store a new memory."""

    @abstractmethod
    def get(self, memory_id: str) -> MemoryRecord:
        """Return one memory by ID."""

    @abstractmethod
    def list(
        self,
        *,
        query: MemoryQuery | None = None,
        now: datetime | None = None,
    ) -> list[MemoryRecord]:
        """Return memories matching the supplied filters."""

    @abstractmethod
    def update(
        self,
        *,
        memory_id: str,
        update: MemoryUpdate,
        updated_at: datetime,
    ) -> MemoryRecord:
        """Update mutable fields of one memory."""

    @abstractmethod
    def delete(self, memory_id: str) -> MemoryRecord:
        """Delete and return one memory."""

    @abstractmethod
    def clear(self) -> None:
        """Delete all memories."""

    @abstractmethod
    def count(
        self,
        *,
        query: MemoryQuery | None = None,
        now: datetime | None = None,
    ) -> int:
        """Return the number of matching memories."""
