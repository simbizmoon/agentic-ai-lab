"""Persistent local witness state for signed transparency checkpoints."""

from __future__ import annotations

import fcntl
import hmac
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from app.exceptions import (
    TransparencyCheckpointConsistencyRequiredError,
    TransparencyCheckpointRollbackError,
    TransparencyCheckpointSplitViewError,
    TransparencyCheckpointStateExportError,
    TransparencyCheckpointStateLockError,
    TransparencyCheckpointStateReadError,
    TransparencyCheckpointStateValidationError,
)
from app.report_integrity import is_valid_sha256_digest
from app.transparency_checkpoint import (
    TransparencyCheckpointVerificationResult,
    TransparencyConsistencyProofVerificationResult,
)

TRANSPARENCY_CHECKPOINT_STATE_VERSION = 1
TRANSPARENCY_CHECKPOINT_STATE_TYPE = "audit_report_transparency_checkpoint_state"
MAX_TRANSPARENCY_CHECKPOINT_STATE_BYTES = 64 * 1024
CHECKPOINT_STATE_FILE_MODE = 0o600

_READ_MESSAGE = "Failed to read the transparency checkpoint state."
_VALIDATION_MESSAGE = "The transparency checkpoint state is invalid."
_EXPORT_MESSAGE = "Failed to export the transparency checkpoint state."
_LOCK_MESSAGE = "Failed to lock the transparency checkpoint state."
_ROLLBACK_MESSAGE = "The transparency checkpoint would roll back the witnessed tree size."
_SPLIT_VIEW_MESSAGE = "The transparency checkpoint conflicts with the witnessed tree root."
_CONSISTENCY_MESSAGE = "A transparency checkpoint consistency proof is required."


class TransparencyCheckpointStatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    state_version: Literal[TRANSPARENCY_CHECKPOINT_STATE_VERSION]
    state_type: Literal[TRANSPARENCY_CHECKPOINT_STATE_TYPE]
    log_id: str = Field(min_length=1, max_length=128)
    highest_tree_size: int = Field(ge=1)
    highest_root_hash: str
    highest_checkpoint_sha256: str
    log_signing_key_id: str = Field(min_length=1, max_length=128)
    updated_at: datetime

    @field_validator("highest_root_hash", "highest_checkpoint_sha256")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid hash")
        return value

    @field_validator("updated_at")
    @classmethod
    def _validate_time(cls, value: datetime) -> datetime:
        return _normalize_aware_datetime(value)


@dataclass(frozen=True)
class TransparencyCheckpointStateApplyResult:
    stored_state: TransparencyCheckpointStatePayload | None
    current_state: TransparencyCheckpointStatePayload
    state_updated: bool


def checkpoint_state_lock_path_for(state_path: Path) -> Path:
    if not isinstance(state_path, Path):
        raise TypeError("state_path must be a Path")
    return state_path.with_name(f"{state_path.name}.lock")


def load_transparency_checkpoint_state(*, path: Path) -> TransparencyCheckpointStatePayload | None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink():
        raise TransparencyCheckpointStateValidationError(_VALIDATION_MESSAGE)
    if not path.exists():
        return None
    if path.is_dir() or not path.is_file():
        raise TransparencyCheckpointStateValidationError(_VALIDATION_MESSAGE)
    try:
        if path.stat().st_size > MAX_TRANSPARENCY_CHECKPOINT_STATE_BYTES:
            raise TransparencyCheckpointStateValidationError(_VALIDATION_MESSAGE)
        payload = _loads_no_duplicate_keys(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TransparencyCheckpointStateValidationError(_VALIDATION_MESSAGE)
        return TransparencyCheckpointStatePayload.model_validate_json(json.dumps(payload))
    except OSError as error:
        raise TransparencyCheckpointStateReadError(_READ_MESSAGE) from error
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise TransparencyCheckpointStateValidationError(_VALIDATION_MESSAGE) from error


def export_transparency_checkpoint_state(*, path: Path, state: TransparencyCheckpointStatePayload) -> None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if not isinstance(state, TransparencyCheckpointStatePayload):
        raise TypeError("state must be a TransparencyCheckpointStatePayload")
    _export_state(path=path, text=format_transparency_checkpoint_state_json(state))


def format_transparency_checkpoint_state_json(state: TransparencyCheckpointStatePayload) -> str:
    return json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=False)


def build_transparency_checkpoint_state(
    *,
    checkpoint: TransparencyCheckpointVerificationResult,
    updated_at: datetime,
) -> TransparencyCheckpointStatePayload:
    return TransparencyCheckpointStatePayload(
        state_version=TRANSPARENCY_CHECKPOINT_STATE_VERSION,
        state_type=TRANSPARENCY_CHECKPOINT_STATE_TYPE,
        log_id=checkpoint.log_id,
        highest_tree_size=checkpoint.tree_size,
        highest_root_hash=checkpoint.root_hash,
        highest_checkpoint_sha256=checkpoint.checkpoint_sha256,
        log_signing_key_id=checkpoint.log_signing_key_id,
        updated_at=_normalize_aware_datetime(updated_at),
    )


def apply_verified_checkpoint_to_state(
    *,
    state_path: Path,
    checkpoint: TransparencyCheckpointVerificationResult,
    consistency_proof: TransparencyConsistencyProofVerificationResult | None,
    updated_at: datetime,
) -> TransparencyCheckpointStateApplyResult:
    if not isinstance(state_path, Path):
        raise TypeError("state_path must be a Path")
    lock_fd = _open_lock(checkpoint_state_lock_path_for(state_path))
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        stored = load_transparency_checkpoint_state(path=state_path)
        if stored is None:
            current = build_transparency_checkpoint_state(checkpoint=checkpoint, updated_at=updated_at)
            export_transparency_checkpoint_state(path=state_path, state=current)
            return TransparencyCheckpointStateApplyResult(stored_state=None, current_state=current, state_updated=True)
        if stored.log_id != checkpoint.log_id or stored.log_signing_key_id != checkpoint.log_signing_key_id:
            raise TransparencyCheckpointSplitViewError(_SPLIT_VIEW_MESSAGE)
        if checkpoint.tree_size < stored.highest_tree_size:
            raise TransparencyCheckpointRollbackError(_ROLLBACK_MESSAGE)
        if checkpoint.tree_size == stored.highest_tree_size:
            same_root = hmac.compare_digest(stored.highest_root_hash, checkpoint.root_hash)
            same_digest = hmac.compare_digest(stored.highest_checkpoint_sha256, checkpoint.checkpoint_sha256)
            if not same_root or not same_digest:
                raise TransparencyCheckpointSplitViewError(_SPLIT_VIEW_MESSAGE)
            return TransparencyCheckpointStateApplyResult(stored_state=stored, current_state=stored, state_updated=False)
        if consistency_proof is None:
            raise TransparencyCheckpointConsistencyRequiredError(_CONSISTENCY_MESSAGE)
        if (
            consistency_proof.old_tree_size != stored.highest_tree_size
            or consistency_proof.old_root_hash != stored.highest_root_hash
            or consistency_proof.new_tree_size != checkpoint.tree_size
            or consistency_proof.new_root_hash != checkpoint.root_hash
        ):
            raise TransparencyCheckpointSplitViewError(_SPLIT_VIEW_MESSAGE)
        current = build_transparency_checkpoint_state(checkpoint=checkpoint, updated_at=updated_at)
        export_transparency_checkpoint_state(path=state_path, state=current)
        return TransparencyCheckpointStateApplyResult(stored_state=stored, current_state=current, state_updated=True)
    finally:
        _close_lock(lock_fd)


def _export_state(*, path: Path, text: str) -> None:
    if path.is_symlink() or path.is_dir():
        raise TransparencyCheckpointStateValidationError(_VALIDATION_MESSAGE)
    temp_path: Path | None = None
    replaced = False
    dir_fd: int | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp") as tmp:
            temp_path = Path(tmp.name)
            tmp.write(text.rstrip("\n") + "\n")
            tmp.flush()
            os.fsync(tmp.fileno())
            os.chmod(temp_path, CHECKPOINT_STATE_FILE_MODE)
        os.replace(temp_path, path)
        replaced = True
        dir_fd = os.open(path.parent, os.O_RDONLY)
        os.fsync(dir_fd)
    except OSError as error:
        raise TransparencyCheckpointStateExportError(_EXPORT_MESSAGE) from error
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


def _open_lock(lock_path: Path) -> int:
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        if lock_path.is_symlink() or lock_path.is_dir():
            raise TransparencyCheckpointStateLockError(_LOCK_MESSAGE)
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, CHECKPOINT_STATE_FILE_MODE)
        os.chmod(lock_path, CHECKPOINT_STATE_FILE_MODE)
        return fd
    except TransparencyCheckpointStateLockError:
        raise
    except OSError as error:
        raise TransparencyCheckpointStateLockError(_LOCK_MESSAGE) from error


def _close_lock(fd: int) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


def _loads_no_duplicate_keys(text: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TransparencyCheckpointStateValidationError(_VALIDATION_MESSAGE)
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)


def _normalize_aware_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("datetime required")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone required")
    return value.astimezone(UTC)
