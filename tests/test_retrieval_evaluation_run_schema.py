"""Tests for retrieval evaluation run schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.rag_evaluation import (
    RetrievalEvaluationSummary,
)
from app.schemas.retrieval_evaluation_run import (
    RetrievalEvaluationRunResult,
)


def empty_summary() -> RetrievalEvaluationSummary:
    """Return an empty evaluation summary."""

    return RetrievalEvaluationSummary(
        cases=[],
        case_count=0,
        passed_count=0,
        pass_rate=0.0,
        mean_recall_at_k=0.0,
        mean_reciprocal_rank=0.0,
    )


def test_run_result_accepts_valid_data() -> None:
    result = RetrievalEvaluationRunResult(
        dataset_id="dataset-1",
        indexed_document_count=3,
        indexed_chunk_count=5,
        embedding_model="test-model",
        embedding_dimensions=3,
        summary=empty_summary(),
    )

    assert result.indexed_document_count == 3
    assert result.indexed_chunk_count == 5


def test_run_result_rejects_chunks_without_documents() -> None:
    with pytest.raises(
        ValidationError,
        match="require indexed documents",
    ):
        RetrievalEvaluationRunResult(
            dataset_id="dataset-1",
            indexed_document_count=0,
            indexed_chunk_count=1,
            embedding_model="test-model",
            embedding_dimensions=3,
            summary=empty_summary(),
        )


def test_run_result_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        RetrievalEvaluationRunResult(
            dataset_id="dataset-1",
            indexed_document_count=0,
            indexed_chunk_count=0,
            embedding_model="test-model",
            embedding_dimensions=3,
            summary=empty_summary(),
            unknown_field="not allowed",
        )
