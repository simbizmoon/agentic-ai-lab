"""Persistent trust state for the active Root Ed25519 key."""

from __future__ import annotations

import base64
import binascii
import fcntl
import hmac
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.authentication_keyring import is_valid_key_id
from app.exceptions import (
    ActiveManifestTrustStateBlocksRootTransitionError,
    MissingRootTrustStateError,
    RootTransitionNotYetValidError,
    RootTrustStateAlreadyExistsError,
    RootTrustStateEpochError,
    RootTrustStateExportError,
    RootTrustStateLockError,
    RootTrustStateReadError,
    RootTrustStateValidationError,
)
from app.report_integrity import is_valid_sha256_digest
from app.root_signature_trust import (
    RAW_ED25519_PUBLIC_KEY_BYTES,
    TrustedRootSigningPublicKey,
    fingerprint_public_key,
)
from app.root_transition import (
    ROOT_TRANSITION_GENERATION,
    validate_root_transition_json,
    verify_root_transition,
)

ROOT_TRUST_STATE_VERSION = 1
ROOT_TRUST_STATE_TYPE = "audit_report_root_trust_state"
ROOT_TRUST_STATE_ENV_NAME = "AUDIT_REPORT_ROOT_TRUST_STATE_PATH"
MAX_ROOT_TRUST_STATE_BYTES = 64 * 1024
ROOT_STATE_FILE_MODE = 0o600

_READ_MESSAGE = "Failed to read the root trust state."
_VALIDATION_MESSAGE = "The root trust state is invalid."
_EXPORT_MESSAGE = "Failed to export the root trust state."
_LOCK_MESSAGE = "Failed to lock the root trust state."
_MISSING_MESSAGE = "The root trust state is missing."
_EXISTS_MESSAGE = "The root trust state already exists."
_EPOCH_MESSAGE = "The root transition epoch is invalid."
_NOT_YET_VALID_MESSAGE = "The root transition is not active for application."
_ACTIVE_MANIFEST_MESSAGE = "The active signing key manifest trust state must be retired before root transition."


class RootTrustStatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    state_version: Literal[ROOT_TRUST_STATE_VERSION]
    state_type: Literal[ROOT_TRUST_STATE_TYPE]
    current_root_epoch: int = Field(ge=1)
    current_root_key_id: str
    current_root_public_key_b64: str
    current_root_public_key_fingerprint: str
    last_transition_generation: int = Field(ge=0)
    last_transition_sha256: str | None
    updated_at: datetime

    @field_validator("current_root_key_id")
    @classmethod
    def _validate_key_id(cls, value: str) -> str:
        if not is_valid_key_id(value):
            raise ValueError("invalid key id")
        return value

    @field_validator("current_root_public_key_b64")
    @classmethod
    def _validate_public_key(cls, value: str) -> str:
        _decode_public_key_b64(value)
        return value

    @field_validator("current_root_public_key_fingerprint")
    @classmethod
    def _validate_fingerprint(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid fingerprint")
        return value

    @field_validator("last_transition_sha256")
    @classmethod
    def _validate_optional_digest(cls, value: str | None) -> str | None:
        if value is not None and not is_valid_sha256_digest(value):
            raise ValueError("invalid digest")
        return value

    @field_validator("updated_at")
    @classmethod
    def _validate_datetime(cls, value: datetime) -> datetime:
        return _normalize_aware_datetime(value)

    @model_validator(mode="after")
    def _validate_state(self) -> RootTrustStatePayload:
        public_key = _decode_public_key_b64(self.current_root_public_key_b64)
        if not hmac.compare_digest(self.current_root_public_key_fingerprint, fingerprint_public_key(public_key)):
            raise ValueError("fingerprint mismatch")
        if self.last_transition_generation == 0 and self.last_transition_sha256 is not None:
            raise ValueError("initial state must not have transition digest")
        if self.last_transition_generation > 0 and self.last_transition_sha256 is None:
            raise ValueError("transition digest required")
        return self


@dataclass(frozen=True)
class RootTransitionApplicationResult:
    previous_root_epoch: int
    next_root_epoch: int
    previous_root_key_id: str
    next_root_key_id: str
    transition_generation: int
    transition_sha256: str
    state_updated: bool


def root_trust_state_lock_path_for(state_path: Path) -> Path:
    if not isinstance(state_path, Path):
        raise TypeError("state_path must be a Path")
    return state_path.with_name(f"{state_path.name}.lock")


def load_root_trust_state(*, path: Path) -> RootTrustStatePayload | None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink():
        raise RootTrustStateValidationError(_VALIDATION_MESSAGE)
    if not path.exists():
        return None
    if path.is_dir() or not path.is_file():
        raise RootTrustStateValidationError(_VALIDATION_MESSAGE)
    try:
        if path.stat().st_size > MAX_ROOT_TRUST_STATE_BYTES:
            raise RootTrustStateValidationError(_VALIDATION_MESSAGE)
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise RootTrustStateReadError(_READ_MESSAGE) from error
    try:
        payload = _loads_no_duplicate_keys(text)
        if not isinstance(payload, dict):
            raise RootTrustStateValidationError(_VALIDATION_MESSAGE)
        return RootTrustStatePayload.model_validate_json(json.dumps(payload))
    except RootTrustStateValidationError:
        raise
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise RootTrustStateValidationError(_VALIDATION_MESSAGE) from error


def format_root_trust_state_json(state: RootTrustStatePayload) -> str:
    if not isinstance(state, RootTrustStatePayload):
        raise TypeError("state must be a RootTrustStatePayload")
    return json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=False)


def export_root_trust_state(*, path: Path, state: RootTrustStatePayload) -> None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if not isinstance(state, RootTrustStatePayload):
        raise TypeError("state must be a RootTrustStatePayload")
    if path.is_symlink() or path.is_dir():
        raise RootTrustStateValidationError(_VALIDATION_MESSAGE)
    text = format_root_trust_state_json(state).rstrip("\n") + "\n"
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
            os.chmod(temp_path, ROOT_STATE_FILE_MODE)
        os.replace(temp_path, path)
        replaced = True
        dir_fd = os.open(path.parent, os.O_RDONLY)
        os.fsync(dir_fd)
    except OSError as error:
        raise RootTrustStateExportError(_EXPORT_MESSAGE) from error
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


def build_initial_root_trust_state(
    *,
    root_public_key: TrustedRootSigningPublicKey,
    root_epoch: int,
    initialized_at: datetime,
) -> RootTrustStatePayload:
    if not isinstance(root_public_key, TrustedRootSigningPublicKey):
        raise TypeError("root_public_key must be a TrustedRootSigningPublicKey")
    if not isinstance(root_epoch, int) or isinstance(root_epoch, bool) or root_epoch < 1:
        raise RootTrustStateEpochError(_EPOCH_MESSAGE)
    initialized_at = _normalize_aware_datetime(initialized_at)
    return RootTrustStatePayload(
        state_version=ROOT_TRUST_STATE_VERSION,
        state_type=ROOT_TRUST_STATE_TYPE,
        current_root_epoch=root_epoch,
        current_root_key_id=root_public_key.key_id,
        current_root_public_key_b64=base64.b64encode(root_public_key.public_key_bytes).decode("ascii"),
        current_root_public_key_fingerprint=root_public_key.public_key_fingerprint,
        last_transition_generation=0,
        last_transition_sha256=None,
        updated_at=initialized_at,
    )


def trusted_root_public_key_from_state(state: RootTrustStatePayload) -> TrustedRootSigningPublicKey:
    if not isinstance(state, RootTrustStatePayload):
        raise TypeError("state must be a RootTrustStatePayload")
    return TrustedRootSigningPublicKey(
        key_id=state.current_root_key_id,
        public_key_bytes=_decode_public_key_b64(state.current_root_public_key_b64),
        public_key_fingerprint=state.current_root_public_key_fingerprint,
    )


def initialize_root_trust_state(
    *,
    path: Path,
    root_public_key: TrustedRootSigningPublicKey,
    root_epoch: int,
    initialized_at: datetime,
) -> RootTrustStatePayload:
    lock_path = root_trust_state_lock_path_for(path)
    lock_fd = _open_lock(lock_path)
    try:
        _lock_fd(lock_fd, exclusive=True)
        if load_root_trust_state(path=path) is not None:
            raise RootTrustStateAlreadyExistsError(_EXISTS_MESSAGE)
        state = build_initial_root_trust_state(
            root_public_key=root_public_key,
            root_epoch=root_epoch,
            initialized_at=initialized_at,
        )
        export_root_trust_state(path=path, state=state)
        return state
    finally:
        _close_lock(lock_fd)


def apply_root_transition(
    *,
    transition_path: Path,
    state_path: Path,
    application_time: datetime,
    active_manifest_state_path: Path | None,
) -> RootTransitionApplicationResult:
    if not isinstance(state_path, Path):
        raise TypeError("state_path must be a Path")
    application_time = _normalize_aware_datetime(application_time)
    lock_path = root_trust_state_lock_path_for(state_path)
    lock_fd = _open_lock(lock_path)
    try:
        _lock_fd(lock_fd, exclusive=True)
        current_state = load_root_trust_state(path=state_path)
        if current_state is None:
            raise MissingRootTrustStateError(_MISSING_MESSAGE)
        if active_manifest_state_path is not None and (
            active_manifest_state_path.exists() or active_manifest_state_path.is_symlink()
        ):
            raise ActiveManifestTrustStateBlocksRootTransitionError(_ACTIVE_MANIFEST_MESSAGE)
        current_root = trusted_root_public_key_from_state(current_state)
        result = verify_root_transition(
            transition_path=transition_path,
            current_root=current_root,
            current_root_epoch=current_state.current_root_epoch,
            verification_time=application_time,
        )
        if not result.is_active_for_application:
            raise RootTransitionNotYetValidError(_NOT_YET_VALID_MESSAGE)
        if result.next_root_epoch != current_state.current_root_epoch + 1:
            raise RootTrustStateEpochError(_EPOCH_MESSAGE)
        transition = validate_root_transition_json(transition_path.read_text(encoding="utf-8"))
        next_state = RootTrustStatePayload(
            state_version=ROOT_TRUST_STATE_VERSION,
            state_type=ROOT_TRUST_STATE_TYPE,
            current_root_epoch=result.next_root_epoch,
            current_root_key_id=result.next_root_key_id,
            current_root_public_key_b64=transition.next_root.public_key_b64,
            current_root_public_key_fingerprint=result.next_root_fingerprint,
            last_transition_generation=ROOT_TRANSITION_GENERATION,
            last_transition_sha256=result.transition_sha256,
            updated_at=application_time,
        )
        export_root_trust_state(path=state_path, state=next_state)
        return RootTransitionApplicationResult(
            previous_root_epoch=result.previous_root_epoch,
            next_root_epoch=result.next_root_epoch,
            previous_root_key_id=result.previous_root_key_id,
            next_root_key_id=result.next_root_key_id,
            transition_generation=result.transition_generation,
            transition_sha256=result.transition_sha256,
            state_updated=True,
        )
    finally:
        _close_lock(lock_fd)


def _open_lock(lock_path: Path) -> int:
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        if lock_path.is_symlink() or lock_path.is_dir():
            raise RootTrustStateLockError(_LOCK_MESSAGE)
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, ROOT_STATE_FILE_MODE)
        os.chmod(lock_path, ROOT_STATE_FILE_MODE)
        return fd
    except RootTrustStateLockError:
        raise
    except OSError as error:
        raise RootTrustStateLockError(_LOCK_MESSAGE) from error


def _lock_fd(fd: int, *, exclusive: bool) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
    except OSError as error:
        raise RootTrustStateLockError(_LOCK_MESSAGE) from error


def _close_lock(fd: int) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


def _loads_no_duplicate_keys(json_text: str) -> object:
    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RootTrustStateValidationError(_VALIDATION_MESSAGE)
            result[key] = value
        return result

    return json.loads(json_text, object_pairs_hook=hook)


def _decode_public_key_b64(value: object) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("invalid base64")
    try:
        public_key = base64.b64decode(value.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError, ValueError) as error:
        raise ValueError("invalid base64") from error
    if len(public_key) != RAW_ED25519_PUBLIC_KEY_BYTES:
        raise ValueError("invalid public key length")
    try:
        Ed25519PublicKey.from_public_bytes(public_key)
    except ValueError as error:
        raise ValueError("invalid public key") from error
    return public_key


def _normalize_aware_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("datetime required")  # noqa: TRY004
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone required")
    return value.astimezone(UTC)


def apply_root_transition_with_transparency(
    *,
    transition_path: Path,
    state_path: Path,
    application_time: datetime,
    active_manifest_state_path: Path | None,
    transparency_log_path: Path,
    transparency_state_path: Path,
    transparency_mode,
) -> RootTransitionApplicationResult:
    from app.transparency_log import (
        TransparencyLogMode,
        register_verified_artifact,
        require_transparency_entry,
        transparency_artifact_from_verified_root_transition,
        verify_transparency_log,
    )

    current_state = load_root_trust_state(path=state_path)
    if current_state is None:
        raise MissingRootTrustStateError(_MISSING_MESSAGE)
    verified = verify_root_transition(
        transition_path=transition_path,
        current_root=trusted_root_public_key_from_state(current_state),
        current_root_epoch=current_state.current_root_epoch,
        verification_time=application_time,
    )
    artifact = transparency_artifact_from_verified_root_transition(verified)
    mode = TransparencyLogMode(transparency_mode)
    if mode is TransparencyLogMode.REGISTER_IF_MISSING:
        register_verified_artifact(
            log_path=transparency_log_path,
            state_path=transparency_state_path,
            artifact=artifact,
            recorded_at=application_time,
        )
    else:
        verification = verify_transparency_log(
            log_path=transparency_log_path,
            state_path=transparency_state_path,
        )
        require_transparency_entry(verification_result=verification, artifact=artifact)
    return apply_root_transition(
        transition_path=transition_path,
        state_path=state_path,
        application_time=application_time,
        active_manifest_state_path=active_manifest_state_path,
    )
