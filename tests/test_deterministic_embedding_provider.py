"""Tests for the deterministic embedding provider."""

import math

import pytest

from app.rag.deterministic_embedding_provider import (
    DeterministicEmbeddingProvider,
)
from app.rag.embedding_provider import (
    EmbeddingProviderError,
)


def test_provider_exposes_configuration() -> None:
    provider = DeterministicEmbeddingProvider(
        dimensions=8,
        model_name="test-deterministic-model",
    )

    assert provider.dimensions == 8
    assert provider.model_name == (
        "test-deterministic-model"
    )


def test_same_text_produces_same_embedding() -> None:
    provider = DeterministicEmbeddingProvider(
        dimensions=8,
    )

    first = provider.embed_text("same text")
    second = provider.embed_text("same text")

    assert first == second


def test_different_text_produces_different_embedding() -> None:
    provider = DeterministicEmbeddingProvider(
        dimensions=8,
    )

    first = provider.embed_text("first text")
    second = provider.embed_text("second text")

    assert first.vector != second.vector


def test_embedding_has_configured_dimensions() -> None:
    provider = DeterministicEmbeddingProvider(
        dimensions=12,
    )

    embedding = provider.embed_text("example text")

    assert embedding.dimensions == 12
    assert len(embedding.vector) == 12


def test_embedding_vector_is_normalized() -> None:
    provider = DeterministicEmbeddingProvider(
        dimensions=16,
    )

    embedding = provider.embed_text("normalized text")
    magnitude = math.sqrt(
        sum(
            value * value
            for value in embedding.vector
        )
    )

    assert magnitude == pytest.approx(1.0)


def test_embed_texts_preserves_input_order() -> None:
    provider = DeterministicEmbeddingProvider(
        dimensions=8,
    )
    texts = [
        "first text",
        "second text",
        "third text",
    ]

    embeddings = provider.embed_texts(texts)

    assert len(embeddings) == 3
    assert embeddings[0] == provider.embed_text(texts[0])
    assert embeddings[1] == provider.embed_text(texts[1])
    assert embeddings[2] == provider.embed_text(texts[2])


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "\n\t",
    ],
)
def test_provider_rejects_blank_text(text: str) -> None:
    provider = DeterministicEmbeddingProvider()

    with pytest.raises(
        EmbeddingProviderError,
        match="must not be blank",
    ):
        provider.embed_text(text)


@pytest.mark.parametrize(
    "dimensions",
    [
        0,
        -1,
    ],
)
def test_provider_rejects_invalid_dimensions(
    dimensions: int,
) -> None:
    with pytest.raises(
        EmbeddingProviderError,
        match="greater than zero",
    ):
        DeterministicEmbeddingProvider(
            dimensions=dimensions,
        )


def test_provider_rejects_blank_model_name() -> None:
    with pytest.raises(
        EmbeddingProviderError,
        match="model_name must not be blank",
    ):
        DeterministicEmbeddingProvider(
            model_name="   ",
        )
