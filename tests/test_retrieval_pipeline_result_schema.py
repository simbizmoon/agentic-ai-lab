"""Tests for retrieval pipeline result schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.document_chunk import DocumentChunk
from app.schemas.rag_context import (
    RagCitation,
    RagContext,
)
from app.schemas.retrieval_pipeline_result import (
    RetrievalPipelineResult,
)
from app.schemas.retrieval_result import RetrievalResult


def retrieval_result(
    *,
    chunk_id: str = "doc-1:chunk:0000",
) -> RetrievalResult:
    """Return one valid retrieval result."""

    text = "Relevant evidence."

    return RetrievalResult(
        chunk=DocumentChunk(
            document_id="doc-1",
            chunk_id=chunk_id,
            ordinal=0,
            text=text,
            start_char=0,
            end_char=len(text),
        ),
        score=0.9,
        rank=1,
    )


def citation(
    *,
    chunk_id: str = "doc-1:chunk:0000",
) -> RagCitation:
    """Return one valid citation."""

    return RagCitation(
        citation_id="S1",
        document_id="doc-1",
        chunk_id=chunk_id,
        rank=1,
        score=0.9,
        start_char=0,
        end_char=18,
    )


def test_pipeline_result_accepts_matching_data() -> None:
    result = RetrievalPipelineResult(
        query="What is relevant?",
        results=[retrieval_result()],
        context=RagContext(
            context_text="[S1]\nRelevant evidence.",
            citations=[citation()],
        ),
    )

    assert result.query == "What is relevant?"
    assert len(result.results) == 1
    assert len(result.context.citations) == 1


def test_pipeline_result_allows_empty_results() -> None:
    result = RetrievalPipelineResult(
        query="Unknown topic",
        results=[],
        context=RagContext(
            context_text="",
            citations=[],
        ),
    )

    assert result.results == []
    assert result.context.context_text == ""


def test_pipeline_result_allows_filtered_context() -> None:
    result = RetrievalPipelineResult(
        query="Find evidence",
        results=[retrieval_result()],
        context=RagContext(
            context_text="",
            citations=[],
        ),
    )

    assert len(result.results) == 1
    assert result.context.citations == []


@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
        "\n\t",
    ],
)
def test_pipeline_result_rejects_blank_query(
    query: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match="query must not be blank",
    ):
        RetrievalPipelineResult(
            query=query,
            results=[],
            context=RagContext(
                context_text="",
                citations=[],
            ),
        )


def test_pipeline_result_rejects_too_many_citations() -> None:
    with pytest.raises(
        ValidationError,
        match="must not exceed",
    ):
        RetrievalPipelineResult(
            query="Find evidence",
            results=[],
            context=RagContext(
                context_text="[S1]\nEvidence.",
                citations=[citation()],
            ),
        )


def test_pipeline_result_rejects_unknown_citation_chunk() -> None:
    with pytest.raises(
        ValidationError,
        match="must reference retrieved Chunks",
    ):
        RetrievalPipelineResult(
            query="Find evidence",
            results=[
                retrieval_result(
                    chunk_id="doc-1:chunk:0000"
                )
            ],
            context=RagContext(
                context_text="[S1]\nDifferent evidence.",
                citations=[
                    citation(
                        chunk_id="doc-2:chunk:0000"
                    )
                ],
            ),
        )


def test_pipeline_result_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        RetrievalPipelineResult(
            query="Find evidence",
            results=[],
            context=RagContext(
                context_text="",
                citations=[],
            ),
            unknown_field="not allowed",
        )
