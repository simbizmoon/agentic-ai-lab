"""Tests for RAG answer evaluation result schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.rag_answer_evaluation_result import (
    RagAnswerCaseEvaluation,
)
from app.schemas.rag_evaluation import (
    CitationEvaluationResult,
)


def passing_citation_result() -> CitationEvaluationResult:
    """Return a passing citation evaluation."""

    return CitationEvaluationResult(
        expected_citation_ids=["S1"],
        cited_ids=["S1"],
        matched_ids=["S1"],
        missing_ids=[],
        unexpected_ids=[],
        precision=1.0,
        recall=1.0,
        passed=True,
    )


def test_case_result_accepts_success() -> None:
    result = RagAnswerCaseEvaluation(
        case_id="case-1",
        question="Question?",
        expected_document_ids=["doc-1"],
        retrieved_document_ids=["doc-1"],
        matched_document_ids=["doc-1"],
        expected_citation_ids=["S1"],
        cited_ids=["S1"],
        retrieval_passed=True,
        answer_generated=True,
        citation_evaluation=passing_citation_result(),
        answer_text="Grounded answer [S1].",
        passed=True,
    )

    assert result.passed is True


def test_case_result_rejects_success_without_answer() -> None:
    with pytest.raises(
        ValidationError,
        match="requires answer_text",
    ):
        RagAnswerCaseEvaluation(
            case_id="case-1",
            question="Question?",
            expected_document_ids=["doc-1"],
            retrieval_passed=True,
            answer_generated=True,
            citation_evaluation=(
                passing_citation_result()
            ),
            answer_text=None,
            passed=True,
        )


def test_case_result_accepts_failure() -> None:
    result = RagAnswerCaseEvaluation(
        case_id="case-1",
        question="Question?",
        expected_document_ids=["doc-1"],
        retrieval_passed=False,
        answer_generated=False,
        citation_evaluation=(
            CitationEvaluationResult(
                expected_citation_ids=[],
                cited_ids=[],
                matched_ids=[],
                missing_ids=[],
                unexpected_ids=[],
                precision=1.0,
                recall=1.0,
                passed=True,
            )
        ),
        error_code="model_request_failed",
        error_message="Request failed.",
        passed=False,
    )

    assert result.answer_generated is False


def test_case_result_rejects_inconsistent_passed_flag() -> None:
    with pytest.raises(
        ValidationError,
        match="passed flag is inconsistent",
    ):
        RagAnswerCaseEvaluation(
            case_id="case-1",
            question="Question?",
            expected_document_ids=["doc-1"],
            retrieved_document_ids=["doc-1"],
            matched_document_ids=["doc-1"],
            expected_citation_ids=["S1"],
            cited_ids=["S1"],
            retrieval_passed=True,
            answer_generated=True,
            citation_evaluation=(
                passing_citation_result()
            ),
            answer_text="Answer [S1].",
            passed=False,
        )
