"""In-memory Vector Store for local retrieval workflows."""

from __future__ import annotations

from collections.abc import Sequence

from app.rag.vector_math import cosine_similarity
from app.rag.vector_store import (
    VectorStore,
    VectorStoreError,
)
from app.schemas.document_embedding import (
    EmbeddedDocumentChunk,
    TextEmbedding,
)
from app.schemas.retrieval_result import RetrievalResult


class InMemoryVectorStore(VectorStore):
    """Store document embeddings in process memory."""

    def __init__(self) -> None:
        self._items: dict[str, EmbeddedDocumentChunk] = {}

    def add(
        self,
        items: Sequence[EmbeddedDocumentChunk],
    ) -> None:
        """Add or replace items by Chunk identifier."""

        for item in items:
            chunk_id = item.chunk.chunk_id
            self._items[chunk_id] = item

    def search(
        self,
        *,
        query_embedding: TextEmbedding,
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        """Return stored Chunks ordered by cosine similarity."""

        if top_k <= 0:
            raise VectorStoreError(
                "top_k must be greater than zero"
            )

        if not self._items:
            return []

        scored_items: list[
            tuple[float, EmbeddedDocumentChunk]
        ] = []

        for item in self._items.values():
            if (
                item.embedding.dimensions
                != query_embedding.dimensions
            ):
                raise VectorStoreError(
                    "query and stored embeddings must have "
                    "matching dimensions"
                )

            if (
                item.embedding.model_name
                != query_embedding.model_name
            ):
                raise VectorStoreError(
                    "query and stored embeddings must use "
                    "the same model"
                )

            score = cosine_similarity(
                query_embedding.vector,
                item.embedding.vector,
            )
            scored_items.append((score, item))

        scored_items.sort(
            key=lambda scored: (
                -scored[0],
                scored[1].chunk.chunk_id,
            )
        )

        selected = scored_items[:top_k]

        return [
            RetrievalResult(
                chunk=item.chunk,
                score=score,
                rank=rank,
            )
            for rank, (score, item) in enumerate(
                selected,
                start=1,
            )
        ]

    def clear(self) -> None:
        """Remove every stored Chunk."""

        self._items.clear()

    def count(self) -> int:
        """Return the number of stored Chunks."""

        return len(self._items)
