"""Safe file-backed persistence for parsed local documents."""

from __future__ import annotations

import fcntl
import json
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Final

from pydantic import ValidationError

from app.report_integrity import is_valid_sha256_digest
from app.research.parsed_document_cache import (
    PARSED_DOCUMENT_CACHE_SCHEMA_VERSION,
    ParsedDocumentCache,
    ParsedDocumentCacheEntry,
    ParsedDocumentCacheEntryAccess,
    ParsedDocumentCacheEntryTooLargeError,
    ParsedDocumentCacheError,
    ParsedDocumentCacheIdentity,
)
from app.schemas.parsed_local_document import ParsedLocalDocument

DEFAULT_MAXIMUM_PARSED_DOCUMENT_CACHE_ENTRY_BYTES: Final = 256 * 1024 * 1024
PARSED_DOCUMENT_CACHE_DIRECTORY_MODE: Final = 0o700
PARSED_DOCUMENT_CACHE_FILE_MODE: Final = 0o600


class FileParsedDocumentCache(ParsedDocumentCache):
    """Store content-addressed parsed documents as atomic JSON entries."""

    def __init__(
        self,
        *,
        directory: Path,
        maximum_entry_bytes: int = (DEFAULT_MAXIMUM_PARSED_DOCUMENT_CACHE_ENTRY_BYTES),
    ) -> None:
        if not isinstance(directory, Path):
            raise TypeError("directory must be a Path")
        if (
            not isinstance(maximum_entry_bytes, int)
            or isinstance(maximum_entry_bytes, bool)
            or maximum_entry_bytes < 1
        ):
            raise ValueError("maximum_entry_bytes must be positive")
        if directory.is_symlink():
            raise ParsedDocumentCacheError(
                "parsed-document cache directory must not be a symlink"
            )
        try:
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not directory.is_dir():
                raise ParsedDocumentCacheError(
                    "parsed-document cache path must be a directory"
                )
            self._directory = directory.resolve(strict=True)
            os.chmod(self._directory, PARSED_DOCUMENT_CACHE_DIRECTORY_MODE)
        except ParsedDocumentCacheError:
            raise
        except (OSError, RuntimeError) as error:
            raise ParsedDocumentCacheError(
                "parsed-document cache directory could not be prepared"
            ) from error
        self._maximum_entry_bytes = maximum_entry_bytes

    @property
    def directory(self) -> Path:
        """Return the canonical cache directory."""

        return self._directory

    def get(self, identity: ParsedDocumentCacheIdentity) -> ParsedLocalDocument | None:
        """Load an exact entry while treating corrupt payloads as misses."""

        self._validate_identity(identity)
        with self._entry_lock(identity.cache_key, exclusive=False):
            return self._get_unlocked(identity)

    def put(
        self,
        identity: ParsedDocumentCacheIdentity,
        parsed_document: ParsedLocalDocument,
    ) -> None:
        """Atomically persist a parsed document for an exact identity."""

        with self.exclusive_entry(identity) as entry:
            entry.put(parsed_document)

    @contextmanager
    def exclusive_entry(
        self, identity: ParsedDocumentCacheIdentity
    ) -> Iterator[ParsedDocumentCacheEntryAccess]:
        """Lock one key for a non-nested recheck and optional write."""

        self._validate_identity(identity)
        with self._entry_lock(identity.cache_key, exclusive=True):
            yield _FileParsedDocumentCacheEntryAccess(self, identity)

    @classmethod
    @contextmanager
    def exclusive_maintenance_entry_lock(
        cls, *, directory: Path, cache_key: str
    ) -> Iterator[None]:
        """Reuse one existing per-key lock for external entry maintenance."""

        if not isinstance(directory, Path):
            raise TypeError("directory must be a Path")
        if not isinstance(cache_key, str) or not is_valid_sha256_digest(cache_key):
            raise ValueError("cache_key must be a lowercase SHA-256 digest")
        lock_fd = cls._open_lock_for_directory(directory, cache_key)
        try:
            cls._lock(lock_fd, exclusive=True)
            yield
        finally:
            cls._close_lock(lock_fd)

    def _get_unlocked(
        self, identity: ParsedDocumentCacheIdentity
    ) -> ParsedLocalDocument | None:
        entry_bytes = self._read_entry_bytes(self._entry_path(identity.cache_key))
        if entry_bytes is None:
            return None
        try:
            payload_text = entry_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return None
        entry = self._parse_entry(payload_text)
        if entry is None or entry.identity != identity:
            return None
        return entry.parsed_document.model_copy(deep=True)

    def _put_unlocked(
        self,
        identity: ParsedDocumentCacheIdentity,
        parsed_document: ParsedLocalDocument,
    ) -> None:
        if not isinstance(parsed_document, ParsedLocalDocument):
            raise TypeError("parsed_document must be a ParsedLocalDocument")
        serialized = self._serialize_entry(identity, parsed_document)
        entry_path = self._entry_path(identity.cache_key)
        self._validate_optional_regular_target(
            entry_path,
            unsafe_message="parsed-document cache entry path is unsafe",
        )
        self._write_entry(entry_path=entry_path, serialized=serialized)

    def _serialize_entry(
        self,
        identity: ParsedDocumentCacheIdentity,
        parsed_document: ParsedLocalDocument,
    ) -> str:
        entry = ParsedDocumentCacheEntry(
            schema_version=PARSED_DOCUMENT_CACHE_SCHEMA_VERSION,
            cache_key=identity.cache_key,
            identity=identity,
            parsed_document=parsed_document.model_copy(deep=True),
        )
        serialized = (
            json.dumps(
                entry.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            ).rstrip("\n")
            + "\n"
        )
        if len(serialized.encode("utf-8")) > self._maximum_entry_bytes:
            raise ParsedDocumentCacheEntryTooLargeError(
                "parsed-document cache entry exceeds maximum size"
            )
        return serialized

    @staticmethod
    def _validate_identity(identity: ParsedDocumentCacheIdentity) -> None:
        if not isinstance(identity, ParsedDocumentCacheIdentity):
            raise TypeError("identity must be a ParsedDocumentCacheIdentity")

    def _entry_path(self, cache_key: str) -> Path:
        return self._directory / f"{cache_key}.json"

    def _lock_path(self, cache_key: str) -> Path:
        return self._directory / f".{cache_key}.lock"

    @contextmanager
    def _entry_lock(self, cache_key: str, *, exclusive: bool) -> Iterator[None]:
        lock_fd = self._open_lock(cache_key)
        try:
            self._lock(lock_fd, exclusive=exclusive)
            yield
        finally:
            self._close_lock(lock_fd)

    def _open_lock(self, cache_key: str) -> int:
        return self._open_lock_for_directory(self._directory, cache_key)

    @classmethod
    def _open_lock_for_directory(cls, directory: Path, cache_key: str) -> int:
        lock_path = directory / f".{cache_key}.lock"
        cls._validate_optional_regular_target(
            lock_path,
            unsafe_message="parsed-document cache lock path is unsafe",
        )
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(lock_path, flags, PARSED_DOCUMENT_CACHE_FILE_MODE)
            try:
                os.fchmod(fd, PARSED_DOCUMENT_CACHE_FILE_MODE)
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise ParsedDocumentCacheError(
                        "parsed-document cache lock path is unsafe"
                    )
            except BaseException:
                os.close(fd)
                raise
            return fd
        except ParsedDocumentCacheError:
            raise
        except OSError as error:
            raise ParsedDocumentCacheError(
                "parsed-document cache lock could not be opened"
            ) from error

    @staticmethod
    def _lock(fd: int, *, exclusive: bool) -> None:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        except OSError as error:
            raise ParsedDocumentCacheError(
                "parsed-document cache lock could not be acquired"
            ) from error

    @staticmethod
    def _close_lock(fd: int) -> None:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(fd)
        except OSError:
            pass

    def _read_entry_bytes(self, entry_path: Path) -> bytes | None:
        try:
            entry_stat = entry_path.lstat()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise ParsedDocumentCacheError(
                "parsed-document cache entry could not be inspected"
            ) from error
        if stat.S_ISLNK(entry_stat.st_mode):
            raise ParsedDocumentCacheError(
                "parsed-document cache entry must not be a symlink"
            )
        if not stat.S_ISREG(entry_stat.st_mode):
            raise ParsedDocumentCacheError(
                "parsed-document cache entry must be a regular file"
            )
        if entry_stat.st_size > self._maximum_entry_bytes:
            return None
        try:
            return entry_path.read_bytes()
        except OSError as error:
            raise ParsedDocumentCacheError(
                "parsed-document cache entry could not be read"
            ) from error

    @staticmethod
    def _parse_entry(payload_text: str) -> ParsedDocumentCacheEntry | None:
        try:
            payload = json.loads(
                payload_text,
                object_pairs_hook=_reject_duplicate_keys,
            )
            return ParsedDocumentCacheEntry.model_validate_json(
                json.dumps(payload, ensure_ascii=False)
            )
        except (json.JSONDecodeError, UnicodeError, ValidationError, ValueError):
            return None

    @staticmethod
    def _validate_optional_regular_target(path: Path, *, unsafe_message: str) -> None:
        try:
            target_stat = path.lstat()
        except FileNotFoundError:
            return
        except OSError as error:
            raise ParsedDocumentCacheError(unsafe_message) from error
        if stat.S_ISLNK(target_stat.st_mode) or not stat.S_ISREG(target_stat.st_mode):
            raise ParsedDocumentCacheError(unsafe_message)

    def _write_entry(self, *, entry_path: Path, serialized: str) -> None:
        temp_path: Path | None = None
        replaced = False
        directory_fd: int | None = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                delete=False,
                dir=self._directory,
                prefix=f".{entry_path.name}.",
                suffix=".tmp",
            ) as temp_file:
                temp_path = Path(temp_file.name)
                os.fchmod(temp_file.fileno(), PARSED_DOCUMENT_CACHE_FILE_MODE)
                temp_file.write(serialized)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_path, entry_path)
            replaced = True
            directory_fd = os.open(self._directory, os.O_RDONLY)
            os.fsync(directory_fd)
        except OSError as error:
            raise ParsedDocumentCacheError(
                "parsed-document cache entry could not be written"
            ) from error
        finally:
            if directory_fd is not None:
                try:
                    os.close(directory_fd)
                except OSError:
                    pass
            if temp_path is not None and not replaced:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


class _FileParsedDocumentCacheEntryAccess(ParsedDocumentCacheEntryAccess):
    def __init__(
        self,
        cache: FileParsedDocumentCache,
        identity: ParsedDocumentCacheIdentity,
    ) -> None:
        self._cache = cache
        self._identity = identity

    def get(self) -> ParsedLocalDocument | None:
        return self._cache._get_unlocked(self._identity)

    def put(self, parsed_document: ParsedLocalDocument) -> None:
        self._cache._put_unlocked(self._identity, parsed_document)
