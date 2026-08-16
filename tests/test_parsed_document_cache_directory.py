from pathlib import Path

import pytest

from app.research.parsed_document_cache_directory import (
    ParsedDocumentCacheConfigurationError,
    resolve_parsed_document_cache_directory,
)


def test_absolute_xdg_cache_home_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", "/tmp/example")
    assert resolve_parsed_document_cache_directory() == Path(
        "/tmp/example/aira/parsed-documents"
    )


@pytest.mark.parametrize("value", [None, "", "   "])
def test_unset_or_blank_xdg_uses_home_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str | None
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    if value is None:
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    else:
        monkeypatch.setenv("XDG_CACHE_HOME", value)
    assert resolve_parsed_document_cache_directory() == (
        tmp_path / ".cache" / "aira" / "parsed-documents"
    )


def test_relative_xdg_cache_home_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", "relative/cache")
    with pytest.raises(ParsedDocumentCacheConfigurationError, match="absolute path"):
        resolve_parsed_document_cache_directory()
