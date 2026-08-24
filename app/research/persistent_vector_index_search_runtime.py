"""Search validated persistent vector-index snapshots without external calls."""

from __future__ import annotations

from app.rag.vector_math import cosine_similarity
from app.rag.vector_store import VectorStoreError
from app.research.persistent_vector_index_lifecycle import (
    PersistentVectorIndexSnapshotStore,
)
from app.schemas.document_embedding import TextEmbedding
from app.schemas.persistent_vector_index import PersistentVectorIndexSnapshot
from app.schemas.retrieval_result import RetrievalResult


class PersistentVectorIndexSearchRuntime:
    """Load the latest sealed generation and search it deterministically."""

    def __init__(self, *, store: PersistentVectorIndexSnapshotStore) -> None:
        self._store = store

    def snapshot(self) -> PersistentVectorIndexSnapshot | None:
        """Return the latest validated snapshot, if present."""

        return self._store.load()

    def count(self) -> int:
        """Return the number of records in the latest generation."""

        snapshot = self._store.load()
        return 0 if snapshot is None else len(snapshot.content.records)

    def search(
        self,
        *,
        query_embedding: TextEmbedding,
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        """Return latest-generation chunks ordered by cosine similarity."""

        if not isinstance(query_embedding, TextEmbedding):
            raise TypeError("query_embedding must be a TextEmbedding")
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
            raise VectorStoreError("top_k must be greater than zero")

        snapshot = self._store.load()
        if snapshot is None:
            return []
        content = snapshot.content
        if query_embedding.dimensions != content.embedding_dimensions:
            raise VectorStoreError(
                "query and persistent index embeddings must have matching dimensions"
            )
        if query_embedding.model_name != content.embedding_model:
            raise VectorStoreError(
                "query and persistent index embeddings must use the same model"
            )
        if not content.records:
            return []

        scored = [
            (
                cosine_similarity(
                    query_embedding.vector,
                    item.embedding.vector,
                ),
                item,
            )
            for item in content.records
        ]
        scored.sort(key=lambda value: (-value[0], value[1].chunk.chunk_id))
        return [
            RetrievalResult(chunk=item.chunk, score=score, rank=rank)
            for rank, (score, item) in enumerate(scored[:top_k], start=1)
        ]
