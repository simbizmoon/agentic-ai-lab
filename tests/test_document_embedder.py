"""Tests for embedding document Chunks."""

from collections.abc import Sequence

import pytest

from app.rag.deterministic_embedding_provider import (
    DeterministicEmbeddingProvider,
)
from app.rag.document_chunker import (
    chunk_document_text,
)
from app.rag.document_embedder import (
    embed_document_chunks,
)
from app.rag.embedding_provider import (
    EmbeddingProvider,
    EmbeddingProviderError,
)
from app.schemas.document_embedding import TextEmbedding


def test_embed_document_chunks_preserves_order() -> None:
    chunks = chunk_document_text(
        document_id="doc-1",
        text="abcdefghijklmnop",
        chunk_size=6,
        chunk_overlap=2,
    )
    provider = DeterministicEmbeddingProvider(
        dimensions=8,
    )

    embedded = embed_document_chunks(
        chunks=chunks,
        provider=provider,
    )

    assert len(embedded) == len(chunks)
    assert [
        item.chunk.chunk_id
        for item in embedded
    ] == [
        chunk.chunk_id
        for chunk in chunks
    ]


def test_embed_document_chunks_records_model_name() -> None:
    chunks = chunk_document_text(
        document_id="doc-1",
        text="short document",
        chunk_size=100,
        chunk_overlap=10,
    )
    provider = DeterministicEmbeddingProvider(
        dimensions=8,
        model_name="deterministic-test",
    )

    embedded = embed_document_chunks(
        chunks=chunks,
        provider=provider,
    )

    assert embedded[0].embedding.model_name == (
        "deterministic-test"
    )
    assert embedded[0].metadata == {
        "embedding_model": "deterministic-test",
    }


def test_embed_document_chunks_returns_empty_for_no_chunks() -> None:
    provider = DeterministicEmbeddingProvider()

    embedded = embed_document_chunks(
        chunks=[],
        provider=provider,
    )

    assert embedded == []


class WrongCountProvider(EmbeddingProvider):
    """Provider that deliberately violates its contract."""

    @property
    def model_name(self) -> str:
        return "wrong-count"

    @property
    def dimensions(self) -> int:
        return 2

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[TextEmbedding]:
        return []


def test_embedder_rejects_wrong_embedding_count() -> None:
    chunks = chunk_document_text(
        document_id="doc-1",
        text="short document",
        chunk_size=100,
        chunk_overlap=10,
    )

    with pytest.raises(
        EmbeddingProviderError,
        match="unexpected embedding count",
    ):
        embed_document_chunks(
            chunks=chunks,
            provider=WrongCountProvider(),
        )
