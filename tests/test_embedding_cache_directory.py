"""Tests for persistent embedding cache directory resolution."""

from pathlib import Path

import pytest

from app.rag.embedding_cache_directory import (
    EmbeddingCacheConfigurationError,
    resolve_embedding_cache_directory,
)


def test_resolver_uses_absolute_xdg_cache_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", "/tmp/example")

    assert resolve_embedding_cache_directory() == Path("/tmp/example/aira/embeddings")


@pytest.mark.parametrize("value", [None, "", "   "])
def test_resolver_uses_home_cache_fallback(
    monkeypatch: pytest.MonkeyPatch,
    value: str | None,
) -> None:
    if value is None:
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    else:
        monkeypatch.setenv("XDG_CACHE_HOME", value)
    monkeypatch.setenv("HOME", "/tmp/test-home")

    assert resolve_embedding_cache_directory() == Path(
        "/tmp/test-home/.cache/aira/embeddings"
    )


def test_resolver_rejects_relative_xdg_cache_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", "relative/cache")

    with pytest.raises(
        EmbeddingCacheConfigurationError,
        match="must be an absolute path",
    ):
        resolve_embedding_cache_directory()
