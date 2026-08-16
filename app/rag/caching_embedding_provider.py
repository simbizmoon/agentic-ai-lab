"""Embedding provider decorator backed by an exact persistent cache."""

from __future__ import annotations

from collections.abc import Sequence

from app.rag.embedding_cache import EmbeddingCache
from app.rag.embedding_provider import (
    EmbeddingProvider,
    EmbeddingProviderError,
)
from app.schemas.document_embedding import TextEmbedding


class CachingEmbeddingProvider(EmbeddingProvider):
    """Avoid repeated provider work for identical embedding identities."""

    def __init__(
        self,
        *,
        provider: EmbeddingProvider,
        cache: EmbeddingCache,
    ) -> None:
        if not isinstance(provider, EmbeddingProvider):
            raise TypeError("provider must be an EmbeddingProvider")
        if not isinstance(cache, EmbeddingCache):
            raise TypeError("cache must be an EmbeddingCache")
        self._provider = provider
        self._cache = cache

    @property
    def model_name(self) -> str:
        """Delegate the configured embedding model name."""

        return self._provider.model_name

    @property
    def dimensions(self) -> int:
        """Delegate the configured embedding dimensions."""

        return self._provider.dimensions

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[TextEmbedding]:
        """Return ordered embeddings while batching unique cache misses."""

        normalized_texts = list(texts)
        if not normalized_texts:
            return self._provider.embed_texts(normalized_texts)

        if any(
            not isinstance(text, str) or not text.strip() for text in normalized_texts
        ):
            return self._provider.embed_texts(normalized_texts)

        embeddings_by_text: dict[str, TextEmbedding] = {}
        missing_texts: list[str] = []
        for text in dict.fromkeys(normalized_texts):
            cached = self._cache.get(
                text=text,
                model_name=self.model_name,
                dimensions=self.dimensions,
            )
            if cached is None:
                missing_texts.append(text)
            else:
                embeddings_by_text[text] = cached

        if missing_texts:
            generated = self._provider.embed_texts(missing_texts)
            if len(generated) != len(missing_texts):
                raise EmbeddingProviderError(
                    "provider returned an unexpected embedding count"
                )
            for text, embedding in zip(
                missing_texts,
                generated,
                strict=True,
            ):
                if not isinstance(embedding, TextEmbedding):
                    raise EmbeddingProviderError(
                        "provider returned an invalid embedding"
                    )
                if (
                    embedding.model_name != self.model_name
                    or embedding.dimensions != self.dimensions
                ):
                    raise EmbeddingProviderError(
                        "provider embedding identity did not match configuration"
                    )
                self._cache.put(text=text, embedding=embedding)
                embeddings_by_text[text] = embedding

        return [
            embeddings_by_text[text].model_copy(deep=True) for text in normalized_texts
        ]
