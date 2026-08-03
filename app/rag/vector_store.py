"""Vector Store interfaces for document retrieval."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.schemas.document_embedding import (
    EmbeddedDocumentChunk,
    TextEmbedding,
)
from app.schemas.retrieval_result import RetrievalResult


class VectorStoreError(RuntimeError):
    """Raised when a Vector Store operation fails."""


class VectorStore(ABC):
    """Interface implemented by document Vector Stores."""

    @abstractmethod
    def add(
        self,
        items: Sequence[EmbeddedDocumentChunk],
    ) -> None:
        """Store embedded document Chunks."""

    @abstractmethod
    def search(
        self,
        *,
        query_embedding: TextEmbedding,
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        """Return the most similar stored Chunks."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all stored Chunks."""

    @abstractmethod
    def count(self) -> int:
        """Return the number of stored Chunks."""
