"""Local rollback protection state for signed archive key manifests."""

from __future__ import annotations

import fcntl
import hmac
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from app.authentication_keyring import is_valid_key_id
from app.exceptions import (
    ManifestTrustStateExportError,
    ManifestTrustStateGenerationConflictError,
    ManifestTrustStateLockError,
    ManifestTrustStatePathError,
    ManifestTrustStateReadError,
    ManifestTrustStateRootMismatchError,
    ManifestTrustStateValidationError,
    MissingManifestTrustStateError,
    SigningKeyManifestRollbackError,
)
from app.report_integrity import is_valid_sha256_digest

if TYPE_CHECKING:
    from app.signing_key_manifest import VerifiedSigningKeyManifest

MANIFEST_TRUST_STATE_VERSION = 1
MANIFEST_TRUST_STATE_TYPE = "archive_signing_key_manifest_trust_state"
MAX_MANIFEST_TRUST_STATE_BYTES = 64 * 1024
MANIFEST_TRUST_STATE_ENV_NAME = "AUDIT_REPORT_SIGNING_KEY_MANIFEST_STATE_PATH"
STATE_FILE_MODE = 0o600

_READ_MESSAGE = "Failed to read the signing key manifest trust state."
_VALIDATION_MESSAGE = "The signing key manifest trust state is invalid."
_EXPORT_MESSAGE = "Failed to export the signing key manifest trust state."
_LOCK_MESSAGE = "Failed to lock the signing key manifest trust state."
_MISSING_MESSAGE = "The signing key manifest trust state is missing."
_PATH_MESSAGE = "The signing key manifest trust state path is required."
_ROOT_MISMATCH_MESSAGE = "The signing key manifest trust state belongs to a different root key."
_GENERATION_CONFLICT_MESSAGE = "The signing key manifest generation conflicts with stored state."
_ROLLBACK_MESSAGE = "The archive signing key manifest generation is too old."


class ManifestTrustStateMode(str, Enum):
    READ_ONLY = "read_only"
    UPDATE = "update"


class ManifestTrustStatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    state_version: Literal[MANIFEST_TRUST_STATE_VERSION]
    state_type: Literal[MANIFEST_TRUST_STATE_TYPE]
    root_key_id: str
    root_key_fingerprint: str
    highest_generation: int = Field(ge=1)
    manifest_sha256: str
    manifest_issued_at: datetime
    verified_at: datetime

    @field_validator("root_key_id")
    @classmethod
    def _validate_key_id(cls, value: str) -> str:
        if not is_valid_key_id(value):
            raise ValueError("invalid key id")
        return value

    @field_validator("root_key_fingerprint", "manifest_sha256")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid sha256")
        return value

    @field_validator("manifest_issued_at", "verified_at")
    @classmethod
    def _validate_datetime(cls, value: datetime) -> datetime:
        return _normalize_aware_datetime(value)


@dataclass(frozen=True)
class ManifestTrustStateDecision:
    stored_state: ManifestTrustStatePayload | None
    effective_minimum_generation: int
    should_update: bool
    state_updated: bool


def manifest_trust_state_lock_path_for(state_path: Path) -> Path:
    if not isinstance(state_path, Path):
        raise TypeError("state_path must be a Path")
    return state_path.with_name(f"{state_path.name}.lock")


def load_manifest_trust_state(*, path: Path) -> ManifestTrustStatePayload | None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink():
        raise ManifestTrustStateValidationError(_VALIDATION_MESSAGE)
    if not path.exists():
        return None
    if path.is_dir() or not path.is_file():
        raise ManifestTrustStateValidationError(_VALIDATION_MESSAGE)
    try:
        if path.stat().st_size > MAX_MANIFEST_TRUST_STATE_BYTES:
            raise ManifestTrustStateValidationError(_VALIDATION_MESSAGE)
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ManifestTrustStateReadError(_READ_MESSAGE) from error
    try:
        payload = _loads_no_duplicate_keys(text)
        if not isinstance(payload, dict):
            raise ManifestTrustStateValidationError(_VALIDATION_MESSAGE)
        return ManifestTrustStatePayload.model_validate_json(json.dumps(payload))
    except ManifestTrustStateValidationError:
        raise
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise ManifestTrustStateValidationError(_VALIDATION_MESSAGE) from error


def format_manifest_trust_state_json(state: ManifestTrustStatePayload) -> str:
    if not isinstance(state, ManifestTrustStatePayload):
        raise TypeError("state must be a ManifestTrustStatePayload")
    return json.dumps(
        state.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    )


def export_manifest_trust_state(*, path: Path, state: ManifestTrustStatePayload) -> None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if not isinstance(state, ManifestTrustStatePayload):
        raise TypeError("state must be a ManifestTrustStatePayload")
    if path.is_symlink() or path.is_dir():
        raise ManifestTrustStateValidationError(_VALIDATION_MESSAGE)

    text = format_manifest_trust_state_json(state).rstrip("\n") + "\n"
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
            os.chmod(temp_path, STATE_FILE_MODE)
        os.replace(temp_path, path)
        replaced = True
        dir_fd = os.open(path.parent, os.O_RDONLY)
        os.fsync(dir_fd)
    except OSError as error:
        raise ManifestTrustStateExportError(_EXPORT_MESSAGE) from error
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


def build_manifest_trust_state(
    *,
    verified_manifest: VerifiedSigningKeyManifest,
    verified_at: datetime,
) -> ManifestTrustStatePayload:
    _validate_verified_manifest(verified_manifest)
    verified_at = _normalize_aware_datetime(verified_at)
    result = verified_manifest.result
    return ManifestTrustStatePayload(
        state_version=MANIFEST_TRUST_STATE_VERSION,
        state_type=MANIFEST_TRUST_STATE_TYPE,
        root_key_id=result.root_key_id,
        root_key_fingerprint=result.root_key_fingerprint,
        highest_generation=result.generation,
        manifest_sha256=result.manifest_sha256,
        manifest_issued_at=result.issued_at,
        verified_at=verified_at,
    )


def evaluate_manifest_trust_state(
    *,
    verified_manifest: VerifiedSigningKeyManifest,
    stored_state: ManifestTrustStatePayload | None,
    configured_minimum_generation: int,
) -> ManifestTrustStateDecision:
    _validate_verified_manifest(verified_manifest)
    configured_minimum_generation = _validate_generation(configured_minimum_generation)
    result = verified_manifest.result
    stored_generation = stored_state.highest_generation if stored_state is not None else None
    effective_minimum = max(
        configured_minimum_generation,
        stored_generation if stored_generation is not None else configured_minimum_generation,
    )
    if result.generation < effective_minimum:
        raise SigningKeyManifestRollbackError(_ROLLBACK_MESSAGE)
    if stored_state is None:
        return ManifestTrustStateDecision(
            stored_state=None,
            effective_minimum_generation=effective_minimum,
            should_update=True,
            state_updated=False,
        )
    if result.root_key_id != stored_state.root_key_id:
        raise ManifestTrustStateRootMismatchError(_ROOT_MISMATCH_MESSAGE)
    if not hmac.compare_digest(result.root_key_fingerprint, stored_state.root_key_fingerprint):
        raise ManifestTrustStateRootMismatchError(_ROOT_MISMATCH_MESSAGE)
    if result.generation == stored_state.highest_generation:
        if not hmac.compare_digest(result.manifest_sha256, stored_state.manifest_sha256):
            raise ManifestTrustStateGenerationConflictError(_GENERATION_CONFLICT_MESSAGE)
        return ManifestTrustStateDecision(
            stored_state=stored_state,
            effective_minimum_generation=effective_minimum,
            should_update=False,
            state_updated=False,
        )
    return ManifestTrustStateDecision(
        stored_state=stored_state,
        effective_minimum_generation=effective_minimum,
        should_update=True,
        state_updated=False,
    )


def apply_manifest_trust_state(
    *,
    verified_manifest: VerifiedSigningKeyManifest,
    state_path: Path | None,
    verified_at: datetime,
    configured_minimum_generation: int = 1,
    mode: ManifestTrustStateMode = ManifestTrustStateMode.UPDATE,
    require_existing_state: bool = False,
) -> ManifestTrustStateDecision:
    _validate_verified_manifest(verified_manifest)
    verified_at = _normalize_aware_datetime(verified_at)
    mode = _normalize_mode(mode)
    if state_path is None:
        if require_existing_state:
            raise MissingManifestTrustStateError(_MISSING_MESSAGE)
        if mode is ManifestTrustStateMode.UPDATE:
            raise ManifestTrustStatePathError(_PATH_MESSAGE)
        return evaluate_manifest_trust_state(
            verified_manifest=verified_manifest,
            stored_state=None,
            configured_minimum_generation=configured_minimum_generation,
        )

    if not isinstance(state_path, Path):
        raise TypeError("state_path must be a Path")
    lock_path = manifest_trust_state_lock_path_for(state_path)
    if lock_path.is_symlink() or lock_path.is_dir():
        raise ManifestTrustStateLockError(_LOCK_MESSAGE)

    lock_fd: int | None = None
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, STATE_FILE_MODE)
        os.chmod(lock_path, STATE_FILE_MODE)
        fcntl.flock(
            lock_fd,
            fcntl.LOCK_SH if mode is ManifestTrustStateMode.READ_ONLY else fcntl.LOCK_EX,
        )
        stored_state = load_manifest_trust_state(path=state_path)
        if require_existing_state and stored_state is None:
            raise MissingManifestTrustStateError(_MISSING_MESSAGE)
        decision = evaluate_manifest_trust_state(
            verified_manifest=verified_manifest,
            stored_state=stored_state,
            configured_minimum_generation=configured_minimum_generation,
        )
        if mode is ManifestTrustStateMode.UPDATE and decision.should_update:
            new_state = build_manifest_trust_state(
                verified_manifest=verified_manifest,
                verified_at=verified_at,
            )
            export_manifest_trust_state(path=state_path, state=new_state)
            return ManifestTrustStateDecision(
                stored_state=decision.stored_state,
                effective_minimum_generation=decision.effective_minimum_generation,
                should_update=decision.should_update,
                state_updated=True,
            )
        return decision
    except (ManifestTrustStateValidationError, ManifestTrustStateReadError, ManifestTrustStateExportError, MissingManifestTrustStateError, ManifestTrustStateRootMismatchError, ManifestTrustStateGenerationConflictError, SigningKeyManifestRollbackError):
        raise
    except OSError as error:
        raise ManifestTrustStateLockError(_LOCK_MESSAGE) from error
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(lock_fd)
            except OSError:
                pass


def _validate_verified_manifest(value: object) -> None:
    if not hasattr(value, "result") or not hasattr(value, "trust_store"):
        raise TypeError("verified_manifest must be a VerifiedSigningKeyManifest")


def _normalize_mode(value: ManifestTrustStateMode) -> ManifestTrustStateMode:
    if isinstance(value, ManifestTrustStateMode):
        return value
    try:
        return ManifestTrustStateMode(value)
    except ValueError as error:
        raise ValueError("mode must be a ManifestTrustStateMode") from error


def _validate_generation(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ManifestTrustStateValidationError(_VALIDATION_MESSAGE)
    return value


def _normalize_aware_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ManifestTrustStateValidationError(_VALIDATION_MESSAGE)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ManifestTrustStateValidationError(_VALIDATION_MESSAGE)
    return value.astimezone(UTC)


def _loads_no_duplicate_keys(text: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)
