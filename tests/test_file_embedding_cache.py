"""Tests for safe persistent file embedding cache behavior."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.rag.embedding_cache import (
    EmbeddingCacheError,
    build_embedding_cache_key,
    calculate_text_sha256,
)
from app.rag.file_embedding_cache import FileEmbeddingCache
from app.schemas.document_embedding import TextEmbedding


def embedding(
    *,
    model_name: str = "model-a",
    dimensions: int = 2,
) -> TextEmbedding:
    return TextEmbedding(
        model_name=model_name,
        dimensions=dimensions,
        vector=[float(index) for index in range(dimensions)],
    )


def entry_path(
    cache: FileEmbeddingCache,
    *,
    text: str,
    model_name: str = "model-a",
    dimensions: int = 2,
) -> Path:
    digest = calculate_text_sha256(text)
    key = build_embedding_cache_key(
        text_sha256=digest,
        model_name=model_name,
        dimensions=dimensions,
    )
    return cache.directory / f"{key}.json"


def test_cache_directory_is_created_with_private_mode(tmp_path: Path) -> None:
    cache = FileEmbeddingCache(directory=tmp_path / "cache")

    assert cache.directory.stat().st_mode & 0o777 == 0o700


def test_existing_cache_directory_is_normalized_to_private_mode(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "cache"
    directory.mkdir(mode=0o777)
    directory.chmod(0o777)

    cache = FileEmbeddingCache(directory=directory)

    assert cache.directory.stat().st_mode & 0o777 == 0o700


def test_cache_directory_chmod_failure_is_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_chmod(path: Path, mode: int) -> None:
        raise OSError("chmod failed")

    monkeypatch.setattr("app.rag.file_embedding_cache.os.chmod", fail_chmod)

    with pytest.raises(
        EmbeddingCacheError,
        match="directory could not be prepared",
    ) as error:
        FileEmbeddingCache(directory=tmp_path / "cache")

    assert isinstance(error.value.__cause__, OSError)


def test_symlink_cache_directory_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    directory = tmp_path / "cache"
    try:
        directory.symlink_to(target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")

    with pytest.raises(EmbeddingCacheError, match="must not be a symlink"):
        FileEmbeddingCache(directory=directory)


def test_put_persists_and_second_cache_object_reads_entry(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "cache"
    first = FileEmbeddingCache(directory=directory)

    first.put(text="persistent text", embedding=embedding())
    second = FileEmbeddingCache(directory=directory)

    assert (
        second.get(
            text="persistent text",
            model_name="model-a",
            dimensions=2,
        )
        == embedding()
    )
    assert entry_path(first, text="persistent text").stat().st_mode & 0o777 == 0o600
    assert (first.directory / ".embedding-cache.lock").stat().st_mode & 0o777 == (0o600)


@pytest.mark.parametrize(
    "replacement",
    [
        "{broken",
        json.dumps({"version": 1}),
        '{"version":1,"version":1}',
    ],
)
def test_corrupt_entry_is_a_cache_miss(
    tmp_path: Path,
    replacement: str,
) -> None:
    cache = FileEmbeddingCache(directory=tmp_path / "cache")
    cache.put(text="text", embedding=embedding())
    entry_path(cache, text="text").write_text(
        replacement,
        encoding="utf-8",
    )

    assert (
        cache.get(
            text="text",
            model_name="model-a",
            dimensions=2,
        )
        is None
    )


def test_invalid_utf8_entry_is_a_cache_miss(tmp_path: Path) -> None:
    cache = FileEmbeddingCache(directory=tmp_path / "cache")
    cache.put(text="text", embedding=embedding())
    entry_path(cache, text="text").write_bytes(b"\xff\xfe")

    assert (
        cache.get(
            text="text",
            model_name="model-a",
            dimensions=2,
        )
        is None
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("cache_key", "f" * 64),
        ("text_sha256", "e" * 64),
        ("model_name", "model-b"),
        ("dimensions", 3),
    ],
)
def test_identity_mismatch_is_a_cache_miss(
    tmp_path: Path,
    field: str,
    value: str | int,
) -> None:
    cache = FileEmbeddingCache(directory=tmp_path / "cache")
    cache.put(text="text", embedding=embedding())
    path = entry_path(cache, text="text")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    if field == "model_name":
        payload["embedding"]["model_name"] = value
    if field == "dimensions":
        payload["embedding"] = {
            "model_name": "model-a",
            "dimensions": 3,
            "vector": [0.0, 1.0, 2.0],
        }
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert (
        cache.get(
            text="text",
            model_name="model-a",
            dimensions=2,
        )
        is None
    )


def test_model_dimensions_and_text_select_different_entries(
    tmp_path: Path,
) -> None:
    cache = FileEmbeddingCache(directory=tmp_path / "cache")
    cache.put(text="text", embedding=embedding())

    assert (
        cache.get(
            text="changed",
            model_name="model-a",
            dimensions=2,
        )
        is None
    )
    assert (
        cache.get(
            text="text",
            model_name="model-b",
            dimensions=2,
        )
        is None
    )
    assert (
        cache.get(
            text="text",
            model_name="model-a",
            dimensions=3,
        )
        is None
    )


def test_write_uses_replace_and_file_and_directory_fsync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = FileEmbeddingCache(directory=tmp_path / "cache")
    original_replace = os.replace
    original_fsync = os.fsync
    replacements: list[tuple[Path, Path]] = []
    fsync_calls: list[int] = []

    def recording_replace(source: Path, target: Path) -> None:
        replacements.append((Path(source), Path(target)))
        original_replace(source, target)

    def recording_fsync(file_descriptor: int) -> None:
        fsync_calls.append(file_descriptor)
        original_fsync(file_descriptor)

    monkeypatch.setattr(
        "app.rag.file_embedding_cache.os.replace",
        recording_replace,
    )
    monkeypatch.setattr(
        "app.rag.file_embedding_cache.os.fsync",
        recording_fsync,
    )

    cache.put(text="text", embedding=embedding())

    assert len(replacements) == 1
    assert replacements[0][0].parent == cache.directory
    assert replacements[0][1] == entry_path(cache, text="text")
    assert len(fsync_calls) == 2


def test_symlink_entry_is_rejected(
    tmp_path: Path,
) -> None:
    cache = FileEmbeddingCache(directory=tmp_path / "cache")
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    path = entry_path(cache, text="text")
    try:
        path.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")

    with pytest.raises(
        EmbeddingCacheError,
        match="must not be a symlink",
    ):
        cache.get(
            text="text",
            model_name="model-a",
            dimensions=2,
        )


def test_read_os_error_is_surfaced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = FileEmbeddingCache(directory=tmp_path / "cache")
    cache.put(text="text", embedding=embedding())

    def fail_read_text(self: Path, *, encoding: str) -> str:
        raise OSError("read failed")

    monkeypatch.setattr(Path, "read_text", fail_read_text)

    with pytest.raises(
        EmbeddingCacheError,
        match="could not be read",
    ) as error:
        cache.get(
            text="text",
            model_name="model-a",
            dimensions=2,
        )
    assert isinstance(error.value.__cause__, OSError)


def test_write_os_error_is_surfaced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = FileEmbeddingCache(directory=tmp_path / "cache")

    def fail_replace(source: Path, target: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(
        "app.rag.file_embedding_cache.os.replace",
        fail_replace,
    )

    with pytest.raises(
        EmbeddingCacheError,
        match="could not be written",
    ) as error:
        cache.put(text="text", embedding=embedding())
    assert isinstance(error.value.__cause__, OSError)


def test_oversized_entry_is_bounded(tmp_path: Path) -> None:
    cache = FileEmbeddingCache(
        directory=tmp_path / "cache",
        maximum_entry_bytes=10,
    )

    with pytest.raises(
        EmbeddingCacheError,
        match="exceeds maximum size",
    ):
        cache.put(text="text", embedding=embedding())


def test_blank_text_is_not_persisted(tmp_path: Path) -> None:
    cache = FileEmbeddingCache(directory=tmp_path / "cache")

    with pytest.raises(
        EmbeddingCacheError,
        match="must not be cached",
    ):
        cache.put(text=" ", embedding=embedding())
