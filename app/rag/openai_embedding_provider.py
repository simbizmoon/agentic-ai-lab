"""OpenAI embedding provider for semantic document retrieval."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, Protocol

from app.rag.embedding_provider import (
    EmbeddingProvider,
    EmbeddingProviderError,
)
from app.schemas.document_embedding import TextEmbedding


class EmbeddingsAPI(Protocol):
    """Minimal OpenAI Embeddings API interface."""

    def create(self, **kwargs: Any) -> object:
        """Create embeddings for supplied text."""


class OpenAIEmbeddingClient(Protocol):
    """Minimal OpenAI client interface required by this provider."""

    embeddings: EmbeddingsAPI


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Generate semantic text embeddings through the OpenAI API."""

    def __init__(
        self,
        *,
        client: OpenAIEmbeddingClient,
        model_name: str = "text-embedding-3-small",
        dimensions: int = 1536,
    ) -> None:
        if not model_name.strip():
            raise EmbeddingProviderError(
                "model_name must not be blank"
            )

        if dimensions <= 0:
            raise EmbeddingProviderError(
                "dimensions must be greater than zero"
            )

        self._client = client
        self._model_name = model_name
        self._dimensions = dimensions

    @property
    def model_name(self) -> str:
        """Return the configured OpenAI embedding model."""

        return self._model_name

    @property
    def dimensions(self) -> int:
        """Return the configured embedding dimensions."""

        return self._dimensions

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[TextEmbedding]:
        """Generate one OpenAI embedding for each supplied text."""

        normalized_texts = list(texts)

        if not normalized_texts:
            return []

        for text in normalized_texts:
            if not isinstance(text, str):
                raise EmbeddingProviderError(
                    "text to embed must be a string"
                )

            if not text.strip():
                raise EmbeddingProviderError(
                    "text to embed must not be blank"
                )

        try:
            response = self._client.embeddings.create(
                model=self.model_name,
                input=normalized_texts,
                dimensions=self.dimensions,
                encoding_format="float",
            )
        except Exception as exc:
            raise EmbeddingProviderError(
                "OpenAI embedding request failed"
            ) from exc

        data = getattr(response, "data", None)

        if not isinstance(data, list):
            raise EmbeddingProviderError(
                "OpenAI embedding response did not contain data"
            )

        if len(data) != len(normalized_texts):
            raise EmbeddingProviderError(
                "OpenAI returned an unexpected embedding count"
            )

        ordered_items = sorted(
            data,
            key=self._embedding_index,
        )

        embeddings: list[TextEmbedding] = []

        for expected_index, item in enumerate(ordered_items):
            actual_index = self._embedding_index(item)

            if actual_index != expected_index:
                raise EmbeddingProviderError(
                    "OpenAI embedding indexes were invalid"
                )

            vector = getattr(item, "embedding", None)

            if not isinstance(vector, list):
                raise EmbeddingProviderError(
                    "OpenAI embedding item did not contain a vector"
                )

            if len(vector) != self.dimensions:
                raise EmbeddingProviderError(
                    "OpenAI embedding dimensions did not match "
                    "the provider configuration"
                )

            if not all(
                isinstance(value, int | float)
                and math.isfinite(value)
                for value in vector
            ):
                raise EmbeddingProviderError(
                    "OpenAI embedding vector contained invalid values"
                )

            embeddings.append(
                TextEmbedding(
                    model_name=self.model_name,
                    dimensions=self.dimensions,
                    vector=[
                        float(value)
                        for value in vector
                    ],
                )
            )

        return embeddings

    @staticmethod
    def _embedding_index(item: object) -> int:
        """Extract a valid embedding item index."""

        index = getattr(item, "index", None)

        if not isinstance(index, int) or index < 0:
            raise EmbeddingProviderError(
                "OpenAI embedding item had an invalid index"
            )

        return index
