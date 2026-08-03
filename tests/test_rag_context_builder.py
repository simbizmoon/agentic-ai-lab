"""Tests for building grounded RAG context."""

from app.rag.context_builder import build_rag_context
from app.schemas.document_chunk import DocumentChunk
from app.schemas.retrieval_result import RetrievalResult


def retrieval_result(
    *,
    document_id: str,
    chunk_id: str,
    text: str,
    rank: int,
    score: float,
    metadata: dict[str, object] | None = None,
) -> RetrievalResult:
    """Create a retrieval result for context tests."""

    return RetrievalResult(
        chunk=DocumentChunk(
            document_id=document_id,
            chunk_id=chunk_id,
            ordinal=rank - 1,
            text=text,
            start_char=0,
            end_char=len(text),
            metadata=dict(metadata or {}),
        ),
        rank=rank,
        score=score,
    )


def test_empty_results_create_empty_context() -> None:
    context = build_rag_context([])

    assert context.context_text == ""
    assert context.citations == []


def test_single_result_creates_context_and_citation() -> None:
    context = build_rag_context(
        [
            retrieval_result(
                document_id="doc-1",
                chunk_id="doc-1:chunk:0000",
                text="Relevant evidence.",
                rank=1,
                score=0.9,
                metadata={"source": "sample.txt"},
            )
        ]
    )

    assert "[S1]" in context.context_text
    assert "Relevant evidence." in context.context_text
    assert "source=sample.txt" in context.context_text
    assert len(context.citations) == 1
    assert context.citations[0].citation_id == "S1"
    assert context.citations[0].source == "sample.txt"


def test_results_are_ordered_by_rank() -> None:
    context = build_rag_context(
        [
            retrieval_result(
                document_id="doc-2",
                chunk_id="doc-2:chunk:0000",
                text="Second-ranked evidence.",
                rank=2,
                score=0.8,
            ),
            retrieval_result(
                document_id="doc-1",
                chunk_id="doc-1:chunk:0000",
                text="First-ranked evidence.",
                rank=1,
                score=0.9,
            ),
        ]
    )

    first_position = context.context_text.index(
        "First-ranked evidence."
    )
    second_position = context.context_text.index(
        "Second-ranked evidence."
    )

    assert first_position < second_position
    assert [
        citation.citation_id
        for citation in context.citations
    ] == ["S1", "S2"]


def test_context_includes_document_and_chunk_ids() -> None:
    context = build_rag_context(
        [
            retrieval_result(
                document_id="patent-v5",
                chunk_id="patent-v5:chunk:0003",
                text="Patent evidence.",
                rank=1,
                score=0.85,
            )
        ]
    )

    assert "document_id=patent-v5" in context.context_text
    assert (
        "chunk_id=patent-v5:chunk:0003"
        in context.context_text
    )


def test_context_formats_score_deterministically() -> None:
    context = build_rag_context(
        [
            retrieval_result(
                document_id="doc-1",
                chunk_id="chunk-1",
                text="Evidence.",
                rank=1,
                score=0.123456789,
            )
        ]
    )

    assert "score=0.123457" in context.context_text


def test_minimum_score_filters_low_scoring_results() -> None:
    context = build_rag_context(
        [
            retrieval_result(
                document_id="doc-high",
                chunk_id="chunk-high",
                text="High-scoring evidence.",
                rank=1,
                score=0.9,
            ),
            retrieval_result(
                document_id="doc-low",
                chunk_id="chunk-low",
                text="Low-scoring evidence.",
                rank=2,
                score=0.2,
            ),
        ],
        minimum_score=0.5,
    )

    assert "High-scoring evidence." in context.context_text
    assert "Low-scoring evidence." not in context.context_text
    assert len(context.citations) == 1


def test_all_filtered_results_create_empty_context() -> None:
    context = build_rag_context(
        [
            retrieval_result(
                document_id="doc-1",
                chunk_id="chunk-1",
                text="Low-scoring evidence.",
                rank=1,
                score=0.1,
            )
        ],
        minimum_score=0.5,
    )

    assert context.context_text == ""
    assert context.citations == []


def test_source_falls_back_to_filename() -> None:
    context = build_rag_context(
        [
            retrieval_result(
                document_id="doc-1",
                chunk_id="chunk-1",
                text="Evidence.",
                rank=1,
                score=0.8,
                metadata={"filename": "fallback.txt"},
            )
        ]
    )

    assert context.citations[0].source == "fallback.txt"
    assert "source=fallback.txt" in context.context_text


def test_source_falls_back_to_title() -> None:
    context = build_rag_context(
        [
            retrieval_result(
                document_id="doc-1",
                chunk_id="chunk-1",
                text="Evidence.",
                rank=1,
                score=0.8,
                metadata={"title": "Document title"},
            )
        ]
    )

    assert context.citations[0].source == "Document title"


def test_missing_source_is_allowed() -> None:
    context = build_rag_context(
        [
            retrieval_result(
                document_id="doc-1",
                chunk_id="chunk-1",
                text="Evidence.",
                rank=1,
                score=0.8,
            )
        ]
    )

    assert context.citations[0].source is None
    assert "source=" not in context.context_text
