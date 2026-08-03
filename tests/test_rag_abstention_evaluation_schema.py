"""Tests for RAG abstention evaluation schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.rag_abstention_evaluation import (
    RagAbstentionCaseEvaluation,
    RagAbstentionEvaluationCase,
)


def test_case_accepts_valid_data() -> None:
    case = RagAbstentionEvaluationCase(
        case_id="case-1",
        question="Unknown question?",
        top_k=2,
        minimum_score=0.8,
        expected_markers=["근거가 부족"],
    )

    assert case.minimum_score == 0.8


@pytest.mark.parametrize(
    "question",
    ["", "   ", "\n\t"],
)
def test_case_rejects_blank_question(
    question: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match="question must not be blank",
    ):
        RagAbstentionEvaluationCase(
            case_id="case-1",
            question=question,
            top_k=2,
            minimum_score=0.8,
            expected_markers=["근거가 부족"],
        )


def test_case_rejects_duplicate_markers() -> None:
    with pytest.raises(
        ValidationError,
        match="markers must be unique",
    ):
        RagAbstentionEvaluationCase(
            case_id="case-1",
            question="Unknown question?",
            top_k=2,
            minimum_score=0.8,
            expected_markers=[
                "근거가 부족",
                "근거가 부족",
            ],
        )


def test_result_accepts_successful_abstention() -> None:
    result = RagAbstentionCaseEvaluation(
        case_id="case-1",
        question="Unknown question?",
        retrieved_document_ids=[],
        cited_ids=[],
        answer_text=(
            "제공된 근거만으로는 답변할 수 없습니다."
        ),
        matched_markers=["근거만으로는"],
        no_evidence=True,
        no_citations=True,
        abstention_detected=True,
        answer_generated=True,
        passed=True,
    )

    assert result.passed is True


def test_result_rejects_inconsistent_passed_flag() -> None:
    with pytest.raises(
        ValidationError,
        match="passed flag is inconsistent",
    ):
        RagAbstentionCaseEvaluation(
            case_id="case-1",
            question="Unknown question?",
            retrieved_document_ids=[],
            cited_ids=[],
            answer_text="근거가 부족합니다.",
            matched_markers=["근거가 부족"],
            no_evidence=True,
            no_citations=True,
            abstention_detected=True,
            answer_generated=True,
            passed=False,
        )
