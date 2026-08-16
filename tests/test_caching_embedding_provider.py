"""Tests for the caching embedding provider decorator."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from app.rag.caching_embedding_provider import CachingEmbeddingProvider
from app.rag.embedding_provider import (
    EmbeddingProvider,
    EmbeddingProviderError,
)
from app.rag.file_embedding_cache import FileEmbeddingCache
from app.schemas.document_embedding import TextEmbedding


class RecordingEmbeddingProvider(EmbeddingProvider):
    """Generate deterministic vectors and record requested batches."""

    def __init__(
        self,
        *,
        model_name: str = "recording-model",
        dimensions: int = 2,
    ) -> None:
        self._model_name = model_name
        self._dimensions = dimensions
        self.calls: list[list[str]] = []

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[TextEmbedding]:
        normalized = list(texts)
        self.calls.append(normalized)
        for text in normalized:
            if not isinstance(text, str):
                raise EmbeddingProviderError("text to embed must be a string")
            if not text.strip():
                raise EmbeddingProviderError("text to embed must not be blank")
        return [
            TextEmbedding(
                model_name=self.model_name,
                dimensions=self.dimensions,
                vector=[
                    float(len(text)),
                    *[float(index) for _ in range(self.dimensions - 1)],
                ],
            )
            for index, text in enumerate(normalized)
        ]


def caching_provider(
    tmp_path: Path,
    provider: RecordingEmbeddingProvider,
) -> CachingEmbeddingProvider:
    return CachingEmbeddingProvider(
        provider=provider,
        cache=FileEmbeddingCache(directory=tmp_path / "cache"),
    )


def test_miss_calls_provider_and_persists_for_new_instance(
    tmp_path: Path,
) -> None:
    first_provider = RecordingEmbeddingProvider()
    first = caching_provider(tmp_path, first_provider)

    expected = first.embed_text("persistent text")
    second_provider = RecordingEmbeddingProvider()
    second = caching_provider(tmp_path, second_provider)

    assert second.embed_text("persistent text") == expected
    assert first_provider.calls == [["persistent text"]]
    assert second_provider.calls == []


def test_repeated_identical_batch_hits_persistent_cache(
    tmp_path: Path,
) -> None:
    texts = [
        "Question: How does AIRA cache embeddings?",
        "First candidate paragraph.",
        "Second candidate paragraph.",
    ]
    first_provider = RecordingEmbeddingProvider()
    first = caching_provider(tmp_path, first_provider)

    expected = first.embed_texts(texts)
    second_provider = RecordingEmbeddingProvider()
    second = caching_provider(tmp_path, second_provider)

    assert second.embed_texts(texts) == expected
    assert first_provider.calls == [texts]
    assert second_provider.calls == []


def test_standalone_local_entry_is_reused_by_integrated_provider(
    tmp_path: Path,
) -> None:
    standalone_provider = RecordingEmbeddingProvider()
    standalone = caching_provider(tmp_path, standalone_provider)
    texts = ["Shared query", "Shared local paragraph"]

    expected = standalone.embed_texts(texts)
    integrated_provider = RecordingEmbeddingProvider()
    integrated = caching_provider(tmp_path, integrated_provider)

    assert integrated.embed_texts(texts) == expected
    assert standalone_provider.calls == [texts]
    assert integrated_provider.calls == []


def test_integrated_web_entry_is_reused_by_integrated_local_provider(
    tmp_path: Path,
) -> None:
    web_provider = RecordingEmbeddingProvider()
    integrated_web = caching_provider(tmp_path, web_provider)
    shared_text = "Evidence text shared across source universes."

    expected = integrated_web.embed_text(shared_text)
    local_provider = RecordingEmbeddingProvider()
    integrated_local = caching_provider(tmp_path, local_provider)

    assert integrated_local.embed_text(shared_text) == expected
    assert web_provider.calls == [[shared_text]]
    assert local_provider.calls == []


def test_mixed_hit_and_miss_batch_preserves_order(
    tmp_path: Path,
) -> None:
    provider = RecordingEmbeddingProvider()
    cached = caching_provider(tmp_path, provider)
    first = cached.embed_text("cached")
    provider.calls.clear()

    results = cached.embed_texts(["new", "cached", "other"])

    assert provider.calls == [["new", "other"]]
    assert results[0].vector == [3.0, 0.0]
    assert results[1] == first
    assert results[2].vector == [5.0, 1.0]


def test_duplicate_text_is_embedded_only_once(
    tmp_path: Path,
) -> None:
    provider = RecordingEmbeddingProvider()
    cached = caching_provider(tmp_path, provider)

    results = cached.embed_texts(["same", "same", "different", "same"])

    assert provider.calls == [["same", "different"]]
    assert results[0] == results[1] == results[3]
    assert results[0] is not results[1]


@pytest.mark.parametrize(
    ("model_name", "dimensions"),
    [
        ("changed-model", 2),
        ("recording-model", 3),
    ],
)
def test_provider_identity_change_causes_miss(
    tmp_path: Path,
    model_name: str,
    dimensions: int,
) -> None:
    original = RecordingEmbeddingProvider()
    caching_provider(tmp_path, original).embed_text("text")
    changed = RecordingEmbeddingProvider(
        model_name=model_name,
        dimensions=dimensions,
    )

    CachingEmbeddingProvider(
        provider=changed,
        cache=FileEmbeddingCache(directory=tmp_path / "cache"),
    ).embed_text("text")

    assert changed.calls == [["text"]]


def test_changed_text_causes_miss(tmp_path: Path) -> None:
    provider = RecordingEmbeddingProvider()
    cached = caching_provider(tmp_path, provider)
    cached.embed_text("first")
    provider.calls.clear()

    cached.embed_text("second")

    assert provider.calls == [["second"]]


def test_properties_delegate_to_provider(tmp_path: Path) -> None:
    provider = RecordingEmbeddingProvider(
        model_name="delegated",
        dimensions=2,
    )
    cached = caching_provider(tmp_path, provider)

    assert cached.model_name == "delegated"
    assert cached.dimensions == 2


@pytest.mark.parametrize("blank", ["", " ", "\n\t"])
def test_blank_text_delegates_validation_without_cache_write(
    tmp_path: Path,
    blank: str,
) -> None:
    provider = RecordingEmbeddingProvider()
    cached = caching_provider(tmp_path, provider)

    with pytest.raises(
        EmbeddingProviderError,
        match="must not be blank",
    ):
        cached.embed_text(blank)

    assert provider.calls == [[blank]]
    assert list((tmp_path / "cache").glob("*.json")) == []
