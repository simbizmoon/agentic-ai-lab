"""Tests for the integrated retrieval pipeline."""

from __future__ import annotations

import math
from collections.abc import Sequence

import pytest

from app.rag.document_retriever import DocumentRetriever
from app.rag.embedding_provider import EmbeddingProvider
from app.rag.in_memory_vector_store import (
    InMemoryVectorStore,
)
from app.rag.retrieval_pipeline import (
    RetrievalPipeline,
    RetrievalPipelineError,
)
from app.schemas.document_embedding import TextEmbedding


class TopicEmbeddingProvider(EmbeddingProvider):
    """Map simple topics to deterministic test vectors."""

    @property
    def model_name(self) -> str:
        return "topic-test-v1"

    @property
    def dimensions(self) -> int:
        return 3

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[TextEmbedding]:
        return [
            TextEmbedding(
                model_name=self.model_name,
                dimensions=self.dimensions,
                vector=self._vector_for_text(text),
            )
            for text in texts
        ]

    def _vector_for_text(
        self,
        text: str,
    ) -> list[float]:
        normalized = text.lower()

        technology = sum(
            normalized.count(keyword)
            for keyword in (
                "python",
                "software",
                "programming",
            )
        )
        cooking = sum(
            normalized.count(keyword)
            for keyword in (
                "cooking",
                "recipe",
                "food",
            )
        )
        health = sum(
            normalized.count(keyword)
            for keyword in (
                "health",
                "exercise",
                "fitness",
            )
        )

        if technology == cooking == health == 0:
            return [1.0, 1.0, 1.0]

        return [
            float(technology),
            float(cooking),
            float(health),
        ]


def make_pipeline() -> RetrievalPipeline:
    """Create a deterministic retrieval pipeline."""

    retriever = DocumentRetriever(
        embedding_provider=TopicEmbeddingProvider(),
        vector_store=InMemoryVectorStore(),
    )

    return RetrievalPipeline(
        retriever=retriever,
    )


def index_test_documents(
    pipeline: RetrievalPipeline,
) -> None:
    """Index several topic-specific documents."""

    pipeline.retriever.index_document(
        document_id="technology",
        text="Python software programming.",
        metadata={"source": "technology.txt"},
    )
    pipeline.retriever.index_document(
        document_id="cooking",
        text="Cooking food with a simple recipe.",
        metadata={"source": "cooking.txt"},
    )
    pipeline.retriever.index_document(
        document_id="health",
        text="Exercise supports health and fitness.",
        metadata={"source": "health.txt"},
    )


def test_pipeline_returns_results_and_context() -> None:
    pipeline = make_pipeline()
    index_test_documents(pipeline)

    result = pipeline.run(
        query="How is Python used in software programming?",
        top_k=2,
    )

    assert result.query == (
        "How is Python used in software programming?"
    )
    assert len(result.results) == 2
    assert result.results[0].chunk.document_id == (
        "technology"
    )
    assert len(result.context.citations) == 2
    assert "[S1]" in result.context.context_text
    assert "Python software programming." in (
        result.context.context_text
    )


def test_pipeline_context_preserves_source_metadata() -> None:
    pipeline = make_pipeline()
    index_test_documents(pipeline)

    result = pipeline.run(
        query="Find a cooking recipe.",
        top_k=1,
    )

    assert result.results[0].chunk.document_id == "cooking"
    assert result.context.citations[0].source == (
        "cooking.txt"
    )
    assert "source=cooking.txt" in (
        result.context.context_text
    )


def test_pipeline_respects_top_k() -> None:
    pipeline = make_pipeline()
    index_test_documents(pipeline)

    result = pipeline.run(
        query="health exercise fitness",
        top_k=2,
    )

    assert len(result.results) == 2
    assert len(result.context.citations) == 2


def test_minimum_score_filters_context_only() -> None:
    pipeline = make_pipeline()
    index_test_documents(pipeline)

    result = pipeline.run(
        query="Python software programming",
        top_k=3,
        minimum_score=0.9,
    )

    assert len(result.results) == 3
    assert len(result.context.citations) == 1
    assert result.context.citations[0].document_id == (
        "technology"
    )


def test_high_minimum_score_can_create_empty_context() -> None:
    pipeline = make_pipeline()
    index_test_documents(pipeline)

    result = pipeline.run(
        query="unrecognized neutral topic",
        top_k=3,
        minimum_score=1.0,
    )

    assert len(result.results) == 3
    assert result.context.context_text == ""
    assert result.context.citations == []


def test_empty_store_returns_empty_pipeline_result() -> None:
    pipeline = make_pipeline()

    result = pipeline.run(
        query="Python programming",
    )

    assert result.results == []
    assert result.context.context_text == ""
    assert result.context.citations == []


@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
        "\n\t",
    ],
)
def test_pipeline_rejects_blank_query(
    query: str,
) -> None:
    pipeline = make_pipeline()

    with pytest.raises(
        RetrievalPipelineError,
        match="query must not be blank",
    ):
        pipeline.run(query=query)


@pytest.mark.parametrize(
    "top_k",
    [
        0,
        -1,
    ],
)
def test_pipeline_rejects_invalid_top_k(
    top_k: int,
) -> None:
    pipeline = make_pipeline()

    with pytest.raises(
        RetrievalPipelineError,
        match="top_k must be greater than zero",
    ):
        pipeline.run(
            query="Python",
            top_k=top_k,
        )


@pytest.mark.parametrize(
    "minimum_score",
    [
        math.inf,
        -math.inf,
        math.nan,
    ],
)
def test_pipeline_rejects_nonfinite_minimum_score(
    minimum_score: float,
) -> None:
    pipeline = make_pipeline()

    with pytest.raises(
        RetrievalPipelineError,
        match="minimum_score must be finite",
    ):
        pipeline.run(
            query="Python",
            minimum_score=minimum_score,
        )


def test_pipeline_result_citations_reference_results() -> None:
    pipeline = make_pipeline()
    index_test_documents(pipeline)

    result = pipeline.run(
        query="food cooking recipe",
        top_k=2,
    )

    result_chunk_ids = {
        item.chunk.chunk_id
        for item in result.results
    }

    assert all(
        citation.chunk_id in result_chunk_ids
        for citation in result.context.citations
    )
