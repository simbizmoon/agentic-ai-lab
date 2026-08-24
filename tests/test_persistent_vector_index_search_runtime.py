"""Offline tests for persistent vector-index search and RAG integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.rag.context_builder import build_rag_context
from app.rag.vector_store import VectorStoreError
from app.research.file_persistent_vector_index import FilePersistentVectorIndex
from app.research.persistent_vector_index_lifecycle import (
    PersistentVectorIndexLifecycle,
)
from app.research.persistent_vector_index_search_runtime import (
    PersistentVectorIndexSearchRuntime,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.document_embedding import EmbeddedDocumentChunk, TextEmbedding

NOW = datetime(2026, 8, 24, 13, 0, tzinfo=UTC)


def _record(
    chunk_id: str,
    *,
    vector: list[float],
    text: str | None = None,
    source: str | None = None,
) -> EmbeddedDocumentChunk:
    chunk_text = text or f"Evidence for {chunk_id}."
    metadata = {}
    if source is not None:
        metadata["source"] = source
    return EmbeddedDocumentChunk(
        chunk=DocumentChunk(
            document_id=f"document-{chunk_id}",
            chunk_id=chunk_id,
            ordinal=0,
            text=chunk_text,
            start_char=0,
            end_char=len(chunk_text),
            metadata=metadata,
        ),
        embedding=TextEmbedding(
            model_name="deterministic-v1",
            dimensions=2,
            vector=vector,
        ),
    )


def _query(
    vector: list[float],
    *,
    model: str = "deterministic-v1",
) -> TextEmbedding:
    return TextEmbedding(model_name=model, dimensions=len(vector), vector=vector)


def _create_index(
    directory: Path,
    records: list[EmbeddedDocumentChunk],
) -> PersistentVectorIndexLifecycle:
    lifecycle = PersistentVectorIndexLifecycle(
        store=FilePersistentVectorIndex(directory=directory),
        clock=lambda: NOW,
    )
    lifecycle.create(
        index_id="integrated-research-index",
        embedding_model="deterministic-v1",
        embedding_dimensions=2,
        records=records,
    )
    return lifecycle


def test_missing_index_has_zero_count_and_empty_results(tmp_path: Path) -> None:
    runtime = PersistentVectorIndexSearchRuntime(
        store=FilePersistentVectorIndex(directory=tmp_path / "index")
    )
    assert runtime.count() == 0
    assert runtime.snapshot() is None
    assert runtime.search(query_embedding=_query([1.0, 0.0])) == []


def test_restart_searches_persisted_records_by_cosine_similarity(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "index"
    _create_index(
        directory,
        [
            _record("chunk-opposite", vector=[-1.0, 0.0]),
            _record("chunk-related", vector=[0.8, 0.2]),
            _record("chunk-exact", vector=[1.0, 0.0]),
        ],
    )

    restarted = PersistentVectorIndexSearchRuntime(
        store=FilePersistentVectorIndex(directory=directory)
    )
    results = restarted.search(query_embedding=_query([1.0, 0.0]), top_k=3)
    assert restarted.count() == 3
    assert [result.chunk.chunk_id for result in results] == [
        "chunk-exact",
        "chunk-related",
        "chunk-opposite",
    ]
    assert [result.rank for result in results] == [1, 2, 3]
    assert results[0].score == pytest.approx(1.0)
    assert results[-1].score == pytest.approx(-1.0)


def test_top_k_bounds_results_and_reranks_from_one(tmp_path: Path) -> None:
    directory = tmp_path / "index"
    _create_index(
        directory,
        [
            _record("chunk-a", vector=[1.0, 0.0]),
            _record("chunk-b", vector=[0.9, 0.1]),
            _record("chunk-c", vector=[0.0, 1.0]),
        ],
    )
    results = PersistentVectorIndexSearchRuntime(
        store=FilePersistentVectorIndex(directory=directory)
    ).search(query_embedding=_query([1.0, 0.0]), top_k=2)
    assert len(results) == 2
    assert [result.rank for result in results] == [1, 2]


def test_equal_scores_use_chunk_id_tie_break(tmp_path: Path) -> None:
    directory = tmp_path / "index"
    _create_index(
        directory,
        [
            _record("chunk-b", vector=[1.0, 0.0]),
            _record("chunk-a", vector=[1.0, 0.0]),
        ],
    )
    results = PersistentVectorIndexSearchRuntime(
        store=FilePersistentVectorIndex(directory=directory)
    ).search(query_embedding=_query([1.0, 0.0]), top_k=2)
    assert [result.chunk.chunk_id for result in results] == [
        "chunk-a",
        "chunk-b",
    ]


@pytest.mark.parametrize("top_k", [0, -1, True, 1.5])
def test_invalid_top_k_is_rejected_before_storage_load(
    tmp_path: Path,
    top_k: object,
) -> None:
    runtime = PersistentVectorIndexSearchRuntime(
        store=FilePersistentVectorIndex(directory=tmp_path / "index")
    )
    with pytest.raises(VectorStoreError, match="greater than zero"):
        runtime.search(query_embedding=_query([1.0, 0.0]), top_k=top_k)  # type: ignore[arg-type]


def test_query_type_is_explicitly_validated(tmp_path: Path) -> None:
    runtime = PersistentVectorIndexSearchRuntime(
        store=FilePersistentVectorIndex(directory=tmp_path / "index")
    )
    with pytest.raises(TypeError, match="must be a TextEmbedding"):
        runtime.search(query_embedding="invalid")  # type: ignore[arg-type]


def test_query_model_mismatch_is_rejected(tmp_path: Path) -> None:
    directory = tmp_path / "index"
    _create_index(directory, [_record("chunk-a", vector=[1.0, 0.0])])
    runtime = PersistentVectorIndexSearchRuntime(
        store=FilePersistentVectorIndex(directory=directory)
    )
    with pytest.raises(VectorStoreError, match="same model"):
        runtime.search(query_embedding=_query([1.0, 0.0], model="other"))


def test_query_dimensions_mismatch_is_rejected(tmp_path: Path) -> None:
    directory = tmp_path / "index"
    _create_index(directory, [_record("chunk-a", vector=[1.0, 0.0])])
    runtime = PersistentVectorIndexSearchRuntime(
        store=FilePersistentVectorIndex(directory=directory)
    )
    with pytest.raises(VectorStoreError, match="matching dimensions"):
        runtime.search(query_embedding=_query([1.0, 0.0, 0.0]))


def test_empty_existing_index_still_validates_query_contract(tmp_path: Path) -> None:
    directory = tmp_path / "index"
    _create_index(directory, [])
    runtime = PersistentVectorIndexSearchRuntime(
        store=FilePersistentVectorIndex(directory=directory)
    )
    assert runtime.search(query_embedding=_query([1.0, 0.0])) == []
    with pytest.raises(VectorStoreError, match="same model"):
        runtime.search(query_embedding=_query([1.0, 0.0], model="other"))


def test_runtime_loads_latest_generation_for_every_search(tmp_path: Path) -> None:
    directory = tmp_path / "index"
    lifecycle = _create_index(directory, [_record("chunk-a", vector=[1.0, 0.0])])
    runtime = PersistentVectorIndexSearchRuntime(
        store=FilePersistentVectorIndex(directory=directory)
    )
    assert runtime.count() == 1

    lifecycle = PersistentVectorIndexLifecycle(
        store=FilePersistentVectorIndex(directory=directory),
        clock=lambda: NOW + timedelta(minutes=1),
    )
    lifecycle.upsert([_record("chunk-b", vector=[0.0, 1.0])])
    assert runtime.count() == 2
    assert runtime.snapshot() is not None
    assert runtime.snapshot().content.generation == 2  # type: ignore[union-attr]


def test_deleted_record_disappears_from_subsequent_search(tmp_path: Path) -> None:
    directory = tmp_path / "index"
    _create_index(
        directory,
        [
            _record("chunk-a", vector=[1.0, 0.0]),
            _record("chunk-b", vector=[0.0, 1.0]),
        ],
    )
    runtime = PersistentVectorIndexSearchRuntime(
        store=FilePersistentVectorIndex(directory=directory)
    )
    lifecycle = PersistentVectorIndexLifecycle(
        store=FilePersistentVectorIndex(directory=directory),
        clock=lambda: NOW + timedelta(minutes=1),
    )
    lifecycle.delete(["chunk-a"])
    results = runtime.search(query_embedding=_query([1.0, 0.0]), top_k=5)
    assert [result.chunk.chunk_id for result in results] == ["chunk-b"]


def test_results_feed_existing_grounded_rag_context(tmp_path: Path) -> None:
    directory = tmp_path / "index"
    exact_text = "Persistent academic evidence with exact provenance."
    _create_index(
        directory,
        [
            _record(
                "academic-chunk",
                vector=[1.0, 0.0],
                text=exact_text,
                source="OpenAlex W123",
            ),
            _record("patent-chunk", vector=[0.0, 1.0]),
        ],
    )
    results = PersistentVectorIndexSearchRuntime(
        store=FilePersistentVectorIndex(directory=directory)
    ).search(query_embedding=_query([1.0, 0.0]), top_k=1)
    context = build_rag_context(results)
    assert exact_text in context.context_text
    assert "chunk_id=academic-chunk" in context.context_text
    assert context.citations[0].source == "OpenAlex W123"


def test_corrupt_snapshot_error_is_not_converted_to_empty_results(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "index"
    store = FilePersistentVectorIndex(directory=directory)
    store.snapshot_path.write_text("{broken", encoding="utf-8")
    runtime = PersistentVectorIndexSearchRuntime(store=store)
    with pytest.raises(RuntimeError, match="corrupt"):
        runtime.search(query_embedding=_query([1.0, 0.0]))
