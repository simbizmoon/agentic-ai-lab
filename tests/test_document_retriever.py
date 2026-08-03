"""Tests for document indexing and retrieval services."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.rag.document_retriever import (
    DocumentRetriever,
    DocumentRetrieverError,
)
from app.rag.embedding_provider import EmbeddingProvider
from app.rag.in_memory_vector_store import (
    InMemoryVectorStore,
)
from app.schemas.document_embedding import TextEmbedding


class KeywordEmbeddingProvider(EmbeddingProvider):
    """Map known keywords to deterministic semantic test vectors."""

    @property
    def model_name(self) -> str:
        return "keyword-test-v1"

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

        technology_score = sum(
            normalized.count(keyword)
            for keyword in (
                "python",
                "software",
                "programming",
                "computer",
            )
        )
        cooking_score = sum(
            normalized.count(keyword)
            for keyword in (
                "cooking",
                "recipe",
                "food",
                "kitchen",
            )
        )
        health_score = sum(
            normalized.count(keyword)
            for keyword in (
                "health",
                "exercise",
                "fitness",
                "medical",
            )
        )

        if (
            technology_score == 0
            and cooking_score == 0
            and health_score == 0
        ):
            return [1.0, 1.0, 1.0]

        return [
            float(technology_score),
            float(cooking_score),
            float(health_score),
        ]


def make_retriever() -> DocumentRetriever:
    """Create a Retriever configured for deterministic tests."""

    return DocumentRetriever(
        embedding_provider=KeywordEmbeddingProvider(),
        vector_store=InMemoryVectorStore(),
    )


def test_index_document_returns_summary() -> None:
    retriever = make_retriever()

    result = retriever.index_document(
        document_id="doc-1",
        text=(
            "Python is a programming language."
            "\n\n"
            "Software can automate repeated work."
        ),
        chunk_size=45,
        chunk_overlap=5,
    )

    assert result.document_id == "doc-1"
    assert result.chunk_count == 2
    assert result.embedding_model == "keyword-test-v1"
    assert result.embedding_dimensions == 3
    assert retriever.indexed_chunk_count() == 2


def test_index_document_preserves_metadata() -> None:
    retriever = make_retriever()

    retriever.index_document(
        document_id="doc-1",
        text="Python programming document.",
        metadata={
            "source": "technology.txt",
            "category": "technology",
        },
    )

    results = retriever.retrieve(
        query="Python software",
        top_k=1,
    )

    assert results[0].chunk.metadata == {
        "source": "technology.txt",
        "category": "technology",
    }


def test_retrieve_returns_most_related_chunk() -> None:
    retriever = make_retriever()

    retriever.index_document(
        document_id="technology",
        text="Python software programming.",
    )
    retriever.index_document(
        document_id="cooking",
        text="Cooking food in the kitchen.",
    )
    retriever.index_document(
        document_id="health",
        text="Exercise supports health and fitness.",
    )

    results = retriever.retrieve(
        query="Which programming software uses Python?",
        top_k=2,
    )

    assert len(results) == 2
    assert results[0].chunk.document_id == "technology"
    assert results[0].rank == 1


def test_retrieve_can_find_cooking_document() -> None:
    retriever = make_retriever()

    retriever.index_document(
        document_id="technology",
        text="Python software programming.",
    )
    retriever.index_document(
        document_id="cooking",
        text="A cooking recipe for food.",
    )

    results = retriever.retrieve(
        query="Find a food recipe for cooking.",
        top_k=1,
    )

    assert results[0].chunk.document_id == "cooking"


def test_retrieve_can_find_health_document() -> None:
    retriever = make_retriever()

    retriever.index_document(
        document_id="technology",
        text="Computer programming software.",
    )
    retriever.index_document(
        document_id="health",
        text="Health and fitness through exercise.",
    )

    results = retriever.retrieve(
        query="How does exercise improve fitness?",
        top_k=1,
    )

    assert results[0].chunk.document_id == "health"


def test_character_chunking_strategy_is_supported() -> None:
    retriever = make_retriever()

    result = retriever.index_document(
        document_id="alphabet",
        text="abcdefghijklmnopqrstuvwxyz",
        chunk_size=10,
        chunk_overlap=2,
        chunking_strategy="characters",
    )

    assert result.chunk_count == 3
    assert retriever.indexed_chunk_count() == 3


def test_paragraph_chunking_strategy_is_default() -> None:
    retriever = make_retriever()

    result = retriever.index_document(
        document_id="paragraphs",
        text="First paragraph.\n\nSecond paragraph.",
        chunk_size=100,
        chunk_overlap=10,
    )

    assert result.chunk_count == 1


def test_reindexing_same_document_replaces_same_chunk_ids() -> None:
    retriever = make_retriever()

    retriever.index_document(
        document_id="doc-1",
        text="Python programming.",
    )
    retriever.index_document(
        document_id="doc-1",
        text="Cooking recipe.",
    )

    assert retriever.indexed_chunk_count() == 1

    results = retriever.retrieve(
        query="cooking food recipe",
        top_k=1,
    )

    assert results[0].chunk.text == "Cooking recipe."


def test_multiple_documents_are_stored_together() -> None:
    retriever = make_retriever()

    retriever.index_document(
        document_id="doc-1",
        text="Python programming.",
    )
    retriever.index_document(
        document_id="doc-2",
        text="Cooking recipe.",
    )

    assert retriever.indexed_chunk_count() == 2


def test_clear_removes_indexed_chunks() -> None:
    retriever = make_retriever()

    retriever.index_document(
        document_id="doc-1",
        text="Python programming.",
    )

    retriever.clear()

    assert retriever.indexed_chunk_count() == 0
    assert retriever.retrieve(
        query="Python",
    ) == []


@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
        "\n\t",
    ],
)
def test_retrieve_rejects_blank_query(
    query: str,
) -> None:
    retriever = make_retriever()

    with pytest.raises(
        DocumentRetrieverError,
        match="query must not be blank",
    ):
        retriever.retrieve(query=query)


def test_retrieve_rejects_invalid_top_k() -> None:
    retriever = make_retriever()

    with pytest.raises(
        Exception,
        match="top_k must be greater than zero",
    ):
        retriever.retrieve(
            query="Python",
            top_k=0,
        )


def test_unsupported_chunking_strategy_is_rejected() -> None:
    retriever = make_retriever()

    with pytest.raises(
        DocumentRetrieverError,
        match="unsupported chunking strategy",
    ):
        retriever.index_document(
            document_id="doc-1",
            text="Document text.",
            chunking_strategy="sentences",  # type: ignore[arg-type]
        )
