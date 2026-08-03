"""Document indexing and retrieval services."""

from __future__ import annotations

from typing import Any, Literal

from app.rag.document_chunker import (
    chunk_document_by_paragraphs,
    chunk_document_text,
)
from app.rag.document_embedder import embed_document_chunks
from app.rag.embedding_provider import EmbeddingProvider
from app.rag.vector_store import VectorStore
from app.schemas.document_index_result import (
    DocumentIndexResult,
)
from app.schemas.retrieval_result import RetrievalResult

ChunkingStrategy = Literal[
    "characters",
    "paragraphs",
]


class DocumentRetrieverError(ValueError):
    """Raised when document indexing or retrieval input is invalid."""


class DocumentRetriever:
    """Index documents and retrieve related Chunks."""

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store

    @property
    def embedding_provider(self) -> EmbeddingProvider:
        """Return the configured embedding provider."""

        return self._embedding_provider

    @property
    def vector_store(self) -> VectorStore:
        """Return the configured Vector Store."""

        return self._vector_store

    def index_document(
        self,
        *,
        document_id: str,
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        chunking_strategy: ChunkingStrategy = "paragraphs",
        metadata: dict[str, Any] | None = None,
    ) -> DocumentIndexResult:
        """Chunk, embed, and store one document."""

        if chunking_strategy == "characters":
            chunks = chunk_document_text(
                document_id=document_id,
                text=text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                metadata=metadata,
            )
        elif chunking_strategy == "paragraphs":
            chunks = chunk_document_by_paragraphs(
                document_id=document_id,
                text=text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                metadata=metadata,
            )
        else:
            raise DocumentRetrieverError(
                "unsupported chunking strategy: "
                f"{chunking_strategy}"
            )

        embedded_chunks = embed_document_chunks(
            chunks=chunks,
            provider=self.embedding_provider,
        )

        self.vector_store.add(embedded_chunks)

        return DocumentIndexResult(
            document_id=document_id,
            chunk_count=len(embedded_chunks),
            embedding_model=(
                self.embedding_provider.model_name
            ),
            embedding_dimensions=(
                self.embedding_provider.dimensions
            ),
        )

    def retrieve(
        self,
        *,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        """Retrieve the most similar indexed document Chunks."""

        if not query.strip():
            raise DocumentRetrieverError(
                "retrieval query must not be blank"
            )

        query_embedding = (
            self.embedding_provider.embed_text(query)
        )

        return self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
        )

    def clear(self) -> None:
        """Remove all indexed Chunks."""

        self.vector_store.clear()

    def indexed_chunk_count(self) -> int:
        """Return the number of indexed Chunks."""

        return self.vector_store.count()
