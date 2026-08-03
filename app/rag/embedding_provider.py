"""Embedding provider interfaces for retrieval workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.schemas.document_embedding import TextEmbedding


class EmbeddingProviderError(RuntimeError):
    """Raised when text embedding generation fails."""


class EmbeddingProvider(ABC):
    """Interface implemented by text embedding providers."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the provider's embedding model identifier."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the number of values in each embedding."""

    @abstractmethod
    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[TextEmbedding]:
        """Generate one embedding for each supplied text."""

    def embed_text(self, text: str) -> TextEmbedding:
        """Generate an embedding for one text."""

        embeddings = self.embed_texts([text])

        if len(embeddings) != 1:
            raise EmbeddingProviderError(
                "provider returned an unexpected embedding count"
            )

        return embeddings[0]
