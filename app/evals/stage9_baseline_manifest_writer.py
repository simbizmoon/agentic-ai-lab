"""Safely persist and reload one locked Stage 9 baseline plan."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Final

from pydantic import ValidationError

from app.schemas.stage9_baseline_experiment_protocol import (
    Stage9BaselineExperimentPlan,
)

STAGE9_MANIFEST_DIRECTORY_MODE: Final = 0o700
STAGE9_MANIFEST_FILE_MODE: Final = 0o600
DEFAULT_MAXIMUM_STAGE9_MANIFEST_BYTES: Final = 16 * 1024 * 1024


@dataclass(frozen=True)
class Stage9BaselineManifestPaths:
    execution_directory: Path
    manifest_path: Path
    checksum_path: Path
    sha256: str


class Stage9BaselineManifestStorageError(RuntimeError):
    """The manifest could not be stored or verified without ambiguity."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


class Stage9BaselineManifestWriter:
    """Create a private immutable manifest directory and verify exact bytes."""

    def __init__(
        self, *, maximum_manifest_bytes: int = DEFAULT_MAXIMUM_STAGE9_MANIFEST_BYTES
    ) -> None:
        if (
            not isinstance(maximum_manifest_bytes, int)
            or isinstance(maximum_manifest_bytes, bool)
            or maximum_manifest_bytes < 1
        ):
            raise ValueError("maximum_manifest_bytes must be a positive integer")
        self._maximum_manifest_bytes = maximum_manifest_bytes

    def write(
        self, plan: Stage9BaselineExperimentPlan, *, output_directory: Path
    ) -> Stage9BaselineManifestPaths:
        if not isinstance(plan, Stage9BaselineExperimentPlan):
            raise TypeError("plan must be a Stage9BaselineExperimentPlan")
        if not isinstance(output_directory, Path):
            raise TypeError("output_directory must be a Path")

        manifest_id = self._safe_component(plan.manifest.manifest_id)
        root = output_directory.expanduser().resolve()
        if root.exists() and not root.is_dir():
            raise ValueError("output path must be a directory")
        root.mkdir(mode=STAGE9_MANIFEST_DIRECTORY_MODE, parents=True, exist_ok=True)
        execution_directory = root / manifest_id
        if execution_directory.is_symlink() or execution_directory.exists():
            raise ValueError("manifest directory already exists")

        content = self._canonical_bytes(plan)
        if len(content) > self._maximum_manifest_bytes:
            raise Stage9BaselineManifestStorageError("manifest exceeds maximum size")
        sha256 = hashlib.sha256(content).hexdigest()
        checksum = f"{sha256}  manifest.json\n".encode("ascii")

        try:
            execution_directory.mkdir(mode=STAGE9_MANIFEST_DIRECTORY_MODE)
            os.chmod(execution_directory, STAGE9_MANIFEST_DIRECTORY_MODE)
            manifest_path = execution_directory / "manifest.json"
            checksum_path = execution_directory / "manifest.json.sha256"
            temporary_manifest = self._prepare(
                execution_directory, manifest_path.name, content
            )
            temporary_checksum = self._prepare(
                execution_directory, checksum_path.name, checksum
            )
            if manifest_path.exists() or checksum_path.exists():
                raise Stage9BaselineManifestStorageError("manifest target is unsafe")
            os.replace(temporary_manifest, manifest_path)
            os.replace(temporary_checksum, checksum_path)
            self._fsync_directory(execution_directory)
            loaded = self.load(manifest_path)
            if loaded != plan:
                raise Stage9BaselineManifestStorageError(
                    "stored manifest failed exact typed verification"
                )
            return Stage9BaselineManifestPaths(
                execution_directory=execution_directory,
                manifest_path=manifest_path,
                checksum_path=checksum_path,
                sha256=sha256,
            )
        except BaseException as error:
            self._cleanup(execution_directory)
            if isinstance(error, (TypeError, ValueError)):
                raise
            if isinstance(error, Stage9BaselineManifestStorageError):
                raise
            raise Stage9BaselineManifestStorageError(
                "manifest artifacts could not be written"
            ) from error

    def load(self, manifest_path: Path) -> Stage9BaselineExperimentPlan:
        if not isinstance(manifest_path, Path):
            raise TypeError("manifest_path must be a Path")
        checksum_path = Path(str(manifest_path) + ".sha256")
        payload = self._read_regular(manifest_path)
        checksum = self._read_regular(checksum_path, maximum_bytes=256)
        try:
            fields = checksum.decode("ascii").split()
            if len(fields) != 2 or fields[1] != "manifest.json":
                raise ValueError("invalid checksum sidecar shape")
            expected = fields[0]
        except (UnicodeDecodeError, ValueError) as error:
            raise Stage9BaselineManifestStorageError(
                "manifest checksum sidecar is invalid"
            ) from error
        actual = hashlib.sha256(payload).hexdigest()
        if expected != actual:
            raise Stage9BaselineManifestStorageError("manifest checksum mismatch")
        try:
            json.loads(payload, object_pairs_hook=_reject_duplicate_keys)
            plan = Stage9BaselineExperimentPlan.model_validate_json(payload)
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValidationError,
            ValueError,
        ) as error:
            raise Stage9BaselineManifestStorageError(
                "manifest content is invalid"
            ) from error
        if self._canonical_bytes(plan) != payload:
            raise Stage9BaselineManifestStorageError("manifest is not canonical JSON")
        return plan

    @staticmethod
    def _canonical_bytes(plan: Stage9BaselineExperimentPlan) -> bytes:
        return (
            json.dumps(
                plan.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")

    @staticmethod
    def _safe_component(value: str) -> str:
        path = Path(value)
        if (
            not value
            or value != value.strip()
            or value in {".", ".."}
            or path.is_absolute()
            or path.parts != (value,)
            or "/" in value
            or "\\" in value
        ):
            raise ValueError("manifest_id must be one safe path component")
        return value

    @staticmethod
    def _prepare(directory: Path, target_name: str, content: bytes) -> Path:
        with NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=directory,
            prefix=f".{target_name}.",
            suffix=".tmp",
        ) as handle:
            os.fchmod(handle.fileno(), STAGE9_MANIFEST_FILE_MODE)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            return Path(handle.name)

    def _read_regular(self, path: Path, *, maximum_bytes: int | None = None) -> bytes:
        limit = maximum_bytes or self._maximum_manifest_bytes
        try:
            entry = path.lstat()
            if not stat.S_ISREG(entry.st_mode):
                raise Stage9BaselineManifestStorageError(
                    "manifest artifact must be a regular file"
                )
            if entry.st_size > limit:
                raise Stage9BaselineManifestStorageError(
                    "manifest artifact exceeds maximum size"
                )
            return path.read_bytes()
        except FileNotFoundError as error:
            raise Stage9BaselineManifestStorageError(
                "manifest artifact is missing"
            ) from error

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _cleanup(directory: Path) -> None:
        if not directory.exists() or directory.is_symlink():
            return
        for path in directory.iterdir():
            try:
                path.unlink()
            except OSError:
                pass
        try:
            directory.rmdir()
        except OSError:
            pass
