"""Tests for RAG question-answering result schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.document_chunk import DocumentChunk
from app.schemas.grounded_answer_result import (
    GroundedAnswerResult,
)
from app.schemas.rag_context import (
    RagCitation,
    RagContext,
)
from app.schemas.rag_question_answering_result import (
    RagQuestionAnsweringResult,
)
from app.schemas.retrieval_pipeline_result import (
    RetrievalPipelineResult,
)
from app.schemas.retrieval_result import RetrievalResult


def citation() -> RagCitation:
    """Return one valid citation."""

    return RagCitation(
        citation_id="S1",
        document_id="doc-1",
        chunk_id="doc-1:chunk:0000",
        rank=1,
        score=0.9,
        start_char=0,
        end_char=18,
        source="sample.txt",
    )


def retrieval(
    *,
    query: str = "What is Python?",
    include_evidence: bool = True,
) -> RetrievalPipelineResult:
    """Return a valid retrieval result."""

    if not include_evidence:
        return RetrievalPipelineResult(
            query=query,
            results=[],
            context=RagContext(
                context_text="",
                citations=[],
            ),
        )

    text = "Python is a language."

    return RetrievalPipelineResult(
        query=query,
        results=[
            RetrievalResult(
                chunk=DocumentChunk(
                    document_id="doc-1",
                    chunk_id="doc-1:chunk:0000",
                    ordinal=0,
                    text=text,
                    start_char=0,
                    end_char=len(text),
                ),
                score=0.9,
                rank=1,
            )
        ],
        context=RagContext(
            context_text="[S1]\nPython is a language.",
            citations=[citation()],
        ),
    )


def answer(
    *,
    question: str = "What is Python?",
    include_evidence: bool = True,
) -> GroundedAnswerResult:
    """Return a valid grounded answer."""

    if not include_evidence:
        return GroundedAnswerResult(
            question=question,
            answer=(
                "The supplied evidence does not contain enough "
                "information."
            ),
            citations=[],
            cited_ids=[],
            model_name="test-model",
            evidence_available=False,
        )

    return GroundedAnswerResult(
        question=question,
        answer="Python is a language [S1].",
        citations=[citation()],
        cited_ids=["S1"],
        model_name="test-model",
        evidence_available=True,
    )


def test_result_accepts_matching_retrieval_and_answer() -> None:
    result = RagQuestionAnsweringResult(
        retrieval=retrieval(),
        answer=answer(),
    )

    assert result.retrieval.query == "What is Python?"
    assert result.answer.cited_ids == ["S1"]


def test_result_accepts_no_evidence_operation() -> None:
    result = RagQuestionAnsweringResult(
        retrieval=retrieval(
            include_evidence=False,
        ),
        answer=answer(
            include_evidence=False,
        ),
    )

    assert result.retrieval.context.citations == []
    assert result.answer.evidence_available is False


def test_result_rejects_question_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match="query must match answer question",
    ):
        RagQuestionAnsweringResult(
            retrieval=retrieval(
                query="What is Python?",
            ),
            answer=answer(
                question="What is Java?",
            ),
        )


def test_result_rejects_citation_mismatch() -> None:
    mismatched_answer = GroundedAnswerResult(
        question="What is Python?",
        answer="Python is a language [S2].",
        citations=[
            RagCitation(
                citation_id="S2",
                document_id="doc-2",
                chunk_id="doc-2:chunk:0000",
                rank=1,
                score=0.8,
                start_char=0,
                end_char=10,
            )
        ],
        cited_ids=["S2"],
        model_name="test-model",
        evidence_available=True,
    )

    with pytest.raises(
        ValidationError,
        match="citations must match",
    ):
        RagQuestionAnsweringResult(
            retrieval=retrieval(),
            answer=mismatched_answer,
        )


def test_result_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        RagQuestionAnsweringResult(
            retrieval=retrieval(),
            answer=answer(),
            unknown_field="not allowed",
        )
