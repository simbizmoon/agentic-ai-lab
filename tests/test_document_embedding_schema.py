"""Tests for document embedding schemas."""

import math

import pytest
from pydantic import ValidationError

from app.schemas.document_chunk import DocumentChunk
from app.schemas.document_embedding import (
    EmbeddedDocumentChunk,
    TextEmbedding,
)


def sample_chunk() -> DocumentChunk:
    """Return a valid test Chunk."""

    return DocumentChunk(
        document_id="doc-1",
        chunk_id="doc-1:chunk:0000",
        ordinal=0,
        text="hello",
        start_char=0,
        end_char=5,
    )


def test_text_embedding_accepts_valid_vector() -> None:
    embedding = TextEmbedding(
        model_name="test-model",
        dimensions=3,
        vector=[0.1, 0.2, 0.3],
    )

    assert embedding.model_name == "test-model"
    assert embedding.dimensions == 3
    assert embedding.vector == [0.1, 0.2, 0.3]


def test_text_embedding_rejects_dimension_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match="length must match dimensions",
    ):
        TextEmbedding(
            model_name="test-model",
            dimensions=3,
            vector=[0.1, 0.2],
        )


@pytest.mark.parametrize(
    "value",
    [
        math.inf,
        -math.inf,
        math.nan,
    ],
)
def test_text_embedding_rejects_nonfinite_values(
    value: float,
) -> None:
    with pytest.raises(
        ValidationError,
        match="values must be finite",
    ):
        TextEmbedding(
            model_name="test-model",
            dimensions=2,
            vector=[0.1, value],
        )


def test_text_embedding_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        TextEmbedding(
            model_name="test-model",
            dimensions=2,
            vector=[0.1, 0.2],
            unknown_field="not allowed",
        )


def test_embedded_chunk_accepts_valid_data() -> None:
    embedded = EmbeddedDocumentChunk(
        chunk=sample_chunk(),
        embedding=TextEmbedding(
            model_name="test-model",
            dimensions=2,
            vector=[0.6, 0.8],
        ),
        metadata={"embedding_model": "test-model"},
    )

    assert embedded.chunk.chunk_id == "doc-1:chunk:0000"
    assert embedded.embedding.dimensions == 2
    assert embedded.metadata == {
        "embedding_model": "test-model",
    }


def test_embedded_chunk_metadata_defaults_to_empty() -> None:
    embedded = EmbeddedDocumentChunk(
        chunk=sample_chunk(),
        embedding=TextEmbedding(
            model_name="test-model",
            dimensions=2,
            vector=[0.6, 0.8],
        ),
    )

    assert embedded.metadata == {}
