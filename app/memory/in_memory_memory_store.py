"""Deterministic in-memory implementation of MemoryStore."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock

from app.memory.memory_store import (
    DuplicateMemoryError,
    MemoryNotFoundError,
    MemoryStore,
)
from app.schemas.memory_query import MemoryQuery
from app.schemas.memory_record import MemoryRecord
from app.schemas.memory_update import MemoryUpdate


class InMemoryMemoryStore(MemoryStore):
    """Store validated memories in process memory."""

    def __init__(self) -> None:
        self._memories: dict[str, MemoryRecord] = {}
        self._lock = RLock()

    def add(self, memory: MemoryRecord) -> MemoryRecord:
        """Store a new memory with a unique ID."""

        with self._lock:
            if memory.memory_id in self._memories:
                raise DuplicateMemoryError(
                    f"memory already exists: {memory.memory_id}"
                )

            stored = memory.model_copy(deep=True)
            self._memories[memory.memory_id] = stored

            return stored.model_copy(deep=True)

    def get(self, memory_id: str) -> MemoryRecord:
        """Return one memory by ID."""

        normalized_id = self._validate_memory_id(memory_id)

        with self._lock:
            memory = self._memories.get(normalized_id)

            if memory is None:
                raise MemoryNotFoundError(
                    f"memory not found: {normalized_id}"
                )

            return memory.model_copy(deep=True)

    def list(
        self,
        *,
        query: MemoryQuery | None = None,
        now: datetime | None = None,
    ) -> list[MemoryRecord]:
        """Return matching memories in deterministic order."""

        effective_query = query or MemoryQuery()
        effective_now = self._resolve_now(now)

        with self._lock:
            matching = [
                memory.model_copy(deep=True)
                for memory in self._memories.values()
                if self._matches(
                    memory=memory,
                    query=effective_query,
                    now=effective_now,
                )
            ]

        return sorted(
            matching,
            key=lambda memory: (
                memory.created_at,
                memory.memory_id,
            ),
        )

    def update(
        self,
        *,
        memory_id: str,
        update: MemoryUpdate,
        updated_at: datetime,
    ) -> MemoryRecord:
        """Update mutable fields while preserving identity."""

        normalized_id = self._validate_memory_id(memory_id)
        normalized_updated_at = self._validate_utc_datetime(
            name="updated_at",
            value=updated_at,
        )

        with self._lock:
            current = self._memories.get(normalized_id)

            if current is None:
                raise MemoryNotFoundError(
                    f"memory not found: {normalized_id}"
                )

            update_values = update.model_dump(
                exclude_unset=True
            )
            update_values["updated_at"] = (
                normalized_updated_at
            )

            updated = current.model_copy(
                update=update_values,
                deep=True,
            )

            validated = MemoryRecord.model_validate(
                updated.model_dump()
            )

            self._memories[normalized_id] = validated

            return validated.model_copy(deep=True)

    def delete(self, memory_id: str) -> MemoryRecord:
        """Delete one memory by ID."""

        normalized_id = self._validate_memory_id(memory_id)

        with self._lock:
            memory = self._memories.pop(
                normalized_id,
                None,
            )

            if memory is None:
                raise MemoryNotFoundError(
                    f"memory not found: {normalized_id}"
                )

            return memory.model_copy(deep=True)

    def clear(self) -> None:
        """Delete all stored memories."""

        with self._lock:
            self._memories.clear()

    def count(
        self,
        *,
        query: MemoryQuery | None = None,
        now: datetime | None = None,
    ) -> int:
        """Return the number of matching memories."""

        return len(
            self.list(
                query=query,
                now=now,
            )
        )

    @staticmethod
    def _matches(
        *,
        memory: MemoryRecord,
        query: MemoryQuery,
        now: datetime,
    ) -> bool:
        """Return whether one memory satisfies all filters."""

        if (
            not query.include_expired
            and memory.expires_at is not None
            and memory.expires_at <= now
        ):
            return False

        if query.kinds and memory.kind not in query.kinds:
            return False

        if query.scopes and memory.scope not in query.scopes:
            return False

        if query.sources and memory.source not in query.sources:
            return False

        if (
            query.subject_id is not None
            and memory.subject_id != query.subject_id
        ):
            return False

        if (
            query.project_id is not None
            and memory.project_id != query.project_id
        ):
            return False

        if (
            query.session_id is not None
            and memory.session_id != query.session_id
        ):
            return False

        memory_tags = {
            tag.strip().casefold()
            for tag in memory.tags
        }
        required_tags = {
            tag.strip().casefold()
            for tag in query.tags
        }

        if not required_tags.issubset(memory_tags):
            return False

        if (
            query.minimum_importance is not None
            and memory.importance
            < query.minimum_importance
        ):
            return False

        if (
            query.minimum_confidence is not None
            and memory.confidence
            < query.minimum_confidence
        ):
            return False

        if (
            query.created_after is not None
            and memory.created_at < query.created_after
        ):
            return False

        return not (
            query.created_before is not None
            and memory.created_at > query.created_before
        )

    @staticmethod
    def _validate_memory_id(memory_id: str) -> str:
        """Reject blank memory identifiers."""

        if not memory_id.strip():
            raise ValueError(
                "memory ID must not be blank"
            )

        return memory_id

    @classmethod
    def _resolve_now(
        cls,
        now: datetime | None,
    ) -> datetime:
        """Return a validated UTC comparison time."""

        if now is None:
            return datetime.now(UTC)

        return cls._validate_utc_datetime(
            name="now",
            value=now,
        )

    @staticmethod
    def _validate_utc_datetime(
        *,
        name: str,
        value: datetime,
    ) -> datetime:
        """Require one timezone-aware UTC datetime."""

        if value.tzinfo is None:
            raise ValueError(
                f"{name} must be timezone-aware"
            )

        if value.utcoffset() != UTC.utcoffset(value):
            raise ValueError(
                f"{name} must use UTC"
            )

        return value
