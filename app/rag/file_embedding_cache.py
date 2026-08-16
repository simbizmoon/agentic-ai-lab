"""Safe file-backed persistence for exact text embeddings."""

from __future__ import annotations

import fcntl
import hmac
import json
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from pydantic import ValidationError

from app.rag.embedding_cache import (
    EmbeddingCache,
    EmbeddingCacheError,
    build_embedding_cache_key,
    calculate_text_sha256,
)
from app.schemas.document_embedding import TextEmbedding
from app.schemas.embedding_cache_entry import (
    EMBEDDING_CACHE_ENTRY_VERSION,
    EmbeddingCacheEntry,
)

DEFAULT_MAXIMUM_EMBEDDING_CACHE_ENTRY_BYTES = 8 * 1024 * 1024
EMBEDDING_CACHE_DIRECTORY_MODE = 0o700
EMBEDDING_CACHE_FILE_MODE = 0o600
_LOCK_FILENAME = ".embedding-cache.lock"


class FileEmbeddingCache(EmbeddingCache):
    """Store content-addressed embedding entries as atomic JSON files."""

    def __init__(
        self,
        *,
        directory: Path,
        maximum_entry_bytes: int = (DEFAULT_MAXIMUM_EMBEDDING_CACHE_ENTRY_BYTES),
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
            raise EmbeddingCacheError("embedding cache directory must not be a symlink")
        try:
            directory.mkdir(parents=True, exist_ok=True)
            if not directory.is_dir():
                raise EmbeddingCacheError("embedding cache path must be a directory")
            self._directory = directory.resolve(strict=True)
            os.chmod(self._directory, EMBEDDING_CACHE_DIRECTORY_MODE)
        except EmbeddingCacheError:
            raise
        except (OSError, RuntimeError) as error:
            raise EmbeddingCacheError(
                "embedding cache directory could not be prepared"
            ) from error
        self._maximum_entry_bytes = maximum_entry_bytes

    def get(
        self,
        *,
        text: str,
        model_name: str,
        dimensions: int,
    ) -> TextEmbedding | None:
        """Load an exact entry while treating corrupt payloads as misses."""

        text_sha256, cache_key = self._identity(
            text=text,
            model_name=model_name,
            dimensions=dimensions,
        )
        entry_path = self._entry_path(cache_key)
        lock_fd = self._open_lock()
        try:
            self._lock(lock_fd, exclusive=False)
            if entry_path.is_symlink():
                raise EmbeddingCacheError("embedding cache entry must not be a symlink")
            if not entry_path.exists():
                return None
            if not entry_path.is_file():
                raise EmbeddingCacheError(
                    "embedding cache entry must be a regular file"
                )
            try:
                if entry_path.stat().st_size > self._maximum_entry_bytes:
                    return None
                payload_text = entry_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return None
            except OSError as error:
                raise EmbeddingCacheError(
                    "embedding cache entry could not be read"
                ) from error
        finally:
            self._close_lock(lock_fd)

        entry = self._parse_entry(payload_text)
        if entry is None:
            return None
        if not self._entry_matches(
            entry=entry,
            cache_key=cache_key,
            text_sha256=text_sha256,
            model_name=model_name,
            dimensions=dimensions,
        ):
            return None
        return entry.embedding.model_copy(deep=True)

    def put(
        self,
        *,
        text: str,
        embedding: TextEmbedding,
    ) -> None:
        """Atomically persist an exact nonblank text embedding."""

        if not isinstance(embedding, TextEmbedding):
            raise TypeError("embedding must be a TextEmbedding")
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if not text.strip():
            raise EmbeddingCacheError("blank text must not be cached")

        text_sha256, cache_key = self._identity(
            text=text,
            model_name=embedding.model_name,
            dimensions=embedding.dimensions,
        )
        entry = EmbeddingCacheEntry(
            version=EMBEDDING_CACHE_ENTRY_VERSION,
            cache_key=cache_key,
            text_sha256=text_sha256,
            model_name=embedding.model_name,
            dimensions=embedding.dimensions,
            embedding=embedding.model_copy(deep=True),
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
            raise EmbeddingCacheError("embedding cache entry exceeds maximum size")

        entry_path = self._entry_path(cache_key)
        lock_fd = self._open_lock()
        try:
            self._lock(lock_fd, exclusive=True)
            if entry_path.is_symlink() or entry_path.is_dir():
                raise EmbeddingCacheError("embedding cache entry path is unsafe")
            self._write_entry(entry_path=entry_path, serialized=serialized)
        finally:
            self._close_lock(lock_fd)

    @property
    def directory(self) -> Path:
        """Return the canonical cache directory."""

        return self._directory

    @classmethod
    @contextmanager
    def exclusive_maintenance_lock(cls, directory: Path) -> Iterator[None]:
        """Reuse the cache global lock for external entry maintenance."""

        if not isinstance(directory, Path):
            raise TypeError("directory must be a Path")
        lock_fd = cls._open_lock_for_directory(directory)
        try:
            cls._lock(lock_fd, exclusive=True)
            yield
        finally:
            cls._close_lock(lock_fd)

    def _identity(
        self,
        *,
        text: str,
        model_name: str,
        dimensions: int,
    ) -> tuple[str, str]:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("model_name must not be blank")
        if (
            not isinstance(dimensions, int)
            or isinstance(dimensions, bool)
            or dimensions < 1
        ):
            raise ValueError("dimensions must be positive")
        text_sha256 = calculate_text_sha256(text)
        return text_sha256, build_embedding_cache_key(
            text_sha256=text_sha256,
            model_name=model_name,
            dimensions=dimensions,
        )

    def _entry_path(self, cache_key: str) -> Path:
        return self._directory / f"{cache_key}.json"

    def _open_lock(self) -> int:
        return self._open_lock_for_directory(self._directory)

    @staticmethod
    def _open_lock_for_directory(directory: Path) -> int:
        lock_path = directory / _LOCK_FILENAME
        if lock_path.is_symlink() or lock_path.is_dir():
            raise EmbeddingCacheError("embedding cache lock path is unsafe")
        try:
            flags = os.O_RDWR | os.O_CREAT
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(
                lock_path,
                flags,
                EMBEDDING_CACHE_FILE_MODE,
            )
            try:
                os.fchmod(fd, EMBEDDING_CACHE_FILE_MODE)
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise EmbeddingCacheError("embedding cache lock path is unsafe")
            except BaseException:
                os.close(fd)
                raise
            return fd
        except EmbeddingCacheError:
            raise
        except OSError as error:
            raise EmbeddingCacheError(
                "embedding cache lock could not be opened"
            ) from error

    @staticmethod
    def _lock(fd: int, *, exclusive: bool) -> None:
        try:
            fcntl.flock(
                fd,
                fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH,
            )
        except OSError as error:
            raise EmbeddingCacheError(
                "embedding cache lock could not be acquired"
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

    @staticmethod
    def _parse_entry(payload_text: str) -> EmbeddingCacheEntry | None:
        try:
            payload = json.loads(
                payload_text,
                object_pairs_hook=_reject_duplicate_keys,
            )
            return EmbeddingCacheEntry.model_validate(payload)
        except (json.JSONDecodeError, UnicodeError, ValidationError, ValueError):
            return None

    @staticmethod
    def _entry_matches(
        *,
        entry: EmbeddingCacheEntry,
        cache_key: str,
        text_sha256: str,
        model_name: str,
        dimensions: int,
    ) -> bool:
        return (
            hmac.compare_digest(entry.cache_key, cache_key)
            and hmac.compare_digest(entry.text_sha256, text_sha256)
            and hmac.compare_digest(entry.model_name, model_name)
            and entry.dimensions == dimensions
        )

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
                temp_file.write(serialized)
                temp_file.flush()
                os.fsync(temp_file.fileno())
                os.chmod(temp_path, EMBEDDING_CACHE_FILE_MODE)
            os.replace(temp_path, entry_path)
            replaced = True
            directory_fd = os.open(self._directory, os.O_RDONLY)
            os.fsync(directory_fd)
        except OSError as error:
            raise EmbeddingCacheError(
                "embedding cache entry could not be written"
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


def _reject_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result
