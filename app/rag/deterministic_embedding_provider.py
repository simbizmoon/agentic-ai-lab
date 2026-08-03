"""Deterministic embeddings for tests and local demonstrations."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence

from app.rag.embedding_provider import (
    EmbeddingProvider,
    EmbeddingProviderError,
)
from app.schemas.document_embedding import TextEmbedding


class DeterministicEmbeddingProvider(EmbeddingProvider):
    """Generate stable vectors without calling an external API."""

    def __init__(
        self,
        *,
        dimensions: int = 16,
        model_name: str = "deterministic-sha256-v1",
    ) -> None:
        if dimensions <= 0:
            raise EmbeddingProviderError(
                "dimensions must be greater than zero"
            )

        if not model_name.strip():
            raise EmbeddingProviderError(
                "model_name must not be blank"
            )

        self._dimensions = dimensions
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        """Return the deterministic model identifier."""

        return self._model_name

    @property
    def dimensions(self) -> int:
        """Return the configured vector dimensions."""

        return self._dimensions

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[TextEmbedding]:
        """Generate stable normalized vectors from text hashes."""

        embeddings: list[TextEmbedding] = []

        for text in texts:
            if not text.strip():
                raise EmbeddingProviderError(
                    "text to embed must not be blank"
                )

            vector = self._create_vector(text)

            embeddings.append(
                TextEmbedding(
                    model_name=self.model_name,
                    dimensions=self.dimensions,
                    vector=vector,
                )
            )

        return embeddings

    def _create_vector(self, text: str) -> list[float]:
        """Create a normalized deterministic vector."""

        values: list[float] = []
        counter = 0

        while len(values) < self.dimensions:
            payload = (
                f"{counter}:{text}"
            ).encode()
            digest = hashlib.sha256(payload).digest()

            for byte in digest:
                value = (byte / 127.5) - 1.0
                values.append(value)

                if len(values) == self.dimensions:
                    break

            counter += 1

        magnitude = math.sqrt(
            sum(value * value for value in values)
        )

        if magnitude == 0:
            raise EmbeddingProviderError(
                "generated embedding has zero magnitude"
            )

        return [
            value / magnitude
            for value in values
        ]
