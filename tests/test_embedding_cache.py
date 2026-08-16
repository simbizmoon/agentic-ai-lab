"""Tests for embedding cache identities and entry schemas."""

import hashlib

import pytest
from pydantic import ValidationError

from app.rag.embedding_cache import (
    build_embedding_cache_key,
    calculate_text_sha256,
)
from app.schemas.document_embedding import TextEmbedding
from app.schemas.embedding_cache_entry import EmbeddingCacheEntry


def test_text_digest_hashes_exact_utf8_bytes() -> None:
    text = "AIRA 임베딩"

    assert (
        calculate_text_sha256(text) == hashlib.sha256(text.encode("utf-8")).hexdigest()
    )
    assert calculate_text_sha256(text) != calculate_text_sha256(f"{text} ")


def test_cache_key_is_deterministic_and_uses_full_identity() -> None:
    arguments = {
        "text_sha256": calculate_text_sha256("same text"),
        "model_name": "model-a",
        "dimensions": 2,
    }

    first = build_embedding_cache_key(**arguments)

    assert first == build_embedding_cache_key(**arguments)
    assert first != build_embedding_cache_key(**{**arguments, "model_name": "model-b"})
    assert first != build_embedding_cache_key(**{**arguments, "dimensions": 3})


def test_entry_is_strict_versioned_and_frozen() -> None:
    digest = calculate_text_sha256("text")
    key = build_embedding_cache_key(
        text_sha256=digest,
        model_name="model",
        dimensions=2,
    )
    entry = EmbeddingCacheEntry(
        version=1,
        cache_key=key,
        text_sha256=digest,
        model_name="model",
        dimensions=2,
        embedding=TextEmbedding(
            model_name="model",
            dimensions=2,
            vector=[1.0, 0.0],
        ),
    )

    with pytest.raises(ValidationError):
        entry.dimensions = 3
    with pytest.raises(ValidationError):
        EmbeddingCacheEntry.model_validate(
            {
                **entry.model_dump(),
                "version": 2,
            }
        )
    with pytest.raises(ValidationError):
        EmbeddingCacheEntry.model_validate(
            {
                **entry.model_dump(),
                "unexpected": True,
            }
        )


def test_entry_rejects_embedding_identity_mismatch() -> None:
    digest = calculate_text_sha256("text")

    with pytest.raises(
        ValidationError,
        match="embedding model does not match",
    ):
        EmbeddingCacheEntry(
            version=1,
            cache_key="a" * 64,
            text_sha256=digest,
            model_name="model-a",
            dimensions=2,
            embedding=TextEmbedding(
                model_name="model-b",
                dimensions=2,
                vector=[1.0, 0.0],
            ),
        )
