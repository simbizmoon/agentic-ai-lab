"""CLI tests for persistent cache inventory and explicit pruning."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

import pytest

from app.cli import build_parser, main
from app.persistent_cache_maintenance import (
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
    CacheKind,
    CachePruneExecutionItem,
    CachePruneOutcome,
)
from app.schemas.research_source_document import ResearchSourceContentType


@pytest.fixture(autouse=True)
def isolate_cache_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))


def _embedding_directory(tmp_path: Path) -> Path:
    return tmp_path / "xdg-cache" / "aira" / "embeddings"


def _parsed_directory(tmp_path: Path) -> Path:
    return tmp_path / "xdg-cache" / "aira" / "parsed-documents"


def _put_embedding(directory: Path, text: str = "embedding text") -> Path:
    cache = FileEmbeddingCache(directory=directory)
    cache.put(
        text=text,
        embedding=TextEmbedding(
            model_name="model-a",
            dimensions=2,
            vector=[0.25, 0.75],
        ),
    )
    key = build_embedding_cache_key(
        text_sha256=calculate_text_sha256(text),
        model_name="model-a",
        dimensions=2,
    )
    return directory / f"{key}.json"


def _put_parsed(directory: Path, content: str = "private local body") -> Path:
    raw = content.encode()
    identity = ParsedDocumentCacheIdentity(
        raw_content_sha256=hashlib.sha256(raw).hexdigest(),
        raw_file_size_bytes=len(raw),
        parser=build_local_document_parser_identity(".txt"),
    )
    FileParsedDocumentCache(directory=directory).put(
        identity,
        ParsedLocalDocument(
            content=content,
            content_type=ResearchSourceContentType.TEXT,
        ),
    )
    return directory / f"{identity.cache_key}.json"


def test_cache_status_reports_both_missing_directories(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["cache", "status"]) == 0
    output = capsys.readouterr().out
    assert "AIRA cache status: embedding" in output
    assert "AIRA cache status: parsed" in output
    assert output.count("directory_exists=false") == 2
    assert not _embedding_directory(tmp_path).exists()
    assert not _parsed_directory(tmp_path).exists()


def test_cache_status_reports_populated_caches_without_content(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _put_embedding(_embedding_directory(tmp_path))
    _put_parsed(_parsed_directory(tmp_path), "do not display this private body")
    assert main(["cache", "status"]) == 0
    output = capsys.readouterr().out
    assert output.count("directory_exists=true") == 2
    assert output.count("valid_entries=1") == 2
    assert "lock_files=1" in output
    assert "oldest_valid_entry_mtime_ns=none" not in output
    assert "do not display this private body" not in output


@pytest.mark.parametrize(
    "arguments",
    [
        ["cache", "prune", "--target-bytes", "0"],
        [
            "cache",
            "prune",
            "--embedding",
            "--parsed",
            "--target-bytes",
            "0",
        ],
    ],
)
def test_cache_prune_requires_exactly_one_kind(arguments: list[str]) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(arguments)


def test_cache_prune_rejects_negative_target(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(["cache", "prune", "--embedding", "--target-bytes", "-1"])
    assert result == 2
    assert "target_bytes must be non-negative" in capsys.readouterr().err


def test_dry_run_plans_without_execution_or_mutation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = _embedding_directory(tmp_path)
    entry = _put_embedding(directory)
    before = {
        path.name: (
            path.read_bytes(),
            stat.S_IMODE(path.stat().st_mode),
            path.stat().st_mtime_ns,
        )
        for path in directory.iterdir()
    }
    service = PersistentCacheMaintenanceService()

    def forbidden_execute(*args: object, **kwargs: object) -> None:
        raise AssertionError("dry-run called execute_prune")

    monkeypatch.setattr(service, "execute_prune", forbidden_execute)
    result = main(
        [
            "cache",
            "prune",
            "--embedding",
            "--target-bytes",
            "0",
            "--dry-run",
        ],
        cache_maintenance_service=service,
    )
    after = {
        path.name: (
            path.read_bytes(),
            stat.S_IMODE(path.stat().st_mode),
            path.stat().st_mtime_ns,
        )
        for path in directory.iterdir()
    }
    output = capsys.readouterr().out
    assert result == 0
    assert "dry-run plan" in output
    assert "selected_entries=1" in output
    assert "expected_remaining_valid_bytes=0" in output
    assert "files_deleted=0" in output
    assert entry.exists()
    assert before == after


@pytest.mark.parametrize("kind", [CacheKind.EMBEDDING, CacheKind.PARSED])
def test_actual_prune_updates_post_status_and_preserves_lock(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    kind: CacheKind,
) -> None:
    directory = (
        _embedding_directory(tmp_path)
        if kind is CacheKind.EMBEDDING
        else _parsed_directory(tmp_path)
    )
    entry = (
        _put_embedding(directory)
        if kind is CacheKind.EMBEDDING
        else _put_parsed(directory)
    )
    locks_before = tuple(directory.glob("*.lock")) + tuple(directory.glob(".*.lock"))
    flag = "--embedding" if kind is CacheKind.EMBEDDING else "--parsed"
    result = main(["cache", "prune", flag, "--target-bytes", "0"])
    output = capsys.readouterr().out
    assert result == 0
    assert not entry.exists()
    assert "planned_entries=1" in output
    assert "deleted_entries=1" in output
    assert "outcome_deleted=1" in output
    assert "post_valid_entries=0" in output
    assert "post_valid_bytes=0" in output
    assert locks_before
    assert all(lock.exists() for lock in locks_before)


def test_actual_prune_preserves_non_candidate_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = _embedding_directory(tmp_path)
    valid = _put_embedding(directory)
    corrupt = directory / (("f" * 64) + ".json")
    temporary = directory / ("." + ("e" * 64) + ".json.random.tmp")
    unknown = directory / "unknown.txt"
    corrupt.write_text("{broken", encoding="utf-8")
    temporary.write_text("temporary", encoding="utf-8")
    unknown.write_text("unknown", encoding="utf-8")
    lock = directory / ".embedding-cache.lock"

    assert main(["cache", "prune", "--embedding", "--target-bytes", "0"]) == 0
    capsys.readouterr()
    assert not valid.exists()
    assert corrupt.exists()
    assert temporary.exists()
    assert unknown.exists()
    assert lock.exists()


def test_skipped_outcomes_are_displayed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = _embedding_directory(tmp_path)
    entry = _put_embedding(directory)
    service = PersistentCacheMaintenanceService()
    original_execute = service.execute_prune

    def stale_then_execute(*, plan):  # type: ignore[no-untyped-def]
        os.utime(entry, None)
        return original_execute(plan=plan)

    monkeypatch.setattr(service, "execute_prune", stale_then_execute)
    assert (
        main(
            ["cache", "prune", "--embedding", "--target-bytes", "0"],
            cache_maintenance_service=service,
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "deleted_entries=0" in output
    assert "skipped_entries=1" in output
    assert "outcome_stale=1" in output
    assert "post_valid_entries=1" in output
    assert entry.exists()


def test_partial_failure_returns_two_and_reports_partial_mutation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = _embedding_directory(tmp_path)
    _put_embedding(directory)
    service = PersistentCacheMaintenanceService()
    item = CachePruneExecutionItem(
        cache_kind=CacheKind.EMBEDDING,
        filename=("a" * 64) + ".json",
        entry_key="a" * 64,
        planned_size_bytes=10,
        outcome=CachePruneOutcome.DELETED,
        deleted_bytes=10,
    )

    def fail_execute(*args: object, **kwargs: object) -> None:
        raise PersistentCachePruneError("forced failure", completed_items=(item,))

    monkeypatch.setattr(service, "execute_prune", fail_execute)
    result = main(
        ["cache", "prune", "--embedding", "--target-bytes", "0"],
        cache_maintenance_service=service,
    )
    error = capsys.readouterr().err
    assert result == 2
    assert "partial-failure" in error
    assert "deleted_entries=1" in error
    assert "deleted_bytes=10" in error
    assert "forced failure" in error
