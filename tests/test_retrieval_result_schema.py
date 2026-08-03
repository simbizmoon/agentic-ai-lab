"""Tests for retrieval result schemas."""

import math

import pytest
from pydantic import ValidationError

from app.schemas.document_chunk import DocumentChunk
from app.schemas.retrieval_result import RetrievalResult


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


def test_retrieval_result_accepts_valid_data() -> None:
    result = RetrievalResult(
        chunk=sample_chunk(),
        score=0.75,
        rank=1,
    )

    assert result.score == 0.75
    assert result.rank == 1


@pytest.mark.parametrize(
    "score",
    [
        -1.1,
        1.1,
        math.inf,
        -math.inf,
        math.nan,
    ],
)
def test_retrieval_result_rejects_invalid_score(
    score: float,
) -> None:
    with pytest.raises(ValidationError):
        RetrievalResult(
            chunk=sample_chunk(),
            score=score,
            rank=1,
        )


def test_retrieval_result_rejects_invalid_rank() -> None:
    with pytest.raises(ValidationError):
        RetrievalResult(
            chunk=sample_chunk(),
            score=0.5,
            rank=0,
        )


def test_retrieval_result_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        RetrievalResult(
            chunk=sample_chunk(),
            score=0.5,
            rank=1,
            unknown_field="not allowed",
        )
