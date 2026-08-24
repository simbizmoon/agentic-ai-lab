"""Safe file-backed storage for persistent vector-index snapshots."""

from __future__ import annotations

import fcntl
import json
import os
import stat
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Final

from pydantic import ValidationError

from app.schemas.persistent_vector_index import PersistentVectorIndexSnapshot

DEFAULT_MAXIMUM_VECTOR_INDEX_SNAPSHOT_BYTES: Final = 256 * 1024 * 1024
VECTOR_INDEX_DIRECTORY_MODE: Final = 0o700
VECTOR_INDEX_FILE_MODE: Final = 0o600
_SNAPSHOT_FILENAME = "vector-index.json"
_LOCK_FILENAME = ".vector-index.lock"


class PersistentVectorIndexStorageError(RuntimeError):
    """Raised when persistent vector-index storage cannot be used safely."""


class PersistentVectorIndexCorruptError(PersistentVectorIndexStorageError):
    """Raised when stored searchable state fails integrity validation."""


class FilePersistentVectorIndex:
    """Atomically save and restore one integrity-checked index snapshot."""

    def __init__(
        self,
        *,
        directory: Path,
        maximum_snapshot_bytes: int = DEFAULT_MAXIMUM_VECTOR_INDEX_SNAPSHOT_BYTES,
    ) -> None:
        if not isinstance(directory, Path):
            raise TypeError("directory must be a Path")
        if (
            not isinstance(maximum_snapshot_bytes, int)
            or isinstance(maximum_snapshot_bytes, bool)
            or maximum_snapshot_bytes < 1
        ):
            raise ValueError("maximum_snapshot_bytes must be positive")
        if directory.is_symlink():
            raise PersistentVectorIndexStorageError(
                "vector index directory must not be a symlink"
            )
        try:
            directory.mkdir(
                parents=True, exist_ok=True, mode=VECTOR_INDEX_DIRECTORY_MODE
            )
            if not directory.is_dir():
                raise PersistentVectorIndexStorageError(
                    "vector index path must be a directory"
                )
            self._directory = directory.resolve(strict=True)
            os.chmod(self._directory, VECTOR_INDEX_DIRECTORY_MODE)
        except PersistentVectorIndexStorageError:
            raise
        except (OSError, RuntimeError) as error:
            raise PersistentVectorIndexStorageError(
                "vector index directory could not be prepared"
            ) from error
        self._maximum_snapshot_bytes = maximum_snapshot_bytes

    @property
    def directory(self) -> Path:
        """Return the canonical private storage directory."""

        return self._directory

    @property
    def snapshot_path(self) -> Path:
        """Return the fixed snapshot path."""

        return self._directory / _SNAPSHOT_FILENAME

    def load(self) -> PersistentVectorIndexSnapshot | None:
        """Load a valid snapshot, return None only when no snapshot exists."""

        lock_fd = self._open_lock()
        try:
            self._lock(lock_fd, exclusive=False)
            payload = self._read_snapshot_bytes()
        finally:
            self._close_lock(lock_fd)
        if payload is None:
            return None
        return self._parse_snapshot(payload)

    def save(self, snapshot: PersistentVectorIndexSnapshot) -> None:
        """Atomically persist a fully validated snapshot."""

        if not isinstance(snapshot, PersistentVectorIndexSnapshot):
            raise TypeError("snapshot must be PersistentVectorIndexSnapshot")
        serialized = (
            json.dumps(
                snapshot.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            ).rstrip("\n")
            + "\n"
        )
        encoded = serialized.encode("utf-8")
        if len(encoded) > self._maximum_snapshot_bytes:
            raise PersistentVectorIndexStorageError(
                "vector index snapshot exceeds maximum size"
            )

        lock_fd = self._open_lock()
        try:
            self._lock(lock_fd, exclusive=True)
            self._validate_optional_regular_target(self.snapshot_path)
            self._write_snapshot(serialized)
        finally:
            self._close_lock(lock_fd)

    def _read_snapshot_bytes(self) -> bytes | None:
        try:
            entry_stat = self.snapshot_path.lstat()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise PersistentVectorIndexStorageError(
                "vector index snapshot could not be inspected"
            ) from error
        if stat.S_ISLNK(entry_stat.st_mode):
            raise PersistentVectorIndexStorageError(
                "vector index snapshot must not be a symlink"
            )
        if not stat.S_ISREG(entry_stat.st_mode):
            raise PersistentVectorIndexStorageError(
                "vector index snapshot must be a regular file"
            )
        if entry_stat.st_size > self._maximum_snapshot_bytes:
            raise PersistentVectorIndexCorruptError(
                "vector index snapshot exceeds maximum readable size"
            )
        try:
            return self.snapshot_path.read_bytes()
        except OSError as error:
            raise PersistentVectorIndexStorageError(
                "vector index snapshot could not be read"
            ) from error

    @staticmethod
    def _parse_snapshot(payload: bytes) -> PersistentVectorIndexSnapshot:
        try:
            payload_text = payload.decode("utf-8")
            value = json.loads(
                payload_text,
                object_pairs_hook=_reject_duplicate_keys,
            )
            return PersistentVectorIndexSnapshot.model_validate_json(
                json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValidationError,
            ValueError,
        ) as error:
            raise PersistentVectorIndexCorruptError(
                "vector index snapshot is corrupt"
            ) from error

    def _open_lock(self) -> int:
        lock_path = self._directory / _LOCK_FILENAME
        self._validate_optional_regular_target(
            lock_path,
            message="vector index lock path is unsafe",
        )
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(lock_path, flags, VECTOR_INDEX_FILE_MODE)
            try:
                os.fchmod(fd, VECTOR_INDEX_FILE_MODE)
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise PersistentVectorIndexStorageError(
                        "vector index lock path is unsafe"
                    )
            except BaseException:
                os.close(fd)
                raise
            return fd
        except PersistentVectorIndexStorageError:
            raise
        except OSError as error:
            raise PersistentVectorIndexStorageError(
                "vector index lock could not be opened"
            ) from error

    @staticmethod
    def _lock(fd: int, *, exclusive: bool) -> None:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        except OSError as error:
            raise PersistentVectorIndexStorageError(
                "vector index lock could not be acquired"
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
    def _validate_optional_regular_target(
        path: Path,
        *,
        message: str = "vector index snapshot path is unsafe",
    ) -> None:
        try:
            target_stat = path.lstat()
        except FileNotFoundError:
            return
        except OSError as error:
            raise PersistentVectorIndexStorageError(message) from error
        if stat.S_ISLNK(target_stat.st_mode) or not stat.S_ISREG(target_stat.st_mode):
            raise PersistentVectorIndexStorageError(message)

    def _write_snapshot(self, serialized: str) -> None:
        temp_path: Path | None = None
        replaced = False
        directory_fd: int | None = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                delete=False,
                dir=self._directory,
                prefix=f".{_SNAPSHOT_FILENAME}.",
                suffix=".tmp",
            ) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(serialized)
                temp_file.flush()
                os.fsync(temp_file.fileno())
                os.chmod(temp_path, VECTOR_INDEX_FILE_MODE)
            os.replace(temp_path, self.snapshot_path)
            replaced = True
            directory_fd = os.open(self._directory, os.O_RDONLY)
            os.fsync(directory_fd)
        except OSError as error:
            raise PersistentVectorIndexStorageError(
                "vector index snapshot could not be written"
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
