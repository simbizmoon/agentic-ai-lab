"""Offline tests for safe file-backed vector-index snapshots."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.research.file_persistent_vector_index import (
    FilePersistentVectorIndex,
    PersistentVectorIndexCorruptError,
    PersistentVectorIndexStorageError,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.document_embedding import EmbeddedDocumentChunk, TextEmbedding
from app.schemas.persistent_vector_index import (
    PersistentVectorIndexContent,
    PersistentVectorIndexSnapshot,
)

NOW = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)


def _snapshot(*, generation: int = 1) -> PersistentVectorIndexSnapshot:
    text = "Persistent retrieval evidence."
    record = EmbeddedDocumentChunk(
        chunk=DocumentChunk(
            document_id="document-1",
            chunk_id="chunk-1",
            ordinal=0,
            text=text,
            start_char=0,
            end_char=len(text),
            metadata={"source_id": "source-1"},
        ),
        embedding=TextEmbedding(
            model_name="deterministic-v1",
            dimensions=2,
            vector=[1.0, 0.0],
        ),
    )
    return PersistentVectorIndexSnapshot.seal(
        PersistentVectorIndexContent(
            index_id="research-index",
            generation=generation,
            embedding_model="deterministic-v1",
            embedding_dimensions=2,
            created_at=NOW,
            updated_at=NOW,
            records=[record],
        )
    )


def test_missing_snapshot_returns_none(tmp_path: Path) -> None:
    store = FilePersistentVectorIndex(directory=tmp_path / "index")
    assert store.load() is None


def test_save_and_new_instance_restore_exact_snapshot(tmp_path: Path) -> None:
    directory = tmp_path / "index"
    first = FilePersistentVectorIndex(directory=directory)
    snapshot = _snapshot()
    first.save(snapshot)

    restored = FilePersistentVectorIndex(directory=directory).load()
    assert restored == snapshot
    assert restored is not snapshot


def test_directory_snapshot_and_lock_are_private(tmp_path: Path) -> None:
    store = FilePersistentVectorIndex(directory=tmp_path / "index")
    store.save(_snapshot())
    assert store.directory.stat().st_mode & 0o777 == 0o700
    assert store.snapshot_path.stat().st_mode & 0o777 == 0o600
    assert (store.directory / ".vector-index.lock").stat().st_mode & 0o777 == 0o600


def test_existing_directory_mode_is_normalized(tmp_path: Path) -> None:
    directory = tmp_path / "index"
    directory.mkdir(mode=0o777)
    directory.chmod(0o777)
    store = FilePersistentVectorIndex(directory=directory)
    assert store.directory.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize(
    "payload",
    [
        b"{broken",
        b'{"content":{},"content":{},"content_sha256":"x"}',
        json.dumps({"content": {}, "content_sha256": "f" * 64}).encode(),
    ],
)
def test_corrupt_snapshot_is_explicit_failure(tmp_path: Path, payload: bytes) -> None:
    store = FilePersistentVectorIndex(directory=tmp_path / "index")
    store.snapshot_path.write_bytes(payload)
    with pytest.raises(PersistentVectorIndexCorruptError, match="is corrupt"):
        store.load()


def test_invalid_utf8_is_explicit_corruption(tmp_path: Path) -> None:
    store = FilePersistentVectorIndex(directory=tmp_path / "index")
    store.snapshot_path.write_bytes(b"\xff\xfe")
    with pytest.raises(PersistentVectorIndexCorruptError, match="is corrupt"):
        store.load()


def test_tampered_valid_json_digest_is_explicit_corruption(tmp_path: Path) -> None:
    store = FilePersistentVectorIndex(directory=tmp_path / "index")
    store.save(_snapshot())
    payload = json.loads(store.snapshot_path.read_text(encoding="utf-8"))
    payload["content"]["generation"] = 2
    store.snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PersistentVectorIndexCorruptError, match="is corrupt"):
        store.load()


def test_save_rejects_snapshot_above_size_limit(tmp_path: Path) -> None:
    store = FilePersistentVectorIndex(
        directory=tmp_path / "index",
        maximum_snapshot_bytes=10,
    )
    with pytest.raises(PersistentVectorIndexStorageError, match="exceeds maximum size"):
        store.save(_snapshot())


def test_load_rejects_snapshot_above_read_limit(tmp_path: Path) -> None:
    directory = tmp_path / "index"
    writer = FilePersistentVectorIndex(directory=directory)
    writer.save(_snapshot())
    reader = FilePersistentVectorIndex(
        directory=directory,
        maximum_snapshot_bytes=10,
    )
    with pytest.raises(
        PersistentVectorIndexCorruptError,
        match="maximum readable size",
    ):
        reader.load()


def test_symlink_directory_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    directory = tmp_path / "index"
    try:
        directory.symlink_to(target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink unavailable: {error}")
    with pytest.raises(
        PersistentVectorIndexStorageError, match="must not be a symlink"
    ):
        FilePersistentVectorIndex(directory=directory)


def test_symlink_snapshot_is_rejected_without_touching_target(tmp_path: Path) -> None:
    store = FilePersistentVectorIndex(directory=tmp_path / "index")
    target = tmp_path / "target.json"
    target.write_text("unchanged", encoding="utf-8")
    try:
        store.snapshot_path.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlink unavailable: {error}")
    with pytest.raises(
        PersistentVectorIndexStorageError, match="must not be a symlink"
    ):
        store.load()
    assert target.read_text(encoding="utf-8") == "unchanged"


def test_symlink_lock_is_rejected(tmp_path: Path) -> None:
    store = FilePersistentVectorIndex(directory=tmp_path / "index")
    target = tmp_path / "target.lock"
    target.write_text("unchanged", encoding="utf-8")
    try:
        (store.directory / ".vector-index.lock").symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlink unavailable: {error}")
    with pytest.raises(PersistentVectorIndexStorageError, match="lock path is unsafe"):
        store.load()


def test_snapshot_directory_target_is_rejected(tmp_path: Path) -> None:
    store = FilePersistentVectorIndex(directory=tmp_path / "index")
    store.snapshot_path.mkdir()
    with pytest.raises(PersistentVectorIndexStorageError, match="regular file"):
        store.load()


def test_save_uses_exclusive_and_load_uses_shared_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[bool] = []
    original = FilePersistentVectorIndex._lock

    def recording(fd: int, *, exclusive: bool) -> None:
        observed.append(exclusive)
        original(fd, exclusive=exclusive)

    monkeypatch.setattr(FilePersistentVectorIndex, "_lock", staticmethod(recording))
    store = FilePersistentVectorIndex(directory=tmp_path / "index")
    store.save(_snapshot())
    store.load()
    assert observed == [True, False]


def test_save_uses_atomic_replace_and_file_and_directory_fsync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FilePersistentVectorIndex(directory=tmp_path / "index")
    original_replace = os.replace
    original_fsync = os.fsync
    replacements: list[tuple[Path, Path]] = []
    fsync_calls: list[int] = []

    def recording_replace(source: Path, target: Path) -> None:
        replacements.append((Path(source), Path(target)))
        original_replace(source, target)

    def recording_fsync(fd: int) -> None:
        fsync_calls.append(fd)
        original_fsync(fd)

    monkeypatch.setattr(
        "app.research.file_persistent_vector_index.os.replace",
        recording_replace,
    )
    monkeypatch.setattr(
        "app.research.file_persistent_vector_index.os.fsync",
        recording_fsync,
    )
    store.save(_snapshot())
    assert len(replacements) == 1
    assert replacements[0][1] == store.snapshot_path
    assert len(fsync_calls) == 2


def test_replace_failure_removes_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FilePersistentVectorIndex(directory=tmp_path / "index")

    def fail_replace(source: Path, target: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(
        "app.research.file_persistent_vector_index.os.replace",
        fail_replace,
    )
    with pytest.raises(PersistentVectorIndexStorageError, match="could not be written"):
        store.save(_snapshot())
    assert list(store.directory.glob(".vector-index.json.*.tmp")) == []
    assert not store.snapshot_path.exists()


def test_save_rejects_wrong_type(tmp_path: Path) -> None:
    store = FilePersistentVectorIndex(directory=tmp_path / "index")
    with pytest.raises(TypeError, match="must be PersistentVectorIndexSnapshot"):
        store.save(object())


@pytest.mark.parametrize("value", [0, -1, True])
def test_rejects_invalid_maximum_size(tmp_path: Path, value: object) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        FilePersistentVectorIndex(
            directory=tmp_path / "index",
            maximum_snapshot_bytes=value,
        )
