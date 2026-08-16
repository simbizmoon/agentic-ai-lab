"""Read-only inventory for AIRA persistent file caches."""

from __future__ import annotations

import json
import os
import re
import stat
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from pydantic import ValidationError

from app.rag.embedding_cache import EmbeddingCacheError, build_embedding_cache_key
from app.rag.file_embedding_cache import (
    DEFAULT_MAXIMUM_EMBEDDING_CACHE_ENTRY_BYTES,
    FileEmbeddingCache,
)
from app.research.file_parsed_document_cache import (
    DEFAULT_MAXIMUM_PARSED_DOCUMENT_CACHE_ENTRY_BYTES,
    FileParsedDocumentCache,
)
from app.research.parsed_document_cache import (
    ParsedDocumentCacheEntry,
    ParsedDocumentCacheError,
)
from app.schemas.embedding_cache_entry import EmbeddingCacheEntry
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

_KEY_PATTERN: Final = r"[0-9a-f]{64}"
_ENTRY_PATTERN: Final = re.compile(rf"^(?P<key>{_KEY_PATTERN})\.json$")
_EMBEDDING_LOCK_FILENAME: Final = ".embedding-cache.lock"
_PARSED_LOCK_PATTERN: Final = re.compile(rf"^\.(?P<key>{_KEY_PATTERN})\.lock$")
_TEMP_PATTERN: Final = re.compile(rf"^\.(?P<key>{_KEY_PATTERN})\.json\.[^.]+\.tmp$")


class PersistentCacheInventoryError(RuntimeError):
    """Raised when a cache directory cannot be inventoried safely."""


class PersistentCachePruneError(RuntimeError):
    """Raised when prune execution fails and may be partially applied."""

    def __init__(
        self,
        message: str,
        *,
        completed_items: tuple[CachePruneExecutionItem, ...] = (),
    ) -> None:
        super().__init__(message)
        self.completed_items = completed_items
        self.deleted_entry_count = sum(
            item.outcome is CachePruneOutcome.DELETED for item in completed_items
        )
        self.deleted_entry_bytes = sum(item.deleted_bytes for item in completed_items)


class _CandidateState(StrEnum):
    VALID = "valid"
    ALREADY_ABSENT = "already_absent"
    STALE = "stale"
    INVALID = "invalid"


class PersistentCacheMaintenanceService:
    """Inspect cache state without locking, repairing, or mutating it.

    Results are observational rather than transactional: concurrent atomic writers
    may make the directory differ before or after any individual item is observed.
    """

    def status(self, *, cache_kind: CacheKind, directory: Path) -> CacheStatus:
        """Return a deterministic read-only inventory of one cache directory."""

        if not isinstance(cache_kind, CacheKind):
            raise TypeError("cache_kind must be a CacheKind")
        if not isinstance(directory, Path):
            raise TypeError("directory must be a Path")
        if not directory.is_absolute():
            raise ValueError("cache directory must be absolute")

        directory_stat = self._directory_stat(directory)
        if directory_stat is None:
            return self._empty_status(cache_kind=cache_kind, directory=directory)
        if stat.S_ISLNK(directory_stat.st_mode):
            raise PersistentCacheInventoryError("cache directory must not be a symlink")
        if not stat.S_ISDIR(directory_stat.st_mode):
            raise PersistentCacheInventoryError("cache path must be a directory")

        valid_entries: list[CacheEntryInfo] = []
        corrupt_count = corrupt_bytes = 0
        lock_count = lock_bytes = 0
        temporary_count = temporary_bytes = 0
        unknown_count = unknown_bytes = 0

        for path, target_stat in self._scanned_targets(directory):
            if not stat.S_ISREG(target_stat.st_mode):
                raise PersistentCacheInventoryError(
                    "cache directory contains an unsafe non-regular target"
                )
            size_bytes = target_stat.st_size
            entry_match = _ENTRY_PATTERN.fullmatch(path.name)
            if entry_match is not None:
                key = entry_match.group("key")
                validity = self._entry_validity(
                    cache_kind=cache_kind,
                    path=path,
                    expected_key=key,
                    expected_stat=target_stat,
                )
                if validity is None:
                    continue
                if validity:
                    valid_entries.append(
                        CacheEntryInfo(
                            cache_kind=cache_kind,
                            filename=path.name,
                            entry_key=key,
                            size_bytes=size_bytes,
                            mtime_ns=target_stat.st_mtime_ns,
                        )
                    )
                else:
                    corrupt_count += 1
                    corrupt_bytes += size_bytes
                continue
            if self._is_lock_file(cache_kind=cache_kind, filename=path.name):
                lock_count += 1
                lock_bytes += size_bytes
                continue
            if _TEMP_PATTERN.fullmatch(path.name) is not None:
                temporary_count += 1
                temporary_bytes += size_bytes
                continue
            unknown_count += 1
            unknown_bytes += size_bytes

        ordered_entries = tuple(
            sorted(valid_entries, key=lambda entry: (entry.mtime_ns, entry.entry_key))
        )
        mtimes = [entry.mtime_ns for entry in ordered_entries]
        return CacheStatus(
            cache_kind=cache_kind,
            directory=directory,
            directory_exists=True,
            entries=ordered_entries,
            valid_entry_count=len(ordered_entries),
            valid_entry_bytes=sum(entry.size_bytes for entry in ordered_entries),
            corrupt_entry_count=corrupt_count,
            corrupt_entry_bytes=corrupt_bytes,
            lock_file_count=lock_count,
            lock_file_bytes=lock_bytes,
            temporary_file_count=temporary_count,
            temporary_file_bytes=temporary_bytes,
            unknown_target_count=unknown_count,
            unknown_target_bytes=unknown_bytes,
            oldest_valid_entry_mtime_ns=min(mtimes, default=None),
            newest_valid_entry_mtime_ns=max(mtimes, default=None),
        )

    @staticmethod
    def plan_prune(
        *, status: CacheStatus, target_entry_bytes_total: int
    ) -> CachePrunePlan:
        """Plan oldest-successful-write-first removal without filesystem access.

        The returned dry-run plan is based only on one observational status. It is
        not permission to delete and must be revalidated under cache-appropriate
        locking by any future execution layer.
        """

        if not isinstance(status, CacheStatus):
            raise TypeError("status must be a CacheStatus")
        if not isinstance(target_entry_bytes_total, int) or isinstance(
            target_entry_bytes_total, bool
        ):
            raise TypeError("target_entry_bytes_total must be an integer")
        if target_entry_bytes_total < 0:
            raise ValueError("target_entry_bytes_total must be non-negative")

        ordered_entries = sorted(
            status.entries,
            key=lambda entry: (entry.mtime_ns, entry.entry_key),
        )
        selected: list[CachePruneCandidate] = []
        selected_bytes = 0
        remaining_bytes = status.valid_entry_bytes
        if remaining_bytes > target_entry_bytes_total:
            for entry in ordered_entries:
                selected.append(
                    CachePruneCandidate(
                        cache_kind=entry.cache_kind,
                        filename=entry.filename,
                        entry_key=entry.entry_key,
                        size_bytes=entry.size_bytes,
                        mtime_ns=entry.mtime_ns,
                    )
                )
                selected_bytes += entry.size_bytes
                remaining_bytes -= entry.size_bytes
                if remaining_bytes <= target_entry_bytes_total:
                    break

        return CachePrunePlan(
            cache_kind=status.cache_kind,
            directory=status.directory,
            target_entry_bytes_total=target_entry_bytes_total,
            observed_valid_entry_count=status.valid_entry_count,
            observed_valid_entry_bytes=status.valid_entry_bytes,
            selected_entry_count=len(selected),
            selected_entry_bytes=selected_bytes,
            expected_remaining_valid_entry_count=(
                status.valid_entry_count - len(selected)
            ),
            expected_remaining_valid_entry_bytes=remaining_bytes,
            candidates=tuple(selected),
        )

    def execute_prune(self, *, plan: CachePrunePlan) -> CachePruneResult:
        """Lock, revalidate, and unlink only unchanged valid plan candidates.

        Execution is non-transactional. A raised PersistentCachePruneError exposes
        completed items because earlier successful deletions are not recreated.
        """

        if not isinstance(plan, CachePrunePlan):
            raise TypeError("plan must be a CachePrunePlan")
        if not plan.candidates:
            return self._prune_result(plan=plan, items=())

        self._validate_execution_directory(plan.directory)
        completed: list[CachePruneExecutionItem] = []
        try:
            if plan.cache_kind is CacheKind.EMBEDDING:
                with FileEmbeddingCache.exclusive_maintenance_lock(plan.directory):
                    for candidate in plan.candidates:
                        completed.append(
                            self._execute_candidate(
                                directory=plan.directory,
                                candidate=candidate,
                            )
                        )
            else:
                for candidate in plan.candidates:
                    with FileParsedDocumentCache.exclusive_maintenance_entry_lock(
                        directory=plan.directory,
                        cache_key=candidate.entry_key,
                    ):
                        completed.append(
                            self._execute_candidate(
                                directory=plan.directory,
                                candidate=candidate,
                            )
                        )
        except (
            EmbeddingCacheError,
            ParsedDocumentCacheError,
            PersistentCachePruneError,
            OSError,
        ) as error:
            self._raise_execution_failure(
                directory=plan.directory,
                completed=completed,
                cause=error,
            )

        if any(item.outcome is CachePruneOutcome.DELETED for item in completed):
            self._fsync_directory(plan.directory, completed=completed)
        return self._prune_result(plan=plan, items=tuple(completed))

    def _execute_candidate(
        self, *, directory: Path, candidate: CachePruneCandidate
    ) -> CachePruneExecutionItem:
        path = directory / candidate.filename
        state = self._revalidate_candidate(path=path, candidate=candidate)
        if state is _CandidateState.VALID:
            try:
                path.unlink()
            except FileNotFoundError:
                state = _CandidateState.ALREADY_ABSENT
            except OSError as error:
                raise PersistentCachePruneError(
                    "cache prune candidate could not be deleted"
                ) from error
        outcome = {
            _CandidateState.VALID: CachePruneOutcome.DELETED,
            _CandidateState.ALREADY_ABSENT: CachePruneOutcome.ALREADY_ABSENT,
            _CandidateState.STALE: CachePruneOutcome.STALE,
            _CandidateState.INVALID: CachePruneOutcome.INVALID,
        }[state]
        return CachePruneExecutionItem(
            cache_kind=candidate.cache_kind,
            filename=candidate.filename,
            entry_key=candidate.entry_key,
            planned_size_bytes=candidate.size_bytes,
            outcome=outcome,
            deleted_bytes=(
                candidate.size_bytes if outcome is CachePruneOutcome.DELETED else 0
            ),
        )

    def _revalidate_candidate(
        self, *, path: Path, candidate: CachePruneCandidate
    ) -> _CandidateState:
        try:
            observed_stat = path.lstat()
        except FileNotFoundError:
            return _CandidateState.ALREADY_ABSENT
        except OSError as error:
            raise PersistentCachePruneError(
                "cache prune candidate could not be inspected"
            ) from error
        if stat.S_ISLNK(observed_stat.st_mode) or not stat.S_ISREG(
            observed_stat.st_mode
        ):
            raise PersistentCachePruneError(
                "cache prune candidate is an unsafe filesystem target"
            )
        if (
            observed_stat.st_size != candidate.size_bytes
            or observed_stat.st_mtime_ns != candidate.mtime_ns
        ):
            return _CandidateState.STALE

        opened = self._open_candidate(path)
        if opened is None:
            return _CandidateState.ALREADY_ABSENT
        descriptor, opened_stat = opened
        try:
            if (
                opened_stat.st_dev != observed_stat.st_dev
                or opened_stat.st_ino != observed_stat.st_ino
                or opened_stat.st_size != candidate.size_bytes
                or opened_stat.st_mtime_ns != candidate.mtime_ns
            ):
                return _CandidateState.STALE
            payload = self._read_descriptor(descriptor, opened_stat.st_size)
            if payload is None:
                return _CandidateState.STALE
            if not self._payload_is_valid(
                cache_kind=candidate.cache_kind,
                payload_bytes=payload,
                expected_key=candidate.entry_key,
            ):
                return _CandidateState.INVALID
            try:
                final_stat = path.lstat()
            except FileNotFoundError:
                return _CandidateState.ALREADY_ABSENT
            except OSError as error:
                raise PersistentCachePruneError(
                    "cache prune candidate could not be re-inspected"
                ) from error
            if stat.S_ISLNK(final_stat.st_mode) or not stat.S_ISREG(final_stat.st_mode):
                raise PersistentCachePruneError(
                    "cache prune candidate became an unsafe filesystem target"
                )
            if (
                final_stat.st_dev != opened_stat.st_dev
                or final_stat.st_ino != opened_stat.st_ino
                or final_stat.st_size != candidate.size_bytes
                or final_stat.st_mtime_ns != candidate.mtime_ns
            ):
                return _CandidateState.STALE
            return _CandidateState.VALID
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass

    @staticmethod
    def _open_candidate(path: Path) -> tuple[int, os.stat_result] | None:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags)
        except FileNotFoundError:
            return None
        except OSError as error:
            raise PersistentCachePruneError(
                "cache prune candidate could not be opened safely"
            ) from error
        try:
            opened_stat = os.fstat(descriptor)
            if not stat.S_ISREG(opened_stat.st_mode):
                raise PersistentCachePruneError(
                    "cache prune candidate must remain a regular file"
                )
            return descriptor, opened_stat
        except BaseException:
            os.close(descriptor)
            raise

    @staticmethod
    def _read_descriptor(descriptor: int, size_bytes: int) -> bytes | None:
        chunks: list[bytes] = []
        remaining = size_bytes
        try:
            while remaining:
                chunk = os.read(descriptor, min(remaining, 1024 * 1024))
                if not chunk:
                    return None
                chunks.append(chunk)
                remaining -= len(chunk)
        except OSError as error:
            raise PersistentCachePruneError(
                "cache prune candidate could not be read"
            ) from error
        return b"".join(chunks)

    @staticmethod
    def _validate_execution_directory(directory: Path) -> None:
        if not directory.is_absolute():
            raise PersistentCachePruneError("cache prune directory must be absolute")
        try:
            directory_stat = directory.lstat()
        except FileNotFoundError as error:
            raise PersistentCachePruneError(
                "cache prune directory no longer exists"
            ) from error
        except OSError as error:
            raise PersistentCachePruneError(
                "cache prune directory could not be inspected"
            ) from error
        if stat.S_ISLNK(directory_stat.st_mode):
            raise PersistentCachePruneError(
                "cache prune directory must not be a symlink"
            )
        if not stat.S_ISDIR(directory_stat.st_mode):
            raise PersistentCachePruneError("cache prune path must be a directory")

    @staticmethod
    def _fsync_directory(
        directory: Path, *, completed: list[CachePruneExecutionItem]
    ) -> None:
        descriptor: int | None = None
        try:
            flags = os.O_RDONLY
            if hasattr(os, "O_DIRECTORY"):
                flags |= os.O_DIRECTORY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(directory, flags)
            if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise OSError("cache prune path is not a directory")
            os.fsync(descriptor)
        except OSError as error:
            raise PersistentCachePruneError(
                "cache prune directory could not be synchronized",
                completed_items=tuple(completed),
            ) from error
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def _raise_execution_failure(
        self,
        *,
        directory: Path,
        completed: list[CachePruneExecutionItem],
        cause: BaseException,
    ) -> None:
        if any(item.outcome is CachePruneOutcome.DELETED for item in completed):
            self._fsync_directory(directory, completed=completed)
        if isinstance(cause, PersistentCachePruneError):
            message = str(cause)
        else:
            message = "cache prune execution failed"
        raise PersistentCachePruneError(
            message,
            completed_items=tuple(completed),
        ) from cause

    @staticmethod
    def _prune_result(
        *, plan: CachePrunePlan, items: tuple[CachePruneExecutionItem, ...]
    ) -> CachePruneResult:
        deleted = [item for item in items if item.outcome is CachePruneOutcome.DELETED]
        return CachePruneResult(
            cache_kind=plan.cache_kind,
            directory=plan.directory,
            planned_entry_count=plan.selected_entry_count,
            planned_entry_bytes=plan.selected_entry_bytes,
            deleted_entry_count=len(deleted),
            deleted_entry_bytes=sum(item.deleted_bytes for item in deleted),
            skipped_entry_count=len(items) - len(deleted),
            items=items,
        )

    @staticmethod
    def _directory_stat(directory: Path) -> os.stat_result | None:
        try:
            return directory.lstat()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise PersistentCacheInventoryError(
                "cache directory could not be inspected"
            ) from error

    @staticmethod
    def _scanned_targets(directory: Path) -> list[tuple[Path, os.stat_result]]:
        targets: list[tuple[Path, os.stat_result]] = []
        try:
            with os.scandir(directory) as iterator:
                directory_entries = sorted(iterator, key=lambda entry: entry.name)
        except OSError as error:
            raise PersistentCacheInventoryError(
                "cache directory could not be scanned"
            ) from error
        for directory_entry in directory_entries:
            try:
                target_stat = directory_entry.stat(follow_symlinks=False)
            except FileNotFoundError:
                continue
            except OSError as error:
                raise PersistentCacheInventoryError(
                    "cache target could not be inspected"
                ) from error
            targets.append((Path(directory_entry.path), target_stat))
        return targets

    def _entry_validity(
        self,
        *,
        cache_kind: CacheKind,
        path: Path,
        expected_key: str,
        expected_stat: os.stat_result,
    ) -> bool | None:
        maximum_bytes = (
            DEFAULT_MAXIMUM_EMBEDDING_CACHE_ENTRY_BYTES
            if cache_kind is CacheKind.EMBEDDING
            else DEFAULT_MAXIMUM_PARSED_DOCUMENT_CACHE_ENTRY_BYTES
        )
        if expected_stat.st_size > maximum_bytes:
            return False
        payload_bytes = self._read_regular_file(path, expected_stat=expected_stat)
        if payload_bytes is None:
            return None
        return self._payload_is_valid(
            cache_kind=cache_kind,
            payload_bytes=payload_bytes,
            expected_key=expected_key,
        )

    @staticmethod
    def _payload_is_valid(
        *, cache_kind: CacheKind, payload_bytes: bytes, expected_key: str
    ) -> bool:
        try:
            payload_text = payload_bytes.decode("utf-8")
            payload = json.loads(payload_text, object_pairs_hook=_reject_duplicate_keys)
            if cache_kind is CacheKind.EMBEDDING:
                entry = EmbeddingCacheEntry.model_validate(payload)
                calculated_key = build_embedding_cache_key(
                    text_sha256=entry.text_sha256,
                    model_name=entry.model_name,
                    dimensions=entry.dimensions,
                )
                return entry.cache_key == expected_key == calculated_key
            entry = ParsedDocumentCacheEntry.model_validate_json(
                json.dumps(payload, ensure_ascii=False)
            )
            return entry.cache_key == expected_key
        except (UnicodeError, json.JSONDecodeError, ValidationError, ValueError):
            return False

    @staticmethod
    def _read_regular_file(
        path: Path, *, expected_stat: os.stat_result
    ) -> bytes | None:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags)
        except FileNotFoundError:
            return None
        except OSError as error:
            raise PersistentCacheInventoryError(
                "cache entry could not be opened safely"
            ) from error
        try:
            current_stat = os.fstat(descriptor)
            if not stat.S_ISREG(current_stat.st_mode):
                raise PersistentCacheInventoryError(
                    "cache entry must remain a regular file"
                )
            if (
                current_stat.st_dev != expected_stat.st_dev
                or current_stat.st_ino != expected_stat.st_ino
                or current_stat.st_size != expected_stat.st_size
                or current_stat.st_mtime_ns != expected_stat.st_mtime_ns
            ):
                return None
            chunks: list[bytes] = []
            remaining = current_stat.st_size
            while remaining:
                chunk = os.read(descriptor, min(remaining, 1024 * 1024))
                if not chunk:
                    return None
                chunks.append(chunk)
                remaining -= len(chunk)
            return b"".join(chunks)
        except OSError as error:
            raise PersistentCacheInventoryError(
                "cache entry could not be read"
            ) from error
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass

    @staticmethod
    def _is_lock_file(*, cache_kind: CacheKind, filename: str) -> bool:
        if cache_kind is CacheKind.EMBEDDING:
            return filename == _EMBEDDING_LOCK_FILENAME
        return _PARSED_LOCK_PATTERN.fullmatch(filename) is not None

    @staticmethod
    def _empty_status(*, cache_kind: CacheKind, directory: Path) -> CacheStatus:
        return CacheStatus(
            cache_kind=cache_kind,
            directory=directory,
            directory_exists=False,
            valid_entry_count=0,
            valid_entry_bytes=0,
            corrupt_entry_count=0,
            corrupt_entry_bytes=0,
            lock_file_count=0,
            lock_file_bytes=0,
            temporary_file_count=0,
            temporary_file_bytes=0,
            unknown_target_count=0,
            unknown_target_bytes=0,
        )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result
