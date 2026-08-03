"""Tests for grounded answer result schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.grounded_answer_result import (
    GroundedAnswerResult,
)
from app.schemas.rag_context import RagCitation


def citation(
    citation_id: str = "S1",
) -> RagCitation:
    """Return a valid citation."""

    return RagCitation(
        citation_id=citation_id,
        document_id="doc-1",
        chunk_id=f"doc-1:chunk:{citation_id}",
        rank=1,
        score=0.9,
        start_char=0,
        end_char=10,
        source="sample.txt",
    )


def test_result_accepts_grounded_answer() -> None:
    result = GroundedAnswerResult(
        question="What is Python?",
        answer="Python is a programming language [S1].",
        citations=[citation()],
        cited_ids=["S1"],
        response_id="resp_123",
        model_name="test-model",
        evidence_available=True,
    )

    assert result.cited_ids == ["S1"]
    assert result.evidence_available is True


def test_result_accepts_answer_without_evidence() -> None:
    result = GroundedAnswerResult(
        question="What is unknown?",
        answer=(
            "The supplied evidence does not contain enough "
            "information."
        ),
        citations=[],
        cited_ids=[],
        model_name="test-model",
        evidence_available=False,
    )

    assert result.citations == []
    assert result.cited_ids == []


@pytest.mark.parametrize(
    "question",
    [
        "",
        "   ",
        "\n\t",
    ],
)
def test_result_rejects_blank_question(
    question: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match="question must not be blank",
    ):
        GroundedAnswerResult(
            question=question,
            answer="Answer.",
            citations=[],
            cited_ids=[],
            model_name="test-model",
            evidence_available=False,
        )


def test_result_rejects_duplicate_cited_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="cited IDs must be unique",
    ):
        GroundedAnswerResult(
            question="What is Python?",
            answer="Answer [S1].",
            citations=[citation()],
            cited_ids=["S1", "S1"],
            model_name="test-model",
            evidence_available=True,
        )


def test_result_rejects_unknown_cited_id() -> None:
    with pytest.raises(
        ValidationError,
        match="reference available citations",
    ):
        GroundedAnswerResult(
            question="What is Python?",
            answer="Answer [S2].",
            citations=[citation("S1")],
            cited_ids=["S2"],
            model_name="test-model",
            evidence_available=True,
        )


def test_result_rejects_evidence_flag_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match="must match citation availability",
    ):
        GroundedAnswerResult(
            question="What is Python?",
            answer="Answer.",
            citations=[citation()],
            cited_ids=[],
            model_name="test-model",
            evidence_available=False,
        )


def test_result_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        GroundedAnswerResult(
            question="What is unknown?",
            answer="No evidence.",
            citations=[],
            cited_ids=[],
            model_name="test-model",
            evidence_available=False,
            unknown_field="not allowed",
        )
