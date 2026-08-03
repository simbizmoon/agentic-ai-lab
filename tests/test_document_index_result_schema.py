"""Tests for document indexing result schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.document_index_result import (
    DocumentIndexResult,
)


def test_document_index_result_accepts_valid_data() -> None:
    result = DocumentIndexResult(
        document_id="doc-1",
        chunk_count=3,
        embedding_model="test-model",
        embedding_dimensions=16,
    )

    assert result.document_id == "doc-1"
    assert result.chunk_count == 3
    assert result.embedding_model == "test-model"
    assert result.embedding_dimensions == 16


def test_document_index_result_allows_zero_chunks() -> None:
    result = DocumentIndexResult(
        document_id="doc-1",
        chunk_count=0,
        embedding_model="test-model",
        embedding_dimensions=16,
    )

    assert result.chunk_count == 0


@pytest.mark.parametrize(
    "chunk_count",
    [-1, -10],
)
def test_document_index_result_rejects_negative_count(
    chunk_count: int,
) -> None:
    with pytest.raises(ValidationError):
        DocumentIndexResult(
            document_id="doc-1",
            chunk_count=chunk_count,
            embedding_model="test-model",
            embedding_dimensions=16,
        )


@pytest.mark.parametrize(
    "dimensions",
    [0, -1],
)
def test_document_index_result_rejects_invalid_dimensions(
    dimensions: int,
) -> None:
    with pytest.raises(ValidationError):
        DocumentIndexResult(
            document_id="doc-1",
            chunk_count=1,
            embedding_model="test-model",
            embedding_dimensions=dimensions,
        )


def test_document_index_result_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        DocumentIndexResult(
            document_id="doc-1",
            chunk_count=1,
            embedding_model="test-model",
            embedding_dimensions=16,
            unknown_field="not allowed",
        )
