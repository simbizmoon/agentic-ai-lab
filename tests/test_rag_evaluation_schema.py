"""Tests for deterministic RAG evaluation schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.rag_evaluation import (
    CitationEvaluationResult,
    RetrievalCaseEvaluation,
    RetrievalEvaluationCase,
    RetrievalEvaluationSummary,
)


def test_retrieval_case_accepts_valid_data() -> None:
    case = RetrievalEvaluationCase(
        case_id="case-1",
        query="What is Python?",
        expected_document_ids=["technology"],
        top_k=3,
    )

    assert case.top_k == 3


@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
        "\n\t",
    ],
)
def test_retrieval_case_rejects_blank_query(
    query: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match="query must not be blank",
    ):
        RetrievalEvaluationCase(
            case_id="case-1",
            query=query,
            expected_document_ids=["technology"],
            top_k=3,
        )


def test_retrieval_case_rejects_duplicate_expected_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="must be unique",
    ):
        RetrievalEvaluationCase(
            case_id="case-1",
            query="What is Python?",
            expected_document_ids=[
                "technology",
                "technology",
            ],
            top_k=3,
        )


def test_retrieval_evaluation_accepts_match() -> None:
    result = RetrievalCaseEvaluation(
        case_id="case-1",
        query="What is Python?",
        expected_document_ids=["technology"],
        retrieved_document_ids=[
            "cooking",
            "technology",
        ],
        matched_document_ids=["technology"],
        first_relevant_rank=2,
        recall_at_k=1.0,
        reciprocal_rank=0.5,
        passed=True,
    )

    assert result.first_relevant_rank == 2


def test_retrieval_evaluation_rejects_invalid_rr() -> None:
    with pytest.raises(
        ValidationError,
        match="must match first relevant rank",
    ):
        RetrievalCaseEvaluation(
            case_id="case-1",
            query="What is Python?",
            expected_document_ids=["technology"],
            retrieved_document_ids=["technology"],
            matched_document_ids=["technology"],
            first_relevant_rank=1,
            recall_at_k=1.0,
            reciprocal_rank=0.5,
            passed=True,
        )


def test_summary_accepts_consistent_counts() -> None:
    case = RetrievalCaseEvaluation(
        case_id="case-1",
        query="What is Python?",
        expected_document_ids=["technology"],
        retrieved_document_ids=["technology"],
        matched_document_ids=["technology"],
        first_relevant_rank=1,
        recall_at_k=1.0,
        reciprocal_rank=1.0,
        passed=True,
    )

    summary = RetrievalEvaluationSummary(
        cases=[case],
        case_count=1,
        passed_count=1,
        pass_rate=1.0,
        mean_recall_at_k=1.0,
        mean_reciprocal_rank=1.0,
    )

    assert summary.case_count == 1


def test_citation_evaluation_accepts_valid_data() -> None:
    result = CitationEvaluationResult(
        expected_citation_ids=["S1", "S2"],
        cited_ids=["S1"],
        matched_ids=["S1"],
        missing_ids=["S2"],
        unexpected_ids=[],
        precision=1.0,
        recall=0.5,
        passed=False,
    )

    assert result.missing_ids == ["S2"]


def test_citation_evaluation_rejects_inconsistent_matches() -> None:
    with pytest.raises(
        ValidationError,
        match="matched citation IDs are inconsistent",
    ):
        CitationEvaluationResult(
            expected_citation_ids=["S1"],
            cited_ids=["S1"],
            matched_ids=[],
            missing_ids=[],
            unexpected_ids=[],
            precision=1.0,
            recall=1.0,
            passed=True,
        )
