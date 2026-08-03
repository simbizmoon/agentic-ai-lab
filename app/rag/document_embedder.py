"""Services for embedding document Chunks."""

from __future__ import annotations

from collections.abc import Sequence

from app.rag.embedding_provider import (
    EmbeddingProvider,
    EmbeddingProviderError,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.document_embedding import (
    EmbeddedDocumentChunk,
)


def embed_document_chunks(
    *,
    chunks: Sequence[DocumentChunk],
    provider: EmbeddingProvider,
) -> list[EmbeddedDocumentChunk]:
    """Generate embeddings while preserving Chunk order."""

    if not chunks:
        return []

    texts = [chunk.text for chunk in chunks]
    embeddings = provider.embed_texts(texts)

    if len(embeddings) != len(chunks):
        raise EmbeddingProviderError(
            "provider returned an unexpected embedding count"
        )

    return [
        EmbeddedDocumentChunk(
            chunk=chunk,
            embedding=embedding,
            metadata={
                "embedding_model": embedding.model_name,
            },
        )
        for chunk, embedding in zip(
            chunks,
            embeddings,
            strict=True,
        )
    ]
