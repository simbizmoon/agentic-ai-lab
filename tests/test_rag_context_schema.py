"""Tests for RAG context and citation schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.rag_context import (
    RagCitation,
    RagContext,
)


def sample_citation(
    *,
    citation_id: str = "S1",
) -> RagCitation:
    """Return a valid RAG citation."""

    return RagCitation(
        citation_id=citation_id,
        document_id="doc-1",
        chunk_id="doc-1:chunk:0000",
        rank=1,
        score=0.75,
        start_char=0,
        end_char=10,
        source="sample.txt",
    )


def test_rag_citation_accepts_valid_data() -> None:
    citation = sample_citation()

    assert citation.citation_id == "S1"
    assert citation.document_id == "doc-1"
    assert citation.score == 0.75
    assert citation.source == "sample.txt"


def test_rag_citation_allows_missing_source() -> None:
    citation = RagCitation(
        citation_id="S1",
        document_id="doc-1",
        chunk_id="doc-1:chunk:0000",
        rank=1,
        score=0.5,
        start_char=0,
        end_char=10,
    )

    assert citation.source is None


def test_rag_citation_rejects_invalid_range() -> None:
    with pytest.raises(
        ValidationError,
        match="end_char must be greater",
    ):
        RagCitation(
            citation_id="S1",
            document_id="doc-1",
            chunk_id="doc-1:chunk:0000",
            rank=1,
            score=0.5,
            start_char=10,
            end_char=10,
        )


def test_rag_context_accepts_context_and_citations() -> None:
    context = RagContext(
        context_text="[S1]\nRelevant evidence.",
        citations=[sample_citation()],
    )

    assert context.context_text.startswith("[S1]")
    assert len(context.citations) == 1


def test_empty_rag_context_is_valid() -> None:
    context = RagContext(
        context_text="",
        citations=[],
    )

    assert context.context_text == ""
    assert context.citations == []


def test_rag_context_rejects_citations_without_text() -> None:
    with pytest.raises(
        ValidationError,
        match="text is required",
    ):
        RagContext(
            context_text="",
            citations=[sample_citation()],
        )


def test_rag_context_rejects_text_without_citations() -> None:
    with pytest.raises(
        ValidationError,
        match="must be empty without citations",
    ):
        RagContext(
            context_text="Evidence without citation.",
            citations=[],
        )


def test_rag_context_rejects_duplicate_citation_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="citation IDs must be unique",
    ):
        RagContext(
            context_text="[S1]\nFirst.\n\n[S1]\nSecond.",
            citations=[
                sample_citation(citation_id="S1"),
                sample_citation(citation_id="S1"),
            ],
        )


def test_rag_context_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        RagContext(
            context_text="",
            citations=[],
            unknown_field="not allowed",
        )
