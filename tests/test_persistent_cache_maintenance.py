from __future__ import annotations

import multiprocessing
import os
import stat
import threading
from pathlib import Path
from typing import Any, Self

import pytest
from pydantic import ValidationError

from app.persistent_cache_maintenance import (
    PersistentCacheInventoryError,
    PersistentCacheMaintenanceService,
    PersistentCachePruneError,
)
from app.rag.embedding_cache import build_embedding_cache_key, calculate_text_sha256
from app.rag.file_embedding_cache import FileEmbeddingCache
from app.research.file_parsed_document_cache import FileParsedDocumentCache
from app.research.parsed_document_cache import (
    ParsedDocumentCacheIdentity,
    build_local_document_parser_identity,
)
from app.schemas.document_embedding import TextEmbedding
from app.schemas.parsed_local_document import ParsedLocalDocument
from app.schemas.persistent_cache_status import (
    CacheEntryInfo,
    CacheKind,
    CachePruneCandidate,
    CachePruneExecutionItem,
    CachePruneOutcome,
    CachePrunePlan,
    CachePruneResult,
    CacheStatus,
)
from app.schemas.research_source_document import ResearchSourceContentType


def _embedding_key(text: str = "cache text") -> str:
    return build_embedding_cache_key(
        text_sha256=calculate_text_sha256(text),
        model_name="model-a",
        dimensions=2,
    )


def _put_embedding(directory: Path, text: str = "cache text") -> Path:
    cache = FileEmbeddingCache(directory=directory)
    cache.put(
        text=text,
        embedding=TextEmbedding(
            model_name="model-a", dimensions=2, vector=[0.25, 0.75]
        ),
    )
    return directory / f"{_embedding_key(text)}.json"


def _parsed_identity(raw: bytes = b"parsed text") -> ParsedDocumentCacheIdentity:
    import hashlib

    return ParsedDocumentCacheIdentity(
        raw_content_sha256=hashlib.sha256(raw).hexdigest(),
        raw_file_size_bytes=len(raw),
        parser=build_local_document_parser_identity(".txt"),
    )


def _put_parsed(directory: Path, raw: bytes = b"parsed text") -> Path:
    identity = _parsed_identity(raw)
    FileParsedDocumentCache(directory=directory).put(
        identity,
        ParsedLocalDocument(
            content=raw.decode(),
            content_type=ResearchSourceContentType.TEXT,
        ),
    )
    return directory / f"{identity.cache_key}.json"


def _status(kind: CacheKind, directory: Path) -> CacheStatus:
    return PersistentCacheMaintenanceService().status(
        cache_kind=kind, directory=directory
    )


def _synthetic_status(
    *,
    kind: CacheKind = CacheKind.EMBEDDING,
    entries: tuple[tuple[str, int, int], ...] = (),
    corrupt_bytes: int = 0,
    lock_bytes: int = 0,
    temporary_bytes: int = 0,
    unknown_bytes: int = 0,
) -> CacheStatus:
    entry_models = tuple(
        CacheEntryInfo(
            cache_kind=kind,
            filename=f"{key}.json",
            entry_key=key,
            size_bytes=size,
            mtime_ns=mtime,
        )
        for key, size, mtime in entries
    )
    mtimes = [entry.mtime_ns for entry in entry_models]
    return CacheStatus(
        cache_kind=kind,
        directory=Path("/tmp/cache"),
        directory_exists=True,
        entries=entry_models,
        valid_entry_count=len(entry_models),
        valid_entry_bytes=sum(entry.size_bytes for entry in entry_models),
        corrupt_entry_count=int(corrupt_bytes > 0),
        corrupt_entry_bytes=corrupt_bytes,
        lock_file_count=int(lock_bytes > 0),
        lock_file_bytes=lock_bytes,
        temporary_file_count=int(temporary_bytes > 0),
        temporary_file_bytes=temporary_bytes,
        unknown_target_count=int(unknown_bytes > 0),
        unknown_target_bytes=unknown_bytes,
        oldest_valid_entry_mtime_ns=min(mtimes, default=None),
        newest_valid_entry_mtime_ns=max(mtimes, default=None),
    )


def _plan(status: CacheStatus, target: int) -> CachePrunePlan:
    return PersistentCacheMaintenanceService.plan_prune(
        status=status, target_entry_bytes_total=target
    )


def _execute(plan: CachePrunePlan) -> CachePruneResult:
    return PersistentCacheMaintenanceService().execute_prune(plan=plan)


def _hold_parsed_lock(
    directory: Path,
    cache_key: str,
    ready: Any,
    release: Any,
) -> None:
    with FileParsedDocumentCache.exclusive_maintenance_entry_lock(
        directory=directory,
        cache_key=cache_key,
    ):
        ready.set()
        release.wait(timeout=10)


@pytest.mark.parametrize("kind", list(CacheKind))
def test_nonexistent_directory_is_empty_without_creation(
    tmp_path: Path, kind: CacheKind
) -> None:
    directory = tmp_path / "missing"
    status_result = _status(kind, directory)
    assert not status_result.directory_exists
    assert status_result.valid_entry_count == 0
    assert not directory.exists()


@pytest.mark.parametrize("kind", list(CacheKind))
def test_empty_directory_is_reported_without_mutation(
    tmp_path: Path, kind: CacheKind
) -> None:
    directory = tmp_path / "cache"
    directory.mkdir(mode=0o755)
    before_mode = stat.S_IMODE(directory.stat().st_mode)
    status_result = _status(kind, directory)
    assert status_result.directory_exists
    assert status_result.valid_entry_count == 0
    assert stat.S_IMODE(directory.stat().st_mode) == before_mode


def test_inventory_models_are_strict_and_frozen(tmp_path: Path) -> None:
    status_result = _status(CacheKind.EMBEDDING, tmp_path / "missing")
    with pytest.raises(ValidationError):
        CacheStatus.model_validate(
            {
                **status_result.model_dump(),
                "valid_entry_count": "0",
            }
        )
    with pytest.raises(ValidationError):
        status_result.valid_entry_count = 1


def test_embedding_entry_and_global_lock_are_accounted(tmp_path: Path) -> None:
    directory = tmp_path / "embedding"
    entry = _put_embedding(directory)
    lock = directory / ".embedding-cache.lock"
    status_result = _status(CacheKind.EMBEDDING, directory)
    assert status_result.valid_entry_count == 1
    assert status_result.valid_entry_bytes == entry.stat().st_size
    assert status_result.lock_file_count == 1
    assert status_result.lock_file_bytes == lock.stat().st_size
    assert status_result.entries[0].entry_key == _embedding_key()


def test_parsed_entry_and_per_key_lock_are_accounted(tmp_path: Path) -> None:
    directory = tmp_path / "parsed"
    entry = _put_parsed(directory)
    identity = _parsed_identity()
    lock = directory / f".{identity.cache_key}.lock"
    status_result = _status(CacheKind.PARSED, directory)
    assert status_result.valid_entry_count == 1
    assert status_result.valid_entry_bytes == entry.stat().st_size
    assert status_result.lock_file_count == 1
    assert status_result.lock_file_bytes == lock.stat().st_size


@pytest.mark.parametrize("kind", list(CacheKind))
def test_recognized_temp_and_unknown_regular_file_are_separate(
    tmp_path: Path, kind: CacheKind
) -> None:
    directory = tmp_path / "cache"
    directory.mkdir()
    key = "a" * 64
    temporary = directory / f".{key}.json.random.tmp"
    unknown = directory / "notes.txt"
    temporary.write_bytes(b"temp")
    unknown.write_bytes(b"unknown")
    status_result = _status(kind, directory)
    assert status_result.temporary_file_count == 1
    assert status_result.temporary_file_bytes == 4
    assert status_result.unknown_target_count == 1
    assert status_result.unknown_target_bytes == 7


@pytest.mark.parametrize("kind", list(CacheKind))
def test_corrupt_json_is_reported_separately(tmp_path: Path, kind: CacheKind) -> None:
    directory = tmp_path / "cache"
    directory.mkdir()
    corrupt = directory / f"{'b' * 64}.json"
    corrupt.write_text("{not-json", encoding="utf-8")
    status_result = _status(kind, directory)
    assert status_result.valid_entry_count == 0
    assert status_result.corrupt_entry_count == 1
    assert status_result.corrupt_entry_bytes == corrupt.stat().st_size
    assert status_result.unknown_target_count == 0


def test_valid_entry_requires_filename_to_match_payload_identity(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "cache"
    entry = _put_embedding(directory)
    entry.rename(directory / f"{'c' * 64}.json")
    status_result = _status(CacheKind.EMBEDDING, directory)
    assert status_result.valid_entry_count == 0
    assert status_result.corrupt_entry_count == 1


def test_oldest_newest_and_entry_order_are_deterministic(tmp_path: Path) -> None:
    directory = tmp_path / "cache"
    newer = _put_embedding(directory, "newer")
    older = _put_embedding(directory, "older")
    os.utime(older, ns=(100, 100))
    os.utime(newer, ns=(200, 200))
    status_result = _status(CacheKind.EMBEDDING, directory)
    assert [entry.mtime_ns for entry in status_result.entries] == [100, 200]
    assert status_result.oldest_valid_entry_mtime_ns == 100
    assert status_result.newest_valid_entry_mtime_ns == 200


def test_status_does_not_change_content_mtime_mode_or_delete(tmp_path: Path) -> None:
    directory = tmp_path / "cache"
    entry = _put_embedding(directory)
    unknown = directory / "keep.me"
    unknown.write_text("unchanged", encoding="utf-8")
    before = {
        path.name: (
            path.read_bytes(),
            path.stat().st_mtime_ns,
            stat.S_IMODE(path.stat().st_mode),
        )
        for path in directory.iterdir()
    }
    _status(CacheKind.EMBEDDING, directory)
    after = {
        path.name: (
            path.read_bytes(),
            path.stat().st_mtime_ns,
            stat.S_IMODE(path.stat().st_mode),
        )
        for path in directory.iterdir()
    }
    assert entry.exists()
    assert before == after


@pytest.mark.parametrize("kind", list(CacheKind))
def test_symlink_and_nonregular_targets_are_explicit_errors(
    tmp_path: Path, kind: CacheKind
) -> None:
    directory = tmp_path / "cache"
    directory.mkdir()
    target = tmp_path / "target"
    target.write_text("target", encoding="utf-8")
    link = directory / "link"
    try:
        link.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")
    with pytest.raises(PersistentCacheInventoryError, match="non-regular"):
        _status(kind, directory)


def test_cache_directory_symlink_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    directory = tmp_path / "cache"
    try:
        directory.symlink_to(target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")
    with pytest.raises(PersistentCacheInventoryError, match="must not be a symlink"):
        _status(CacheKind.EMBEDDING, directory)


def test_nested_directory_is_an_explicit_unsafe_target(tmp_path: Path) -> None:
    directory = tmp_path / "cache"
    directory.mkdir()
    (directory / "nested").mkdir()
    with pytest.raises(PersistentCacheInventoryError, match="non-regular"):
        _status(CacheKind.PARSED, directory)


def test_embedding_and_parsed_patterns_remain_isolated(tmp_path: Path) -> None:
    embedding_directory = tmp_path / "embedding"
    parsed_directory = tmp_path / "parsed"
    _put_embedding(embedding_directory)
    _put_parsed(parsed_directory)
    embedding_status = _status(CacheKind.EMBEDDING, embedding_directory)
    parsed_status = _status(CacheKind.PARSED, parsed_directory)
    assert embedding_status.cache_kind is CacheKind.EMBEDDING
    assert parsed_status.cache_kind is CacheKind.PARSED
    assert embedding_status.entries[0].entry_key != parsed_status.entries[0].entry_key


def test_concurrent_disappearance_during_stat_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "cache"
    directory.mkdir()
    path = directory / "unknown"
    path.write_text("value", encoding="utf-8")
    original_scandir = os.scandir

    class VanishingEntry:
        name = "unknown"

        @staticmethod
        def stat(*, follow_symlinks: bool) -> os.stat_result:
            raise FileNotFoundError

    VanishingEntry.path = str(path)

    class Entries:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def __iter__(self):  # type: ignore[no-untyped-def]
            return iter([VanishingEntry()])

    monkeypatch.setattr(os, "scandir", lambda value: Entries())
    try:
        status_result = _status(CacheKind.EMBEDDING, directory)
    finally:
        monkeypatch.setattr(os, "scandir", original_scandir)
    assert status_result.unknown_target_count == 0


def test_concurrent_disappearance_before_entry_open_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "cache"
    _put_embedding(directory)
    original_open = os.open

    def disappearing_open(path: Path, flags: int) -> int:
        if Path(path).suffix == ".json":
            raise FileNotFoundError
        return original_open(path, flags)

    monkeypatch.setattr("app.persistent_cache_maintenance.os.open", disappearing_open)
    status_result = _status(CacheKind.EMBEDDING, directory)
    assert status_result.valid_entry_count == 0
    assert status_result.corrupt_entry_count == 0


def test_genuine_target_stat_failure_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "cache"
    directory.mkdir()

    class BrokenEntry:
        name = "broken"
        path = str(directory / "broken")

        @staticmethod
        def stat(*, follow_symlinks: bool) -> os.stat_result:
            raise PermissionError("denied")

    class Entries:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def __iter__(self):  # type: ignore[no-untyped-def]
            return iter([BrokenEntry()])

    monkeypatch.setattr(os, "scandir", lambda value: Entries())
    with pytest.raises(PersistentCacheInventoryError, match="could not be inspected"):
        _status(CacheKind.PARSED, directory)


def test_genuine_entry_read_failure_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "cache"
    _put_embedding(directory)

    def fail_read(descriptor: int, size: int) -> bytes:
        raise OSError("read failed")

    monkeypatch.setattr("app.persistent_cache_maintenance.os.read", fail_read)
    with pytest.raises(PersistentCacheInventoryError, match="could not be read"):
        _status(CacheKind.EMBEDDING, directory)


def test_empty_status_produces_empty_plan() -> None:
    plan = _plan(_synthetic_status(), 0)
    assert plan.selected_entry_count == 0
    assert plan.expected_remaining_valid_entry_count == 0
    assert plan.expected_remaining_valid_entry_bytes == 0


@pytest.mark.parametrize("target", [31, 30])
def test_current_bytes_at_or_below_target_produce_empty_plan(target: int) -> None:
    status_result = _synthetic_status(entries=(("a" * 64, 30, 1),))
    plan = _plan(status_result, target)
    assert plan.candidates == ()
    assert plan.expected_remaining_valid_entry_bytes == 30


def test_target_zero_selects_all_valid_entries() -> None:
    status_result = _synthetic_status(entries=(("a" * 64, 10, 1), ("b" * 64, 20, 2)))
    plan = _plan(status_result, 0)
    assert [candidate.entry_key for candidate in plan.candidates] == [
        "a" * 64,
        "b" * 64,
    ]
    assert plan.selected_entry_bytes == 30
    assert plan.expected_remaining_valid_entry_bytes == 0


def test_one_oldest_entry_is_selected_to_reach_target() -> None:
    status_result = _synthetic_status(entries=(("a" * 64, 10, 1), ("b" * 64, 20, 2)))
    plan = _plan(status_result, 20)
    assert plan.selected_entry_count == 1
    assert plan.candidates[0].entry_key == "a" * 64
    assert plan.expected_remaining_valid_entry_count == 1
    assert plan.expected_remaining_valid_entry_bytes == 20


def test_multiple_indivisible_entries_can_reduce_below_target() -> None:
    status_result = _synthetic_status(
        entries=(
            ("a" * 64, 7, 1),
            ("b" * 64, 8, 2),
            ("c" * 64, 20, 3),
        )
    )
    plan = _plan(status_result, 25)
    assert plan.selected_entry_count == 2
    assert plan.selected_entry_bytes == 15
    assert plan.expected_remaining_valid_entry_bytes == 20


def test_equal_mtime_uses_entry_key_as_tie_breaker() -> None:
    status_result = _synthetic_status(entries=(("b" * 64, 10, 1), ("a" * 64, 10, 1)))
    plan = _plan(status_result, 10)
    assert [candidate.entry_key for candidate in plan.candidates] == ["a" * 64]


def test_nonvalid_categories_do_not_affect_target_or_candidates() -> None:
    status_result = _synthetic_status(
        entries=(("a" * 64, 10, 1),),
        corrupt_bytes=100,
        lock_bytes=200,
        temporary_bytes=300,
        unknown_bytes=400,
    )
    plan = _plan(status_result, 10)
    assert plan.observed_valid_entry_bytes == 10
    assert plan.candidates == ()


@pytest.mark.parametrize("kind", list(CacheKind))
def test_plan_preserves_cache_kind(kind: CacheKind) -> None:
    status_result = _synthetic_status(kind=kind, entries=(("a" * 64, 10, 1),))
    plan = _plan(status_result, 0)
    assert plan.cache_kind is kind
    assert plan.candidates[0].cache_kind is kind


def test_planning_is_deterministic_and_does_not_mutate_status() -> None:
    status_result = _synthetic_status(entries=(("b" * 64, 20, 2), ("a" * 64, 10, 1)))
    before = status_result.model_dump_json()
    first = _plan(status_result, 20)
    second = _plan(status_result, 20)
    assert first == second
    assert status_result.model_dump_json() == before


def test_prune_plan_models_are_strict_and_frozen() -> None:
    candidate = CachePruneCandidate(
        cache_kind=CacheKind.EMBEDDING,
        filename=("a" * 64) + ".json",
        entry_key="a" * 64,
        size_bytes=10,
        mtime_ns=1,
    )
    plan = _plan(_synthetic_status(entries=(("a" * 64, 10, 1),)), 0)
    with pytest.raises(ValidationError):
        CachePruneCandidate.model_validate(
            {**candidate.model_dump(), "size_bytes": "10"}
        )
    with pytest.raises(ValidationError):
        plan.selected_entry_count = 2


@pytest.mark.parametrize("target", [-1, True, "0"])
def test_invalid_target_is_rejected(target: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        PersistentCacheMaintenanceService.plan_prune(
            status=_synthetic_status(),
            target_entry_bytes_total=target,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("selected_entry_count", 2, "count"),
        ("selected_entry_bytes", 9, "bytes"),
        ("expected_remaining_valid_entry_count", 1, "count"),
        ("expected_remaining_valid_entry_bytes", 1, "bytes"),
    ],
)
def test_plan_rejects_inconsistent_aggregates(
    field: str, value: int, message: str
) -> None:
    plan = _plan(_synthetic_status(entries=(("a" * 64, 10, 1),)), 0)
    payload = plan.model_dump()
    payload[field] = value
    with pytest.raises(ValidationError, match=message):
        CachePrunePlan.model_validate(payload)


def test_plan_rejects_insufficient_or_excessive_selection() -> None:
    status_result = _synthetic_status(entries=(("a" * 64, 10, 1), ("b" * 64, 10, 2)))
    valid_plan = _plan(status_result, 10)
    missing = valid_plan.model_dump()
    missing.update(
        selected_entry_count=0,
        selected_entry_bytes=0,
        expected_remaining_valid_entry_count=2,
        expected_remaining_valid_entry_bytes=20,
        candidates=(),
    )
    with pytest.raises(ValidationError, match="must be selected"):
        CachePrunePlan.model_validate(missing)

    excessive = _plan(status_result, 0).model_dump()
    excessive["target_entry_bytes_total"] = 10
    with pytest.raises(ValidationError, match="more entries"):
        CachePrunePlan.model_validate(excessive)


def test_real_status_planning_does_not_access_or_mutate_filesystem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "cache"
    _put_embedding(directory, "first")
    _put_embedding(directory, "second")
    status_result = _status(CacheKind.EMBEDDING, directory)
    before = {
        path.name: (
            path.read_bytes(),
            stat.S_IMODE(path.stat().st_mode),
            path.stat().st_mtime_ns,
        )
        for path in directory.iterdir()
    }

    def fail_filesystem_access(*args: object, **kwargs: object) -> None:
        raise AssertionError("planner accessed filesystem")

    monkeypatch.setattr(os, "scandir", fail_filesystem_access)
    monkeypatch.setattr(os, "open", fail_filesystem_access)
    plan = _plan(status_result, 0)
    assert plan.selected_entry_count == 2

    after = {
        path.name: (
            path.read_bytes(),
            stat.S_IMODE(path.stat().st_mode),
            path.stat().st_mtime_ns,
        )
        for path in directory.iterdir()
    }
    assert before == after


def test_empty_plan_does_not_create_or_inspect_directory(tmp_path: Path) -> None:
    directory = tmp_path / "missing"
    plan = _plan(_synthetic_status(), 0).model_copy(update={"directory": directory})
    result = _execute(plan)
    assert result.planned_entry_count == 0
    assert result.items == ()
    assert not directory.exists()


def test_embedding_prune_deletes_only_planned_entry_and_preserves_lock(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "embedding"
    selected = _put_embedding(directory, "selected")
    retained = _put_embedding(directory, "retained")
    os.utime(selected, ns=(100, 100))
    os.utime(retained, ns=(200, 200))
    cache = FileEmbeddingCache(directory=directory)
    plan = _plan(_status(CacheKind.EMBEDDING, directory), retained.stat().st_size)

    result = _execute(plan)

    assert result.deleted_entry_count == 1
    assert result.items[0].outcome is CachePruneOutcome.DELETED
    assert not selected.exists()
    assert retained.exists()
    assert (directory / ".embedding-cache.lock").exists()
    assert cache.get(text="retained", model_name="model-a", dimensions=2) is not None
    assert cache.get(text="selected", model_name="model-a", dimensions=2) is None
    cache.put(
        text="selected",
        embedding=TextEmbedding(
            model_name="model-a", dimensions=2, vector=[0.25, 0.75]
        ),
    )
    assert selected.exists()


def test_prune_never_deletes_corrupt_temp_unknown_or_lock_files(tmp_path: Path) -> None:
    directory = tmp_path / "embedding"
    selected = _put_embedding(directory)
    corrupt = directory / (("f" * 64) + ".json")
    temporary = directory / ("." + ("e" * 64) + ".json.random.tmp")
    unknown = directory / "unknown.txt"
    corrupt.write_text("{broken", encoding="utf-8")
    temporary.write_text("temporary", encoding="utf-8")
    unknown.write_text("unknown", encoding="utf-8")
    lock = directory / ".embedding-cache.lock"
    plan = _plan(_status(CacheKind.EMBEDDING, directory), 0)

    result = _execute(plan)

    assert result.deleted_entry_count == 1
    assert not selected.exists()
    assert corrupt.exists()
    assert temporary.exists()
    assert unknown.exists()
    assert lock.exists()


def test_embedding_execution_uses_existing_global_exclusive_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "embedding"
    _put_embedding(directory)
    plan = _plan(_status(CacheKind.EMBEDDING, directory), 0)
    observed: list[bool] = []
    original_lock = FileEmbeddingCache._lock

    def recording_lock(descriptor: int, *, exclusive: bool) -> None:
        observed.append(exclusive)
        original_lock(descriptor, exclusive=exclusive)

    monkeypatch.setattr(FileEmbeddingCache, "_lock", staticmethod(recording_lock))
    _execute(plan)
    assert observed == [True]


def test_parsed_prune_deletes_entry_and_preserves_per_key_lock(tmp_path: Path) -> None:
    directory = tmp_path / "parsed"
    selected = _put_parsed(directory, b"selected")
    retained = _put_parsed(directory, b"retained")
    os.utime(selected, ns=(100, 100))
    os.utime(retained, ns=(200, 200))
    selected_identity = _parsed_identity(b"selected")
    retained_identity = _parsed_identity(b"retained")
    plan = _plan(_status(CacheKind.PARSED, directory), retained.stat().st_size)

    result = _execute(plan)

    assert result.deleted_entry_count == 1
    assert not selected.exists()
    assert retained.exists()
    assert (directory / f".{selected_identity.cache_key}.lock").exists()
    assert (directory / f".{retained_identity.cache_key}.lock").exists()
    cache = FileParsedDocumentCache(directory=directory)
    assert cache.get(selected_identity) is None
    assert cache.get(retained_identity) is not None
    cache.put(
        selected_identity,
        ParsedLocalDocument(
            content="selected", content_type=ResearchSourceContentType.TEXT
        ),
    )
    assert selected.exists()


def test_parsed_execution_uses_per_key_exclusive_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "parsed"
    _put_parsed(directory)
    plan = _plan(_status(CacheKind.PARSED, directory), 0)
    observed: list[bool] = []
    original_lock = FileParsedDocumentCache._lock

    def recording_lock(descriptor: int, *, exclusive: bool) -> None:
        observed.append(exclusive)
        original_lock(descriptor, exclusive=exclusive)

    monkeypatch.setattr(FileParsedDocumentCache, "_lock", staticmethod(recording_lock))
    _execute(plan)
    assert observed == [True]


def test_missing_candidate_is_safely_skipped(tmp_path: Path) -> None:
    directory = tmp_path / "embedding"
    entry = _put_embedding(directory)
    plan = _plan(_status(CacheKind.EMBEDDING, directory), 0)
    entry.unlink()
    result = _execute(plan)
    assert result.deleted_entry_count == 0
    assert result.skipped_entry_count == 1
    assert result.items[0].outcome is CachePruneOutcome.ALREADY_ABSENT


def test_changed_candidate_is_stale_and_preserved(tmp_path: Path) -> None:
    directory = tmp_path / "embedding"
    entry = _put_embedding(directory)
    plan = _plan(_status(CacheKind.EMBEDDING, directory), 0)
    entry.write_text("changed", encoding="utf-8")
    result = _execute(plan)
    assert result.items[0].outcome is CachePruneOutcome.STALE
    assert entry.read_text(encoding="utf-8") == "changed"


def test_current_corrupt_candidate_is_invalid_and_preserved(tmp_path: Path) -> None:
    directory = tmp_path / "parsed"
    entry = _put_parsed(directory)
    plan = _plan(_status(CacheKind.PARSED, directory), 0)
    candidate = plan.candidates[0]
    entry.write_bytes(b"x" * candidate.size_bytes)
    os.utime(entry, ns=(candidate.mtime_ns, candidate.mtime_ns))
    result = _execute(plan)
    assert result.items[0].outcome is CachePruneOutcome.INVALID
    assert entry.exists()


def test_symlink_replacement_is_rejected_without_touching_target(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "embedding"
    entry = _put_embedding(directory)
    plan = _plan(_status(CacheKind.EMBEDDING, directory), 0)
    external = tmp_path / "external"
    external.write_text("unchanged", encoding="utf-8")
    entry.unlink()
    try:
        entry.symlink_to(external)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")
    with pytest.raises(PersistentCachePruneError, match="unsafe"):
        _execute(plan)
    assert external.read_text(encoding="utf-8") == "unchanged"
    assert entry.is_symlink()


def test_nonregular_replacement_is_rejected(tmp_path: Path) -> None:
    directory = tmp_path / "parsed"
    entry = _put_parsed(directory)
    plan = _plan(_status(CacheKind.PARSED, directory), 0)
    entry.unlink()
    entry.mkdir()
    with pytest.raises(PersistentCachePruneError, match="unsafe"):
        _execute(plan)
    assert entry.is_dir()


def test_missing_execution_directory_is_explicit_for_nonempty_plan(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "embedding"
    _put_embedding(directory)
    plan = _plan(_status(CacheKind.EMBEDDING, directory), 0)
    for path in directory.iterdir():
        path.unlink()
    directory.rmdir()
    with pytest.raises(PersistentCachePruneError, match="no longer exists"):
        _execute(plan)
    assert not directory.exists()


def test_unlink_failure_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "embedding"
    entry = _put_embedding(directory)
    plan = _plan(_status(CacheKind.EMBEDDING, directory), 0)

    def fail_unlink(path: Path, *, missing_ok: bool = False) -> None:
        raise OSError("unlink failed")

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(PersistentCachePruneError, match="could not be deleted"):
        _execute(plan)
    assert entry.exists()


def test_directory_fsync_occurs_only_after_deletion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "embedding"
    entry = _put_embedding(directory)
    plan = _plan(_status(CacheKind.EMBEDDING, directory), 0)
    original_fsync = os.fsync
    fsynced_modes: list[int] = []

    def recording_fsync(descriptor: int) -> None:
        fsynced_modes.append(stat.S_IFMT(os.fstat(descriptor).st_mode))
        original_fsync(descriptor)

    monkeypatch.setattr("app.persistent_cache_maintenance.os.fsync", recording_fsync)
    _execute(plan)
    assert not entry.exists()
    assert fsynced_modes == [stat.S_IFDIR]


def test_fsync_failure_is_explicit_with_deleted_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "embedding"
    entry = _put_embedding(directory)
    plan = _plan(_status(CacheKind.EMBEDDING, directory), 0)

    def fail_fsync(descriptor: int) -> None:
        raise OSError("fsync failed")

    monkeypatch.setattr("app.persistent_cache_maintenance.os.fsync", fail_fsync)
    with pytest.raises(PersistentCachePruneError, match="synchronized") as error:
        _execute(plan)
    assert not entry.exists()
    assert error.value.deleted_entry_count == 1


def test_partial_failure_keeps_completed_deletion_and_exposes_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "embedding"
    first = _put_embedding(directory, "first")
    second = _put_embedding(directory, "second")
    os.utime(first, ns=(100, 100))
    os.utime(second, ns=(200, 200))
    plan = _plan(_status(CacheKind.EMBEDDING, directory), 0)
    original_unlink = Path.unlink

    def fail_second(path: Path, *, missing_ok: bool = False) -> None:
        if path == second:
            raise OSError("second unlink failed")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_second)
    with pytest.raises(PersistentCachePruneError) as error:
        _execute(plan)
    assert not first.exists()
    assert second.exists()
    assert error.value.deleted_entry_count == 1
    assert error.value.completed_items[0].entry_key == plan.candidates[0].entry_key


def test_active_parsed_key_lock_blocks_deletion_and_other_key_remains_independent(
    tmp_path: Path,
) -> None:
    if "fork" not in multiprocessing.get_all_start_methods():
        pytest.skip("fork multiprocessing is unavailable")
    directory = tmp_path / "parsed"
    blocked_entry = _put_parsed(directory, b"blocked")
    independent_entry = _put_parsed(directory, b"independent")
    os.utime(blocked_entry, ns=(100, 100))
    os.utime(independent_entry, ns=(200, 200))
    full_status = _status(CacheKind.PARSED, directory)
    blocked_candidate = next(
        entry for entry in full_status.entries if entry.filename == blocked_entry.name
    )
    independent_candidate = next(
        entry
        for entry in full_status.entries
        if entry.filename == independent_entry.name
    )
    blocked_plan = _plan(
        full_status.model_copy(
            update={
                "entries": (blocked_candidate,),
                "valid_entry_count": 1,
                "valid_entry_bytes": blocked_candidate.size_bytes,
                "oldest_valid_entry_mtime_ns": blocked_candidate.mtime_ns,
                "newest_valid_entry_mtime_ns": blocked_candidate.mtime_ns,
            }
        ),
        0,
    )
    independent_plan = _plan(
        full_status.model_copy(
            update={
                "entries": (independent_candidate,),
                "valid_entry_count": 1,
                "valid_entry_bytes": independent_candidate.size_bytes,
                "oldest_valid_entry_mtime_ns": independent_candidate.mtime_ns,
                "newest_valid_entry_mtime_ns": independent_candidate.mtime_ns,
            }
        ),
        0,
    )
    context = multiprocessing.get_context("fork")
    ready = context.Event()
    release = context.Event()
    process = context.Process(
        target=_hold_parsed_lock,
        args=(directory, blocked_candidate.entry_key, ready, release),
    )
    process.start()
    assert ready.wait(timeout=5)

    completed = threading.Event()
    thread = threading.Thread(
        target=lambda: (_execute(blocked_plan), completed.set()), daemon=True
    )
    thread.start()
    assert not completed.wait(timeout=0.2)
    independent_result = _execute(independent_plan)
    assert independent_result.deleted_entry_count == 1
    assert not independent_entry.exists()
    assert blocked_entry.exists()

    release.set()
    process.join(timeout=5)
    thread.join(timeout=5)
    assert process.exitcode == 0
    assert completed.is_set()
    assert not blocked_entry.exists()


def test_execution_result_models_validate_aggregates_and_are_frozen() -> None:
    item = CachePruneExecutionItem(
        cache_kind=CacheKind.EMBEDDING,
        filename=("a" * 64) + ".json",
        entry_key="a" * 64,
        planned_size_bytes=10,
        outcome=CachePruneOutcome.DELETED,
        deleted_bytes=10,
    )
    result = CachePruneResult(
        cache_kind=CacheKind.EMBEDDING,
        directory=Path("/tmp/cache"),
        planned_entry_count=1,
        planned_entry_bytes=10,
        deleted_entry_count=1,
        deleted_entry_bytes=10,
        skipped_entry_count=0,
        items=(item,),
    )
    with pytest.raises(ValidationError):
        result.deleted_entry_count = 0
    strict_payload = result.model_dump()
    strict_payload["deleted_entry_count"] = "1"
    with pytest.raises(ValidationError):
        CachePruneResult.model_validate(strict_payload)
    invalid = result.model_dump()
    invalid["deleted_entry_bytes"] = 9
    with pytest.raises(ValidationError, match="deleted entry bytes"):
        CachePruneResult.model_validate(invalid)
