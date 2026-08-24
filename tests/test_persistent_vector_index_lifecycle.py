"""Offline tests for persistent vector-index lifecycle transitions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.research.file_persistent_vector_index import FilePersistentVectorIndex
from app.research.persistent_vector_index_lifecycle import (
    PersistentVectorIndexLifecycle,
    PersistentVectorIndexLifecycleError,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.document_embedding import EmbeddedDocumentChunk, TextEmbedding
from app.schemas.persistent_vector_index import PersistentVectorIndexSnapshot

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


class MemoryStore:
    def __init__(self) -> None:
        self.snapshot: PersistentVectorIndexSnapshot | None = None
        self.saved: list[PersistentVectorIndexSnapshot] = []

    def load(self) -> PersistentVectorIndexSnapshot | None:
        return self.snapshot

    def save(self, snapshot: PersistentVectorIndexSnapshot) -> None:
        self.snapshot = snapshot
        self.saved.append(snapshot)


def _record(
    chunk_id: str,
    *,
    model: str = "deterministic-v1",
    dimensions: int = 2,
    vector: list[float] | None = None,
    metadata: dict[str, Any] | None = None,
) -> EmbeddedDocumentChunk:
    text = f"Exact text for {chunk_id}."
    return EmbeddedDocumentChunk(
        chunk=DocumentChunk(
            document_id=f"document-{chunk_id}",
            chunk_id=chunk_id,
            ordinal=0,
            text=text,
            start_char=0,
            end_char=len(text),
            metadata={"source_id": f"source-{chunk_id}"},
        ),
        embedding=TextEmbedding(
            model_name=model,
            dimensions=dimensions,
            vector=vector or [1.0, 0.0],
        ),
        metadata=metadata or {},
    )


def _runtime(
    store: MemoryStore,
    timestamp: datetime = NOW,
) -> PersistentVectorIndexLifecycle:
    return PersistentVectorIndexLifecycle(store=store, clock=lambda: timestamp)


def _created(store: MemoryStore) -> PersistentVectorIndexLifecycle:
    runtime = _runtime(store)
    runtime.create(
        index_id="integrated-research-index",
        embedding_model="deterministic-v1",
        embedding_dimensions=2,
        records=[_record("chunk-b"), _record("chunk-a")],
    )
    return runtime


def test_create_seals_generation_one_in_deterministic_order() -> None:
    store = MemoryStore()
    snapshot = _created(store).load()
    assert snapshot is not None
    assert snapshot.content.generation == 1
    assert snapshot.content.created_at == NOW
    assert snapshot.content.updated_at == NOW
    assert [item.chunk.chunk_id for item in snapshot.content.records] == [
        "chunk-a",
        "chunk-b",
    ]
    assert store.saved == [snapshot]


def test_create_empty_index() -> None:
    store = MemoryStore()
    snapshot = _runtime(store).create(
        index_id="empty-index",
        embedding_model="deterministic-v1",
        embedding_dimensions=2,
    )
    assert snapshot.content.records == []


def test_create_never_overwrites_existing_index() -> None:
    store = MemoryStore()
    runtime = _created(store)
    with pytest.raises(PersistentVectorIndexLifecycleError, match="already exists"):
        runtime.create(
            index_id="replacement",
            embedding_model="deterministic-v1",
            embedding_dimensions=2,
        )
    assert len(store.saved) == 1


def test_upsert_adds_and_replaces_then_increments_once() -> None:
    store = MemoryStore()
    _created(store)
    later = NOW + timedelta(minutes=1)
    replacement = _record("chunk-a", vector=[0.0, 1.0], metadata={"new": True})
    added = _record("chunk-c")
    snapshot = _runtime(store, later).upsert([added, replacement])
    assert snapshot.content.generation == 2
    assert snapshot.content.created_at == NOW
    assert snapshot.content.updated_at == later
    assert [item.chunk.chunk_id for item in snapshot.content.records] == [
        "chunk-a",
        "chunk-b",
        "chunk-c",
    ]
    assert snapshot.content.records[0] == replacement


def test_identical_upsert_is_no_op_without_generation_or_write() -> None:
    store = MemoryStore()
    _created(store)
    current = store.snapshot
    assert current is not None
    result = _runtime(store, NOW + timedelta(minutes=1)).upsert(
        [current.content.records[0]]
    )
    assert result is current
    assert result.content.generation == 1
    assert len(store.saved) == 1


@pytest.mark.parametrize(
    ("record", "message"),
    [
        (_record("chunk-c", model="other"), "model does not match"),
        (
            _record("chunk-c", dimensions=3, vector=[1.0, 0.0, 0.0]),
            "dimensions do not match",
        ),
    ],
)
def test_upsert_rejects_incompatible_embedding_without_write(
    record: EmbeddedDocumentChunk,
    message: str,
) -> None:
    store = MemoryStore()
    runtime = _created(store)
    with pytest.raises(PersistentVectorIndexLifecycleError, match=message):
        runtime.upsert([record])
    assert len(store.saved) == 1


def test_upsert_rejects_case_insensitive_duplicate_batch() -> None:
    store = MemoryStore()
    runtime = _created(store)
    with pytest.raises(PersistentVectorIndexLifecycleError, match="must be unique"):
        runtime.upsert([_record("chunk-c"), _record("CHUNK-C")])
    assert len(store.saved) == 1


def test_delete_targeted_records_and_preserve_others() -> None:
    store = MemoryStore()
    _created(store)
    snapshot = _runtime(store, NOW + timedelta(minutes=1)).delete(["CHUNK-A"])
    assert snapshot.content.generation == 2
    assert [item.chunk.chunk_id for item in snapshot.content.records] == ["chunk-b"]


def test_delete_missing_or_empty_is_no_op() -> None:
    store = MemoryStore()
    runtime = _created(store)
    first = runtime.delete(["missing"])
    second = runtime.delete([])
    assert first is store.snapshot
    assert second is store.snapshot
    assert len(store.saved) == 1


def test_delete_all_records_produces_valid_empty_generation() -> None:
    store = MemoryStore()
    _created(store)
    snapshot = _runtime(store, NOW + timedelta(minutes=1)).delete(
        ["chunk-a", "chunk-b"]
    )
    assert snapshot.content.generation == 2
    assert snapshot.content.records == []


@pytest.mark.parametrize("operation", ["upsert", "delete"])
def test_mutation_requires_existing_index(operation: str) -> None:
    runtime = _runtime(MemoryStore())
    with pytest.raises(PersistentVectorIndexLifecycleError, match="does not exist"):
        if operation == "upsert":
            runtime.upsert([_record("chunk-a")])
        else:
            runtime.delete(["chunk-a"])


def test_changed_transition_rejects_clock_rollback_without_write() -> None:
    store = MemoryStore()
    _created(store)
    with pytest.raises(PersistentVectorIndexLifecycleError, match="move backwards"):
        _runtime(store, NOW - timedelta(seconds=1)).upsert([_record("chunk-c")])
    assert len(store.saved) == 1


@pytest.mark.parametrize("timestamp", [NOW.replace(tzinfo=None), "not-a-time"])
def test_create_rejects_invalid_clock(timestamp: object) -> None:
    store = MemoryStore()
    runtime = PersistentVectorIndexLifecycle(store=store, clock=lambda: timestamp)  # type: ignore[return-value]
    with pytest.raises(PersistentVectorIndexLifecycleError, match="clock must return"):
        runtime.create(
            index_id="index",
            embedding_model="deterministic-v1",
            embedding_dimensions=2,
        )
    assert store.saved == []


def test_input_collections_are_not_mutated() -> None:
    store = MemoryStore()
    runtime = _created(store)
    records = [_record("chunk-d"), _record("chunk-c")]
    original = list(records)
    runtime.upsert(records)
    assert records == original


def test_file_store_restart_preserves_latest_generation(tmp_path: Path) -> None:
    directory = tmp_path / "index"
    first = PersistentVectorIndexLifecycle(
        store=FilePersistentVectorIndex(directory=directory),
        clock=lambda: NOW,
    )
    first.create(
        index_id="integrated-research-index",
        embedding_model="deterministic-v1",
        embedding_dimensions=2,
        records=[_record("chunk-a")],
    )
    first = PersistentVectorIndexLifecycle(
        store=FilePersistentVectorIndex(directory=directory),
        clock=lambda: NOW + timedelta(minutes=1),
    )
    first.upsert([_record("chunk-b")])

    restored = PersistentVectorIndexLifecycle(
        store=FilePersistentVectorIndex(directory=directory)
    ).load()
    assert restored is not None
    assert restored.content.generation == 2
    assert [item.chunk.chunk_id for item in restored.content.records] == [
        "chunk-a",
        "chunk-b",
    ]


def test_invalid_sequence_shapes_fail_before_write() -> None:
    store = MemoryStore()
    runtime = _created(store)
    with pytest.raises(TypeError, match="records must be a sequence"):
        runtime.upsert("chunk-a")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="chunk_ids must be a sequence"):
        runtime.delete("chunk-a")  # type: ignore[arg-type]
    with pytest.raises(PersistentVectorIndexLifecycleError, match="blank"):
        runtime.delete(["  "])
    assert len(store.saved) == 1
