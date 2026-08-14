"""Trust-boundary validation for local research source files."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.exceptions import ReportIntegrityReadError
from app.report_integrity import calculate_sha256, is_valid_sha256_digest


class LocalDocumentAccessError(ValueError):
    """Raised when a local research source fails access validation."""


class LocalDocumentAccessPolicy(BaseModel):
    """Immutable bounds for accessing local research source files."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    allowed_roots: tuple[Path, ...]
    maximum_file_bytes: int = Field(ge=1)

    @field_validator("allowed_roots", mode="before")
    @classmethod
    def _validate_allowed_roots(cls, value: object) -> tuple[Path, ...]:
        if not isinstance(value, tuple) or not value:
            raise ValueError("allowed_roots must be a nonempty tuple of Paths")

        resolved_roots: list[Path] = []
        for root in value:
            if not isinstance(root, Path):
                raise TypeError("allowed_roots must contain only Paths")
            if not root.is_absolute():
                raise ValueError("allowed roots must be absolute paths")
            try:
                resolved_root = root.expanduser().resolve(strict=True)
            except (OSError, RuntimeError) as error:
                raise ValueError("allowed roots must exist and be readable") from error
            if not resolved_root.is_dir():
                raise ValueError("allowed roots must be directories")
            if resolved_root in resolved_roots:
                raise ValueError("allowed roots must be unique")
            resolved_roots.append(resolved_root)
        return tuple(resolved_roots)


class LocalDocumentAccessResult(BaseModel):
    """Validated local source identity and raw-byte provenance."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    resolved_path: Path
    file_size_bytes: int = Field(ge=0)
    content_sha256: str

    @field_validator("resolved_path")
    @classmethod
    def _validate_resolved_path(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("resolved_path must be absolute")
        return value

    @field_validator("file_size_bytes")
    @classmethod
    def _reject_boolean_size(cls, value: int) -> int:
        if isinstance(value, bool):
            raise TypeError("file_size_bytes must be an integer")
        return value

    @field_validator("content_sha256")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("content_sha256 must be a lowercase SHA-256 digest")
        return value


class LocalDocumentAccessGate:
    """Validate one local research source against an immutable policy."""

    def __init__(self, policy: LocalDocumentAccessPolicy) -> None:
        if not isinstance(policy, LocalDocumentAccessPolicy):
            raise TypeError("policy must be a LocalDocumentAccessPolicy")
        self._policy = policy

    def validate(self, path: Path) -> LocalDocumentAccessResult:
        """Validate and fingerprint a local source without parsing its content."""
        if not isinstance(path, Path):
            raise LocalDocumentAccessError("local document source must be a Path")

        try:
            source_path = path.expanduser()
        except RuntimeError as error:
            raise LocalDocumentAccessError("local document source path could not be expanded") from error
        if source_path.is_symlink():
            raise LocalDocumentAccessError("local document source must not be a symlink")
        if not source_path.exists():
            raise LocalDocumentAccessError("local document source does not exist")
        if not source_path.is_file():
            raise LocalDocumentAccessError("local document source must be a regular file")

        try:
            resolved_path = source_path.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise LocalDocumentAccessError("local document source could not be resolved") from error
        if not any(_is_within(resolved_path, root) for root in self._policy.allowed_roots):
            raise LocalDocumentAccessError("local document source is outside the allowed roots")

        try:
            file_size_bytes = resolved_path.stat().st_size
        except OSError as error:
            raise LocalDocumentAccessError("local document source size could not be read") from error
        if file_size_bytes > self._policy.maximum_file_bytes:
            raise LocalDocumentAccessError("local document source exceeds the maximum file size")

        try:
            content_sha256 = calculate_sha256(resolved_path)
        except ReportIntegrityReadError as error:
            raise LocalDocumentAccessError("local document source could not be hashed") from error

        return LocalDocumentAccessResult(
            resolved_path=resolved_path,
            file_size_bytes=file_size_bytes,
            content_sha256=content_sha256,
        )


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
