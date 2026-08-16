"""Contracts and identity helpers for text embedding caches."""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod

from app.schemas.document_embedding import TextEmbedding


class EmbeddingCacheError(RuntimeError):
    """Raised when an embedding cache cannot be accessed safely."""


class EmbeddingCache(ABC):
    """Persistent cache contract for exact text embeddings."""

    @abstractmethod
    def get(
        self,
        *,
        text: str,
        model_name: str,
        dimensions: int,
    ) -> TextEmbedding | None:
        """Return an exact cached embedding, or None on a cache miss."""

    @abstractmethod
    def put(
        self,
        *,
        text: str,
        embedding: TextEmbedding,
    ) -> None:
        """Persist an exact text embedding."""


def calculate_text_sha256(text: str) -> str:
    """Hash the exact UTF-8 bytes of text."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_embedding_cache_key(
    *,
    text_sha256: str,
    model_name: str,
    dimensions: int,
) -> str:
    """Build a deterministic key from an embedding's full identity."""

    identity = json.dumps(
        {
            "dimensions": dimensions,
            "model_name": model_name,
            "text_sha256": text_sha256,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()
