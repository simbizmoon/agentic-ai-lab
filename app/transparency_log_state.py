"""Persistent state for the local transparency log tip."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.exceptions import (
    TransparencyLogStateExportError,
    TransparencyLogStateReadError,
    TransparencyLogStateValidationError,
)
from app.report_integrity import is_valid_sha256_digest

TRANSPARENCY_LOG_STATE_VERSION = 1
TRANSPARENCY_LOG_STATE_TYPE = "audit_report_transparency_log_state"
MAX_TRANSPARENCY_LOG_STATE_BYTES = 64 * 1024

_STATE_FILE_MODE = 0o600
_READ_MESSAGE = "Failed to read the transparency log state."
_VALIDATION_MESSAGE = "The transparency log state is invalid."
_EXPORT_MESSAGE = "Failed to export the transparency log state."
_ALLOWED_ARTIFACT_TYPES = {"root_transition", "signing_key_manifest"}


class TransparencyLogStatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    state_version: Literal[TRANSPARENCY_LOG_STATE_VERSION]
    state_type: Literal[TRANSPARENCY_LOG_STATE_TYPE]
    log_version: int = Field(ge=1)
    last_sequence: int = Field(ge=1)
    last_entry_hash: str
    last_artifact_type: str
    last_artifact_identifier: str = Field(min_length=1, max_length=512)
    updated_at: datetime

    @field_validator("last_entry_hash")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid hash")
        return value

    @field_validator("last_artifact_type")
    @classmethod
    def _validate_artifact_type(cls, value: str) -> str:
        if value not in _ALLOWED_ARTIFACT_TYPES:
            raise ValueError("invalid artifact type")
        return value

    @field_validator("updated_at")
    @classmethod
    def _validate_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timezone required")
        return value.astimezone(UTC)


def load_transparency_log_state(*, path: Path) -> TransparencyLogStatePayload | None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink():
        raise TransparencyLogStateValidationError(_VALIDATION_MESSAGE)
    if not path.exists():
        return None
    if path.is_dir() or not path.is_file():
        raise TransparencyLogStateValidationError(_VALIDATION_MESSAGE)
    try:
        if path.stat().st_size > MAX_TRANSPARENCY_LOG_STATE_BYTES:
            raise TransparencyLogStateValidationError(_VALIDATION_MESSAGE)
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise TransparencyLogStateReadError(_READ_MESSAGE) from error
    try:
        payload = _loads_no_duplicate_keys(text)
        if not isinstance(payload, dict):
            raise TransparencyLogStateValidationError(_VALIDATION_MESSAGE)
        return TransparencyLogStatePayload.model_validate_json(json.dumps(payload))
    except TransparencyLogStateValidationError:
        raise
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise TransparencyLogStateValidationError(_VALIDATION_MESSAGE) from error


def build_transparency_log_state(*, entry: object, updated_at: datetime) -> TransparencyLogStatePayload:
    if updated_at.tzinfo is None or updated_at.utcoffset() is None:
        raise TransparencyLogStateValidationError(_VALIDATION_MESSAGE)
    artifact_type = entry.artifact_type
    if hasattr(artifact_type, "value"):
        artifact_type = artifact_type.value
    return TransparencyLogStatePayload(
        state_version=TRANSPARENCY_LOG_STATE_VERSION,
        state_type=TRANSPARENCY_LOG_STATE_TYPE,
        log_version=entry.entry_version,
        last_sequence=entry.sequence,
        last_entry_hash=entry.entry_hash,
        last_artifact_type=artifact_type,
        last_artifact_identifier=entry.artifact_identifier,
        updated_at=updated_at.astimezone(UTC),
    )


def format_transparency_log_state_json(state: TransparencyLogStatePayload) -> str:
    if not isinstance(state, TransparencyLogStatePayload):
        raise TypeError("state must be a TransparencyLogStatePayload")
    return json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=False)


def export_transparency_log_state(*, path: Path, state: TransparencyLogStatePayload) -> None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if not isinstance(state, TransparencyLogStatePayload):
        raise TypeError("state must be a TransparencyLogStatePayload")
    if path.is_symlink() or path.is_dir():
        raise TransparencyLogStateValidationError(_VALIDATION_MESSAGE)
    text = format_transparency_log_state_json(state).rstrip("\n") + "\n"
    temp_path: Path | None = None
    replaced = False
    dir_fd: int | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(text)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            os.chmod(temp_path, _STATE_FILE_MODE)
        os.replace(temp_path, path)
        replaced = True
        dir_fd = os.open(path.parent, os.O_RDONLY)
        os.fsync(dir_fd)
    except OSError as error:
        raise TransparencyLogStateExportError(_EXPORT_MESSAGE) from error
    finally:
        if dir_fd is not None:
            try:
                os.close(dir_fd)
            except OSError:
                pass
        if temp_path is not None and not replaced:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _loads_no_duplicate_keys(text: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TransparencyLogStateValidationError(_VALIDATION_MESSAGE)
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)
