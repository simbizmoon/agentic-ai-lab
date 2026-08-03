"""Application service for structured agent memories."""

from __future__ import annotations

from datetime import UTC, datetime

from app.memory.clock import Clock, SystemClock
from app.memory.memory_id_generator import (
    MemoryIdGenerator,
    UuidMemoryIdGenerator,
)
from app.memory.memory_store import MemoryStore
from app.schemas.memory_create import MemoryCreate
from app.schemas.memory_query import MemoryQuery
from app.schemas.memory_record import MemoryRecord
from app.schemas.memory_update import MemoryUpdate


class MemoryServiceError(RuntimeError):
    """Raised when a memory service operation is invalid."""


class MemoryService:
    """Create and manage memories with automatic IDs and timestamps."""

    def __init__(
        self,
        *,
        store: MemoryStore,
        clock: Clock | None = None,
        id_generator: MemoryIdGenerator | None = None,
    ) -> None:
        self._store = store
        self._clock = clock or SystemClock()
        self._id_generator = (
            id_generator or UuidMemoryIdGenerator()
        )

    @property
    def store(self) -> MemoryStore:
        """Return the configured memory store."""

        return self._store

    def clock_now(self) -> datetime:
        """Return the current validated UTC service time."""

        return self._validated_now()

    def create(
        self,
        request: MemoryCreate,
    ) -> MemoryRecord:
        """Create and persist a new memory."""

        now = self._validated_now()
        memory_id = self._id_generator.generate()

        if not memory_id.strip():
            raise MemoryServiceError(
                "memory ID generator returned a blank ID"
            )

        if (
            request.expires_at is not None
            and request.expires_at <= now
        ):
            raise MemoryServiceError(
                "expires_at must be later than creation time"
            )

        memory = MemoryRecord(
            memory_id=memory_id,
            kind=request.kind,
            scope=request.scope,
            source=request.source,
            content=request.content,
            subject_id=request.subject_id,
            project_id=request.project_id,
            session_id=request.session_id,
            source_reference=request.source_reference,
            tags=request.tags,
            importance=request.importance,
            confidence=request.confidence,
            created_at=now,
            updated_at=now,
            expires_at=request.expires_at,
            metadata=request.metadata,
        )

        return self.store.add(memory)

    def get(
        self,
        memory_id: str,
        *,
        record_access: bool = False,
    ) -> MemoryRecord:
        """Return one memory and optionally record its access time."""

        if not record_access:
            return self.store.get(memory_id)

        return self.touch(memory_id)

    def list(
        self,
        *,
        query: MemoryQuery | None = None,
    ) -> list[MemoryRecord]:
        """Return memories matching the supplied filters."""

        return self.store.list(
            query=query,
            now=self._validated_now(),
        )

    def count(
        self,
        *,
        query: MemoryQuery | None = None,
    ) -> int:
        """Return the number of matching memories."""

        return self.store.count(
            query=query,
            now=self._validated_now(),
        )

    def update(
        self,
        *,
        memory_id: str,
        update: MemoryUpdate,
    ) -> MemoryRecord:
        """Update one memory using the current UTC time."""

        now = self._validated_now()
        current = self.store.get(memory_id)

        if (
            update.expires_at is not None
            and update.expires_at <= current.created_at
        ):
            raise MemoryServiceError(
                "expires_at must be later than creation time"
            )

        return self.store.update(
            memory_id=memory_id,
            update=update,
            updated_at=now,
        )

    def touch(self, memory_id: str) -> MemoryRecord:
        """Record that one memory was accessed."""

        now = self._validated_now()

        return self.store.update(
            memory_id=memory_id,
            update=MemoryUpdate(
                last_accessed_at=now,
            ),
            updated_at=now,
        )

    def delete(self, memory_id: str) -> MemoryRecord:
        """Delete and return one memory."""

        return self.store.delete(memory_id)

    def clear(self) -> None:
        """Delete all stored memories."""

        self.store.clear()

    def _validated_now(self) -> datetime:
        """Return a timezone-aware UTC time from the clock."""

        value = self._clock.now()

        if value.tzinfo is None:
            raise MemoryServiceError(
                "clock must return a timezone-aware datetime"
            )

        if value.utcoffset() != UTC.utcoffset(value):
            raise MemoryServiceError(
                "clock must return UTC"
            )

        return value
