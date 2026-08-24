"""Deterministic lifecycle operations for persistent vector-index snapshots."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Protocol

from app.schemas.document_embedding import EmbeddedDocumentChunk
from app.schemas.persistent_vector_index import (
    PersistentVectorIndexContent,
    PersistentVectorIndexSnapshot,
)


class PersistentVectorIndexLifecycleError(RuntimeError):
    """Raised when a requested index lifecycle transition is invalid."""


class PersistentVectorIndexSnapshotStore(Protocol):
    """Minimal storage contract required by the lifecycle runtime."""

    def load(self) -> PersistentVectorIndexSnapshot | None: ...

    def save(self, snapshot: PersistentVectorIndexSnapshot) -> None: ...


class PersistentVectorIndexLifecycle:
    """Create and evolve one persistent index through sealed generations."""

    def __init__(
        self,
        *,
        store: PersistentVectorIndexSnapshotStore,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC))

    def load(self) -> PersistentVectorIndexSnapshot | None:
        """Return the current validated snapshot, if one exists."""

        return self._store.load()

    def create(
        self,
        *,
        index_id: str,
        embedding_model: str,
        embedding_dimensions: int,
        records: Sequence[EmbeddedDocumentChunk] = (),
    ) -> PersistentVectorIndexSnapshot:
        """Create generation one; never overwrite an existing index."""

        if self._store.load() is not None:
            raise PersistentVectorIndexLifecycleError(
                "persistent vector index already exists"
            )
        timestamp = self._timestamp()
        content = PersistentVectorIndexContent(
            index_id=index_id,
            generation=1,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
            created_at=timestamp,
            updated_at=timestamp,
            records=self._normalize_records(records),
        )
        snapshot = PersistentVectorIndexSnapshot.seal(content)
        self._store.save(snapshot)
        return snapshot

    def upsert(
        self,
        records: Sequence[EmbeddedDocumentChunk],
    ) -> PersistentVectorIndexSnapshot:
        """Add or replace records by case-insensitive chunk identity."""

        current = self._require_snapshot()
        incoming = self._normalize_records(records)
        self._validate_compatibility(current.content, incoming)

        merged = {
            item.chunk.chunk_id.casefold(): item for item in current.content.records
        }
        for item in incoming:
            merged[item.chunk.chunk_id.casefold()] = item
        next_records = sorted(
            merged.values(), key=lambda item: item.chunk.chunk_id.casefold()
        )
        if next_records == current.content.records:
            return current
        return self._save_transition(current, next_records)

    def delete(self, chunk_ids: Sequence[str]) -> PersistentVectorIndexSnapshot:
        """Delete exact chunk identities; missing identities are a no-op."""

        current = self._require_snapshot()
        normalized_ids = self._normalize_chunk_ids(chunk_ids)
        if not normalized_ids:
            return current
        next_records = [
            item
            for item in current.content.records
            if item.chunk.chunk_id.casefold() not in normalized_ids
        ]
        if next_records == current.content.records:
            return current
        return self._save_transition(current, next_records)

    def _save_transition(
        self,
        current: PersistentVectorIndexSnapshot,
        records: list[EmbeddedDocumentChunk],
    ) -> PersistentVectorIndexSnapshot:
        timestamp = self._timestamp()
        if timestamp < current.content.updated_at:
            raise PersistentVectorIndexLifecycleError(
                "lifecycle clock must not move backwards"
            )
        content = PersistentVectorIndexContent(
            index_id=current.content.index_id,
            generation=current.content.generation + 1,
            embedding_model=current.content.embedding_model,
            embedding_dimensions=current.content.embedding_dimensions,
            created_at=current.content.created_at,
            updated_at=timestamp,
            records=records,
        )
        snapshot = PersistentVectorIndexSnapshot.seal(content)
        self._store.save(snapshot)
        return snapshot

    def _require_snapshot(self) -> PersistentVectorIndexSnapshot:
        snapshot = self._store.load()
        if snapshot is None:
            raise PersistentVectorIndexLifecycleError(
                "persistent vector index does not exist"
            )
        return snapshot

    def _timestamp(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime):
            raise PersistentVectorIndexLifecycleError(
                "lifecycle clock must return a datetime"
            )
        if value.tzinfo is None or value.utcoffset() is None:
            raise PersistentVectorIndexLifecycleError(
                "lifecycle clock must return a timezone-aware datetime"
            )
        return value

    @staticmethod
    def _normalize_records(
        records: Sequence[EmbeddedDocumentChunk],
    ) -> list[EmbeddedDocumentChunk]:
        if isinstance(records, (str, bytes)):
            raise TypeError("records must be a sequence of embedded chunks")
        normalized = list(records)
        if not all(isinstance(item, EmbeddedDocumentChunk) for item in normalized):
            raise TypeError("records must contain EmbeddedDocumentChunk values")
        identities = [item.chunk.chunk_id.casefold() for item in normalized]
        if len(identities) != len(set(identities)):
            raise PersistentVectorIndexLifecycleError(
                "incoming chunk IDs must be unique"
            )
        return sorted(normalized, key=lambda item: item.chunk.chunk_id.casefold())

    @staticmethod
    def _normalize_chunk_ids(chunk_ids: Sequence[str]) -> set[str]:
        if isinstance(chunk_ids, (str, bytes)):
            raise TypeError("chunk_ids must be a sequence of strings")
        normalized: set[str] = set()
        for value in chunk_ids:
            if not isinstance(value, str):
                raise TypeError("chunk_ids must contain strings")
            if not value.strip():
                raise PersistentVectorIndexLifecycleError(
                    "chunk_ids must not contain blank values"
                )
            normalized.add(value.casefold())
        return normalized

    @staticmethod
    def _validate_compatibility(
        content: PersistentVectorIndexContent,
        records: Sequence[EmbeddedDocumentChunk],
    ) -> None:
        for item in records:
            if item.embedding.model_name != content.embedding_model:
                raise PersistentVectorIndexLifecycleError(
                    "record embedding model does not match persistent index"
                )
            if item.embedding.dimensions != content.embedding_dimensions:
                raise PersistentVectorIndexLifecycleError(
                    "record embedding dimensions do not match persistent index"
                )
