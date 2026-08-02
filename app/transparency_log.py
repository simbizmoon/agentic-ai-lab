"""Append-only local transparency log for verified trust artifacts."""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

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
    RootTransitionTransparencyConflictError,
    SigningKeyManifestTransparencyConflictError,
    TransparencyLogConflictError,
    TransparencyLogDivergenceError,
    TransparencyLogReadError,
    TransparencyLogStateMismatchError,
    TransparencyLogValidationError,
    TransparencyLogWriteError,
    UnloggedRootTransitionError,
    UnloggedSigningKeyManifestError,
)
from app.report_integrity import is_valid_sha256_digest
from app.transparency_log_state import (
    build_transparency_log_state,
    export_transparency_log_state,
    load_transparency_log_state,
)

TRANSPARENCY_LOG_VERSION = 1
TRANSPARENCY_LOG_ENTRY_VERSION = 1
TRANSPARENCY_LOG_ENTRY_TYPE = "audit_report_transparency_log_entry"
TRANSPARENCY_LOG_ENTRY_HASH_DOMAIN = b"agentic-ai-lab:transparency-log-entry:sha256:v1"
MAX_TRANSPARENCY_LOG_BYTES = 20 * 1024 * 1024
MAX_TRANSPARENCY_LOG_ENTRIES = 100_000
MAX_TRANSPARENCY_ENTRY_BYTES = 64 * 1024
TRANSPARENCY_LOG_PATH_ENV_NAME = "AUDIT_REPORT_TRANSPARENCY_LOG_PATH"
TRANSPARENCY_LOG_STATE_PATH_ENV_NAME = "AUDIT_REPORT_TRANSPARENCY_LOG_STATE_PATH"
TRANSPARENCY_FILE_MODE = 0o600

_READ_MESSAGE = "Failed to read the transparency log."
_VALIDATION_MESSAGE = "The transparency log is invalid."
_WRITE_MESSAGE = "Failed to append to the transparency log."
_CONFLICT_MESSAGE = "The transparency log already contains a conflicting artifact."
_UNLOGGED_ROOT_MESSAGE = "The root transition is not registered in the transparency log."
_UNLOGGED_MANIFEST_MESSAGE = "The signing key manifest is not registered in the transparency log."
_DIVERGENCE_MESSAGE = "The transparency log and state do not match."


class TransparencyLogEntryType(str, Enum):
    ROOT_TRANSITION = "root_transition"
    SIGNING_KEY_MANIFEST = "signing_key_manifest"


class TransparencyLogMode(str, Enum):
    REQUIRE_EXISTING = "require_existing"
    REGISTER_IF_MISSING = "register_if_missing"


class TransparencyLogModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class RootTransitionLogMetadata(TransparencyLogModel):
    previous_root_epoch: int = Field(ge=1)
    previous_root_key_id: str
    previous_root_fingerprint: str
    next_root_epoch: int = Field(ge=1)
    next_root_key_id: str
    next_root_fingerprint: str
    transition_generation: int = Field(ge=1)
    issued_at: datetime
    valid_from: datetime
    valid_until: datetime

    @field_validator("previous_root_key_id", "next_root_key_id")
    @classmethod
    def _validate_key_id(cls, value: str) -> str:
        if not is_valid_key_id(value):
            raise ValueError("invalid key id")
        return value

    @field_validator("previous_root_fingerprint", "next_root_fingerprint")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid digest")
        return value

    @field_validator("issued_at", "valid_from", "valid_until")
    @classmethod
    def _validate_datetime(cls, value: datetime) -> datetime:
        return _normalize_aware_datetime(value)


class SigningKeyManifestLogMetadata(TransparencyLogModel):
    root_key_id: str
    root_key_fingerprint: str
    manifest_generation: int = Field(ge=1)
    issued_at: datetime
    valid_from: datetime
    valid_until: datetime
    active_signing_key_id: str
    key_count: int = Field(ge=1)

    @field_validator("root_key_id", "active_signing_key_id")
    @classmethod
    def _validate_key_id(cls, value: str) -> str:
        if not is_valid_key_id(value):
            raise ValueError("invalid key id")
        return value

    @field_validator("root_key_fingerprint")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid digest")
        return value

    @field_validator("issued_at", "valid_from", "valid_until")
    @classmethod
    def _validate_datetime(cls, value: datetime) -> datetime:
        return _normalize_aware_datetime(value)


class TransparencyLogEntryUnsignedPayload(TransparencyLogModel):
    entry_version: Literal[TRANSPARENCY_LOG_ENTRY_VERSION]
    entry_type: Literal[TRANSPARENCY_LOG_ENTRY_TYPE]
    sequence: int = Field(ge=1)
    recorded_at: datetime
    artifact_type: TransparencyLogEntryType
    artifact_version: int = Field(ge=1)
    artifact_identifier: str = Field(min_length=1, max_length=512)
    artifact_sha256: str
    previous_entry_hash: str | None
    metadata: RootTransitionLogMetadata | SigningKeyManifestLogMetadata

    @field_validator("recorded_at")
    @classmethod
    def _validate_recorded_at(cls, value: datetime) -> datetime:
        return _normalize_aware_datetime(value)

    @field_validator("artifact_sha256", "previous_entry_hash")
    @classmethod
    def _validate_digest(cls, value: str | None) -> str | None:
        if value is not None and not is_valid_sha256_digest(value):
            raise ValueError("invalid digest")
        return value

    @model_validator(mode="after")
    def _validate_metadata(self) -> TransparencyLogEntryUnsignedPayload:
        if self.artifact_type is TransparencyLogEntryType.ROOT_TRANSITION:
            if not isinstance(self.metadata, RootTransitionLogMetadata):
                raise ValueError("invalid metadata")
            expected = _root_transition_identifier(self.metadata)
        else:
            if not isinstance(self.metadata, SigningKeyManifestLogMetadata):
                raise ValueError("invalid metadata")
            expected = _signing_key_manifest_identifier(self.metadata)
        if self.artifact_identifier != expected:
            raise ValueError("artifact identifier mismatch")
        return self


class TransparencyLogEntryPayload(TransparencyLogEntryUnsignedPayload):
    entry_hash: str

    @field_validator("entry_hash")
    @classmethod
    def _validate_entry_hash(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid entry hash")
        return value


@dataclass(frozen=True)
class VerifiedTransparencyArtifact:
    artifact_type: TransparencyLogEntryType
    artifact_version: int
    artifact_identifier: str
    artifact_sha256: str
    metadata: RootTransitionLogMetadata | SigningKeyManifestLogMetadata


@dataclass(frozen=True)
class TransparencyLogInclusionResult:
    sequence: int
    entry_hash: str
    recorded_at: datetime
    artifact_type: TransparencyLogEntryType
    artifact_identifier: str
    artifact_sha256: str


@dataclass(frozen=True)
class TransparencyLogVerificationResult:
    log_version: int
    entry_count: int
    first_sequence: int | None
    last_sequence: int | None
    last_entry_hash: str | None
    root_transition_count: int
    signing_key_manifest_count: int
    entries_by_identifier: Mapping[str, TransparencyLogInclusionResult]


@dataclass(frozen=True)
class TransparencyLogAppendResult:
    inclusion: TransparencyLogInclusionResult
    entry_registered: bool
    verification_result: TransparencyLogVerificationResult


def canonicalize_transparency_log_unsigned_entry(entry: TransparencyLogEntryUnsignedPayload) -> bytes:
    if not isinstance(entry, TransparencyLogEntryUnsignedPayload):
        raise TypeError("entry must be a TransparencyLogEntryUnsignedPayload")
    return json.dumps(
        entry.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def calculate_transparency_entry_hash(entry: TransparencyLogEntryUnsignedPayload) -> str:
    digest = hashlib.sha256()
    digest.update(TRANSPARENCY_LOG_ENTRY_HASH_DOMAIN)
    digest.update(b"\0")
    digest.update(canonicalize_transparency_log_unsigned_entry(entry))
    return digest.hexdigest()


def transparency_artifact_from_verified_root_transition(result: object) -> VerifiedTransparencyArtifact:
    metadata = RootTransitionLogMetadata(
        previous_root_epoch=result.previous_root_epoch,
        previous_root_key_id=result.previous_root_key_id,
        previous_root_fingerprint=result.previous_root_fingerprint,
        next_root_epoch=result.next_root_epoch,
        next_root_key_id=result.next_root_key_id,
        next_root_fingerprint=result.next_root_fingerprint,
        transition_generation=result.transition_generation,
        issued_at=result.issued_at,
        valid_from=result.valid_from,
        valid_until=result.valid_until,
    )
    return VerifiedTransparencyArtifact(
        artifact_type=TransparencyLogEntryType.ROOT_TRANSITION,
        artifact_version=result.transition_version,
        artifact_identifier=_root_transition_identifier(metadata),
        artifact_sha256=result.transition_sha256,
        metadata=metadata,
    )


def transparency_artifact_from_verified_signing_key_manifest(result: object) -> VerifiedTransparencyArtifact:
    metadata = SigningKeyManifestLogMetadata(
        root_key_id=result.root_key_id,
        root_key_fingerprint=result.root_key_fingerprint,
        manifest_generation=result.generation,
        issued_at=result.issued_at,
        valid_from=result.valid_from,
        valid_until=result.valid_until,
        active_signing_key_id=result.active_key_id,
        key_count=result.key_count,
    )
    return VerifiedTransparencyArtifact(
        artifact_type=TransparencyLogEntryType.SIGNING_KEY_MANIFEST,
        artifact_version=result.manifest_version,
        artifact_identifier=_signing_key_manifest_identifier(metadata),
        artifact_sha256=result.manifest_sha256,
        metadata=metadata,
    )


def transparency_log_lock_path_for(log_path: Path) -> Path:
    if not isinstance(log_path, Path):
        raise TypeError("log_path must be a Path")
    return log_path.with_name(f"{log_path.name}.lock")


def verify_transparency_log(*, log_path: Path, state_path: Path) -> TransparencyLogVerificationResult:
    lock_fd = _open_lock(transparency_log_lock_path_for(log_path))
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_SH)
        return _verify_transparency_log_unlocked(log_path=log_path, state_path=state_path)
    except OSError as error:
        raise TransparencyLogReadError(_READ_MESSAGE) from error
    finally:
        _close_lock(lock_fd)


def require_transparency_entry(
    *,
    verification_result: TransparencyLogVerificationResult,
    artifact: VerifiedTransparencyArtifact,
) -> TransparencyLogInclusionResult:
    inclusion = verification_result.entries_by_identifier.get(artifact.artifact_identifier)
    if inclusion is None:
        if artifact.artifact_type is TransparencyLogEntryType.ROOT_TRANSITION:
            raise UnloggedRootTransitionError(_UNLOGGED_ROOT_MESSAGE)
        raise UnloggedSigningKeyManifestError(_UNLOGGED_MANIFEST_MESSAGE)
    if inclusion.artifact_type is not artifact.artifact_type or not hmac.compare_digest(
        inclusion.artifact_sha256,
        artifact.artifact_sha256,
    ):
        if artifact.artifact_type is TransparencyLogEntryType.ROOT_TRANSITION:
            raise RootTransitionTransparencyConflictError(_CONFLICT_MESSAGE)
        raise SigningKeyManifestTransparencyConflictError(_CONFLICT_MESSAGE)
    return inclusion


def register_verified_artifact(
    *,
    log_path: Path,
    state_path: Path,
    artifact: VerifiedTransparencyArtifact,
    recorded_at: datetime,
) -> TransparencyLogAppendResult:
    if not isinstance(log_path, Path) or not isinstance(state_path, Path):
        raise TypeError("log_path and state_path must be Path")
    if not isinstance(artifact, VerifiedTransparencyArtifact):
        raise TypeError("artifact must be a VerifiedTransparencyArtifact")
    recorded_at = _normalize_aware_datetime(recorded_at)
    lock_fd = _open_lock(transparency_log_lock_path_for(log_path))
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        verification = _verify_transparency_log_unlocked(log_path=log_path, state_path=state_path)
        existing = verification.entries_by_identifier.get(artifact.artifact_identifier)
        if existing is not None:
            inclusion = require_transparency_entry(verification_result=verification, artifact=artifact)
            return TransparencyLogAppendResult(inclusion=inclusion, entry_registered=False, verification_result=verification)
        if verification.entry_count >= MAX_TRANSPARENCY_LOG_ENTRIES:
            raise TransparencyLogValidationError(_VALIDATION_MESSAGE)
        sequence = verification.entry_count + 1
        unsigned = TransparencyLogEntryUnsignedPayload(
            entry_version=TRANSPARENCY_LOG_ENTRY_VERSION,
            entry_type=TRANSPARENCY_LOG_ENTRY_TYPE,
            sequence=sequence,
            recorded_at=recorded_at,
            artifact_type=artifact.artifact_type,
            artifact_version=artifact.artifact_version,
            artifact_identifier=artifact.artifact_identifier,
            artifact_sha256=artifact.artifact_sha256,
            previous_entry_hash=verification.last_entry_hash,
            metadata=artifact.metadata,
        )
        entry = TransparencyLogEntryPayload(**unsigned.model_dump(), entry_hash=calculate_transparency_entry_hash(unsigned))
        line = json.dumps(entry.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")) + "\n"
        if len(line.encode("utf-8")) > MAX_TRANSPARENCY_ENTRY_BYTES:
            raise TransparencyLogValidationError(_VALIDATION_MESSAGE)
        _append_log_line(log_path=log_path, line=line)
        export_transparency_log_state(
            path=state_path,
            state=build_transparency_log_state(entry=entry, updated_at=recorded_at),
        )
        verification_after = _verify_transparency_log_unlocked(log_path=log_path, state_path=state_path)
        inclusion = require_transparency_entry(verification_result=verification_after, artifact=artifact)
        return TransparencyLogAppendResult(inclusion=inclusion, entry_registered=True, verification_result=verification_after)
    except (
        RootTransitionTransparencyConflictError,
        SigningKeyManifestTransparencyConflictError,
        TransparencyLogConflictError,
    ):
        raise
    except OSError as error:
        raise TransparencyLogWriteError(_WRITE_MESSAGE) from error
    finally:
        _close_lock(lock_fd)


def _verify_transparency_log_unlocked(*, log_path: Path, state_path: Path) -> TransparencyLogVerificationResult:
    if not isinstance(log_path, Path) or not isinstance(state_path, Path):
        raise TypeError("log_path and state_path must be Path")
    state = load_transparency_log_state(path=state_path)
    if log_path.is_symlink() or log_path.is_dir():
        raise TransparencyLogValidationError(_VALIDATION_MESSAGE)
    if not log_path.exists():
        if state is not None:
            raise TransparencyLogDivergenceError(_DIVERGENCE_MESSAGE)
        return _empty_result()
    if state is None:
        raise TransparencyLogDivergenceError(_DIVERGENCE_MESSAGE)
    try:
        if log_path.stat().st_size > MAX_TRANSPARENCY_LOG_BYTES:
            raise TransparencyLogValidationError(_VALIDATION_MESSAGE)
    except OSError as error:
        raise TransparencyLogReadError(_READ_MESSAGE) from error

    entries: dict[str, TransparencyLogInclusionResult] = {}
    previous_hash: str | None = None
    root_count = 0
    manifest_count = 0
    sequence = 0
    try:
        with log_path.open("rb") as file_obj:
            for raw_line in file_obj:
                if not raw_line.endswith(b"\n") or raw_line.strip() == b"":
                    raise TransparencyLogValidationError(_VALIDATION_MESSAGE)
                if len(raw_line) > MAX_TRANSPARENCY_ENTRY_BYTES:
                    raise TransparencyLogValidationError(_VALIDATION_MESSAGE)
                sequence += 1
                if sequence > MAX_TRANSPARENCY_LOG_ENTRIES:
                    raise TransparencyLogValidationError(_VALIDATION_MESSAGE)
                entry = _parse_entry(raw_line.decode("utf-8").rstrip("\n"))
                if entry.sequence != sequence:
                    raise TransparencyLogValidationError(_VALIDATION_MESSAGE)
                if sequence == 1 and entry.previous_entry_hash is not None:
                    raise TransparencyLogValidationError(_VALIDATION_MESSAGE)
                if sequence > 1 and entry.previous_entry_hash != previous_hash:
                    raise TransparencyLogValidationError(_VALIDATION_MESSAGE)
                unsigned = TransparencyLogEntryUnsignedPayload(**entry.model_dump(exclude={"entry_hash"}))
                calculated = calculate_transparency_entry_hash(unsigned)
                if not hmac.compare_digest(entry.entry_hash, calculated):
                    raise TransparencyLogValidationError(_VALIDATION_MESSAGE)
                if entry.artifact_identifier in entries:
                    raise TransparencyLogConflictError(_CONFLICT_MESSAGE)
                inclusion = TransparencyLogInclusionResult(
                    sequence=entry.sequence,
                    entry_hash=entry.entry_hash,
                    recorded_at=entry.recorded_at,
                    artifact_type=entry.artifact_type,
                    artifact_identifier=entry.artifact_identifier,
                    artifact_sha256=entry.artifact_sha256,
                )
                entries[entry.artifact_identifier] = inclusion
                if entry.artifact_type is TransparencyLogEntryType.ROOT_TRANSITION:
                    root_count += 1
                else:
                    manifest_count += 1
                previous_hash = entry.entry_hash
    except UnicodeDecodeError as error:
        raise TransparencyLogValidationError(_VALIDATION_MESSAGE) from error
    except OSError as error:
        raise TransparencyLogReadError(_READ_MESSAGE) from error

    if sequence == 0:
        raise TransparencyLogDivergenceError(_DIVERGENCE_MESSAGE)
    if state.last_sequence != sequence or state.last_entry_hash != previous_hash:
        raise TransparencyLogStateMismatchError(_DIVERGENCE_MESSAGE)
    return TransparencyLogVerificationResult(
        log_version=TRANSPARENCY_LOG_VERSION,
        entry_count=sequence,
        first_sequence=1,
        last_sequence=sequence,
        last_entry_hash=previous_hash,
        root_transition_count=root_count,
        signing_key_manifest_count=manifest_count,
        entries_by_identifier=MappingProxyType(entries),
    )


def _empty_result() -> TransparencyLogVerificationResult:
    return TransparencyLogVerificationResult(
        log_version=TRANSPARENCY_LOG_VERSION,
        entry_count=0,
        first_sequence=None,
        last_sequence=None,
        last_entry_hash=None,
        root_transition_count=0,
        signing_key_manifest_count=0,
        entries_by_identifier=MappingProxyType({}),
    )


def _parse_entry(text: str) -> TransparencyLogEntryPayload:
    try:
        payload = _loads_no_duplicate_keys(text)
        if not isinstance(payload, dict):
            raise TransparencyLogValidationError(_VALIDATION_MESSAGE)
        return TransparencyLogEntryPayload.model_validate_json(json.dumps(payload))
    except TransparencyLogValidationError:
        raise
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise TransparencyLogValidationError(_VALIDATION_MESSAGE) from error


def _append_log_line(*, log_path: Path, line: str) -> None:
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if log_path.is_symlink() or log_path.is_dir():
            raise TransparencyLogValidationError(_VALIDATION_MESSAGE)
        current_size = log_path.stat().st_size if log_path.exists() else 0
        if current_size + len(line.encode("utf-8")) > MAX_TRANSPARENCY_LOG_BYTES:
            raise TransparencyLogValidationError(_VALIDATION_MESSAGE)
        with log_path.open("a", encoding="utf-8") as file_obj:
            os.chmod(log_path, TRANSPARENCY_FILE_MODE)
            file_obj.write(line)
            file_obj.flush()
            os.fsync(file_obj.fileno())
    except OSError as error:
        raise TransparencyLogWriteError(_WRITE_MESSAGE) from error


def _open_lock(lock_path: Path) -> int:
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        if lock_path.is_symlink() or lock_path.is_dir():
            raise TransparencyLogWriteError(_WRITE_MESSAGE)
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, TRANSPARENCY_FILE_MODE)
        os.chmod(lock_path, TRANSPARENCY_FILE_MODE)
        return fd
    except OSError as error:
        raise TransparencyLogWriteError(_WRITE_MESSAGE) from error


def _close_lock(fd: int) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


def _root_transition_identifier(metadata: RootTransitionLogMetadata) -> str:
    return (
        "root-transition:"
        f"{metadata.previous_root_epoch}:"
        f"{metadata.next_root_epoch}:"
        f"{metadata.transition_generation}"
    )


def _signing_key_manifest_identifier(metadata: SigningKeyManifestLogMetadata) -> str:
    return f"signing-key-manifest:{metadata.root_key_fingerprint}:{metadata.manifest_generation}"


def _loads_no_duplicate_keys(text: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TransparencyLogValidationError(_VALIDATION_MESSAGE)
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)


def _normalize_aware_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("datetime required")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone required")
    return value.astimezone(UTC)
