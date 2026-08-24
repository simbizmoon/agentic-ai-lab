"""Offline tests for persistent vector-index snapshot contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.document_chunk import DocumentChunk
from app.schemas.document_embedding import EmbeddedDocumentChunk, TextEmbedding
from app.schemas.persistent_vector_index import (
    PERSISTENT_VECTOR_INDEX_SCHEMA_VERSION,
    PersistentVectorIndexContent,
    PersistentVectorIndexSnapshot,
    calculate_vector_index_content_sha256,
    canonical_vector_index_content,
)

NOW = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)


def _record(
    chunk_id: str,
    *,
    model: str = "deterministic-v1",
    dimensions: int = 2,
    vector: list[float] | None = None,
) -> EmbeddedDocumentChunk:
    text = f"Text for {chunk_id}."
    return EmbeddedDocumentChunk(
        chunk=DocumentChunk(
            document_id=f"document-{chunk_id}",
            chunk_id=chunk_id,
            ordinal=0,
            text=text,
            start_char=0,
            end_char=len(text),
            metadata={
                "source_id": f"source-{chunk_id}",
                "source_type": "academic",
            },
        ),
        embedding=TextEmbedding(
            model_name=model,
            dimensions=dimensions,
            vector=vector or [1.0, 0.0],
        ),
        metadata={"embedding_model": model},
    )


def _content(
    *,
    records: list[EmbeddedDocumentChunk] | None = None,
    generation: int = 1,
    created_at: datetime = NOW,
    updated_at: datetime = NOW,
) -> PersistentVectorIndexContent:
    return PersistentVectorIndexContent(
        index_id="integrated-research-index",
        generation=generation,
        embedding_model="deterministic-v1",
        embedding_dimensions=2,
        created_at=created_at,
        updated_at=updated_at,
        records=records if records is not None else [_record("chunk-a")],
    )


def test_content_accepts_ordered_compatible_records() -> None:
    content = _content(records=[_record("chunk-a"), _record("chunk-b")])
    assert content.schema_version == PERSISTENT_VECTOR_INDEX_SCHEMA_VERSION
    assert content.generation == 1
    assert [item.chunk.chunk_id for item in content.records] == [
        "chunk-a",
        "chunk-b",
    ]


def test_empty_index_content_is_valid() -> None:
    content = _content(records=[])
    assert content.records == []


@pytest.mark.parametrize("field", ["index_id", "embedding_model"])
def test_content_rejects_blank_identity(field: str) -> None:
    data = _content().model_dump()
    data[field] = "   "
    with pytest.raises(ValidationError, match=f"{field} must not be blank"):
        PersistentVectorIndexContent(**data)


def test_content_requires_generation_from_one() -> None:
    with pytest.raises(ValidationError):
        _content(generation=0)


def test_content_rejects_unknown_schema_version() -> None:
    data = _content().model_dump()
    data["schema_version"] = 2
    with pytest.raises(ValidationError):
        PersistentVectorIndexContent(**data)


@pytest.mark.parametrize("field", ["created_at", "updated_at"])
def test_content_requires_timezone_aware_timestamps(field: str) -> None:
    data = _content().model_dump()
    data[field] = NOW.replace(tzinfo=None)
    with pytest.raises(ValidationError, match=f"{field} must be timezone-aware"):
        PersistentVectorIndexContent(**data)


def test_content_rejects_updated_before_created() -> None:
    with pytest.raises(ValidationError, match="must not be before"):
        _content(updated_at=NOW - timedelta(seconds=1))


def test_content_rejects_duplicate_chunk_ids_case_insensitively() -> None:
    with pytest.raises(ValidationError, match="chunk IDs must be unique"):
        _content(records=[_record("chunk-a"), _record("CHUNK-A")])


def test_content_requires_deterministic_chunk_id_order() -> None:
    with pytest.raises(ValidationError, match="ordered by chunk_id"):
        _content(records=[_record("chunk-b"), _record("chunk-a")])


def test_content_rejects_record_model_mismatch() -> None:
    with pytest.raises(ValidationError, match="snapshot embedding_model"):
        _content(records=[_record("chunk-a", model="different-model")])


def test_content_rejects_record_dimension_mismatch() -> None:
    with pytest.raises(ValidationError, match="snapshot embedding_dimensions"):
        _content(
            records=[
                _record(
                    "chunk-a",
                    dimensions=3,
                    vector=[1.0, 0.0, 0.0],
                )
            ]
        )


def test_canonical_bytes_are_stable() -> None:
    first = _content(records=[_record("chunk-a"), _record("chunk-b")])
    second = _content(records=[_record("chunk-a"), _record("chunk-b")])
    assert canonical_vector_index_content(first) == canonical_vector_index_content(
        second
    )
    assert calculate_vector_index_content_sha256(
        first
    ) == calculate_vector_index_content_sha256(second)


def test_digest_changes_when_searchable_content_changes() -> None:
    first = _content(records=[_record("chunk-a")])
    second = _content(records=[_record("chunk-b")])
    assert calculate_vector_index_content_sha256(
        first
    ) != calculate_vector_index_content_sha256(second)


def test_snapshot_seal_calculates_valid_digest() -> None:
    content = _content(records=[_record("chunk-a"), _record("chunk-b")])
    snapshot = PersistentVectorIndexSnapshot.seal(content)
    assert snapshot.content == content
    assert snapshot.content_sha256 == calculate_vector_index_content_sha256(content)


def test_snapshot_rejects_tampered_digest() -> None:
    with pytest.raises(ValidationError, match="must match canonical"):
        PersistentVectorIndexSnapshot(
            content=_content(),
            content_sha256="f" * 64,
        )


def test_snapshot_rejects_malformed_digest() -> None:
    with pytest.raises(ValidationError):
        PersistentVectorIndexSnapshot(
            content=_content(),
            content_sha256="not-a-sha256",
        )


def test_snapshot_detects_content_changed_after_prior_seal() -> None:
    first = PersistentVectorIndexSnapshot.seal(_content(generation=1))
    changed = _content(generation=2, updated_at=NOW + timedelta(seconds=1))
    with pytest.raises(ValidationError, match="must match canonical"):
        PersistentVectorIndexSnapshot(
            content=changed,
            content_sha256=first.content_sha256,
        )


def test_content_and_snapshot_reject_unknown_fields() -> None:
    content_data = _content().model_dump()
    content_data["database_path"] = "/tmp/index.db"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PersistentVectorIndexContent(**content_data)

    snapshot_data = PersistentVectorIndexSnapshot.seal(_content()).model_dump()
    snapshot_data["winner"] = "chunk-a"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PersistentVectorIndexSnapshot(**snapshot_data)


def test_models_are_frozen() -> None:
    content = _content()
    snapshot = PersistentVectorIndexSnapshot.seal(content)
    with pytest.raises(ValidationError):
        content.generation = 2
    with pytest.raises(ValidationError):
        snapshot.content_sha256 = "0" * 64
