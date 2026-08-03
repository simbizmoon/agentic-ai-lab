"""Tests for deterministic retrieval evaluation."""

import pytest

from app.rag.retrieval_evaluator import (
    evaluate_retrieval_case,
    summarize_retrieval_evaluations,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.rag_evaluation import (
    RetrievalEvaluationCase,
)
from app.schemas.retrieval_result import RetrievalResult


def result(
    *,
    document_id: str,
    rank: int,
    score: float,
) -> RetrievalResult:
    """Create one ranked retrieval result."""

    text = f"Evidence from {document_id}."

    return RetrievalResult(
        chunk=DocumentChunk(
            document_id=document_id,
            chunk_id=f"{document_id}:chunk:0000",
            ordinal=0,
            text=text,
            start_char=0,
            end_char=len(text),
        ),
        score=score,
        rank=rank,
    )


def evaluation_case(
    *,
    expected_document_ids: list[str],
    top_k: int = 3,
) -> RetrievalEvaluationCase:
    """Create one retrieval evaluation case."""

    return RetrievalEvaluationCase(
        case_id="case-1",
        query="Find the relevant document.",
        expected_document_ids=expected_document_ids,
        top_k=top_k,
    )


def test_first_result_match_has_rr_one() -> None:
    evaluation = evaluate_retrieval_case(
        case=evaluation_case(
            expected_document_ids=["technology"]
        ),
        results=[
            result(
                document_id="technology",
                rank=1,
                score=0.9,
            ),
            result(
                document_id="cooking",
                rank=2,
                score=0.5,
            ),
        ],
    )

    assert evaluation.first_relevant_rank == 1
    assert evaluation.reciprocal_rank == 1.0
    assert evaluation.recall_at_k == 1.0
    assert evaluation.passed is True


def test_second_result_match_has_rr_half() -> None:
    evaluation = evaluate_retrieval_case(
        case=evaluation_case(
            expected_document_ids=["technology"]
        ),
        results=[
            result(
                document_id="cooking",
                rank=1,
                score=0.9,
            ),
            result(
                document_id="technology",
                rank=2,
                score=0.8,
            ),
        ],
    )

    assert evaluation.first_relevant_rank == 2
    assert evaluation.reciprocal_rank == 0.5


def test_no_match_has_zero_metrics() -> None:
    evaluation = evaluate_retrieval_case(
        case=evaluation_case(
            expected_document_ids=["technology"]
        ),
        results=[
            result(
                document_id="cooking",
                rank=1,
                score=0.9,
            )
        ],
    )

    assert evaluation.first_relevant_rank is None
    assert evaluation.reciprocal_rank == 0.0
    assert evaluation.recall_at_k == 0.0
    assert evaluation.passed is False


def test_recall_supports_multiple_expected_documents() -> None:
    evaluation = evaluate_retrieval_case(
        case=evaluation_case(
            expected_document_ids=[
                "technology",
                "software-guide",
            ]
        ),
        results=[
            result(
                document_id="technology",
                rank=1,
                score=0.9,
            ),
            result(
                document_id="cooking",
                rank=2,
                score=0.7,
            ),
        ],
    )

    assert evaluation.matched_document_ids == [
        "technology"
    ]
    assert evaluation.recall_at_k == 0.5


def test_evaluation_respects_top_k() -> None:
    evaluation = evaluate_retrieval_case(
        case=evaluation_case(
            expected_document_ids=["technology"],
            top_k=1,
        ),
        results=[
            result(
                document_id="cooking",
                rank=1,
                score=0.9,
            ),
            result(
                document_id="technology",
                rank=2,
                score=0.8,
            ),
        ],
    )

    assert evaluation.retrieved_document_ids == [
        "cooking"
    ]
    assert evaluation.passed is False


def test_summary_calculates_aggregate_metrics() -> None:
    first = evaluate_retrieval_case(
        case=RetrievalEvaluationCase(
            case_id="case-1",
            query="Technology query",
            expected_document_ids=["technology"],
            top_k=2,
        ),
        results=[
            result(
                document_id="technology",
                rank=1,
                score=0.9,
            )
        ],
    )
    second = evaluate_retrieval_case(
        case=RetrievalEvaluationCase(
            case_id="case-2",
            query="Cooking query",
            expected_document_ids=["cooking"],
            top_k=2,
        ),
        results=[
            result(
                document_id="technology",
                rank=1,
                score=0.9,
            ),
            result(
                document_id="cooking",
                rank=2,
                score=0.8,
            ),
        ],
    )

    summary = summarize_retrieval_evaluations(
        [first, second]
    )

    assert summary.case_count == 2
    assert summary.passed_count == 2
    assert summary.pass_rate == 1.0
    assert summary.mean_recall_at_k == 1.0
    assert summary.mean_reciprocal_rank == pytest.approx(
        0.75
    )


def test_empty_summary_has_zero_metrics() -> None:
    summary = summarize_retrieval_evaluations([])

    assert summary.case_count == 0
    assert summary.pass_rate == 0.0
    assert summary.mean_recall_at_k == 0.0
    assert summary.mean_reciprocal_rank == 0.0
