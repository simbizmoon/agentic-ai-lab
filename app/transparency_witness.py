"""Local Ed25519 witness statements for signed transparency checkpoints."""

from __future__ import annotations

import base64
import binascii
import fcntl
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.exceptions import (
    TransparencyWitnessConfigurationError,
    TransparencyWitnessRollbackError,
    TransparencyWitnessSignatureError,
    TransparencyWitnessSplitViewError,
    TransparencyWitnessStateError,
)
from app.report_integrity import is_valid_sha256_digest
from app.transparency_checkpoint import (
    TransparencyCheckpointVerificationMode,
    TransparencyCheckpointVerificationResult,
    verify_checkpoint_consistency_proof,
    verify_transparency_checkpoint,
)
from app.transparency_merkle import (
    load_transparency_consistency_proof,
    transparency_consistency_proof_digest,
)
from app.transparency_witness_trust import (
    RAW_WITNESS_PUBLIC_KEY_BYTES,
    RevokedWitnessPolicy,
    TransparencyWitnessTrustStorePayload,
    ensure_witness_trusted_for_verification,
    is_valid_witness_id,
    normalize_aware_datetime,
)

TRANSPARENCY_WITNESS_STATEMENT_VERSION = 1
TRANSPARENCY_WITNESS_STATEMENT_TYPE = "audit_report_transparency_witness_statement"
TRANSPARENCY_WITNESS_SIGNATURE_DOMAIN = b"agentic-ai-lab:transparency-witness-statement:ed25519:v1"
TRANSPARENCY_WITNESS_SIGNATURE_ALGORITHM = "Ed25519"

TRANSPARENCY_WITNESS_PRIVATE_KEY_ENV_NAME = "AUDIT_REPORT_TRANSPARENCY_WITNESS_ED25519_PRIVATE_KEY_B64"
TRANSPARENCY_WITNESS_PUBLIC_KEY_ENV_NAME = "AUDIT_REPORT_TRANSPARENCY_WITNESS_ED25519_PUBLIC_KEY_B64"
TRANSPARENCY_WITNESS_ID_ENV_NAME = "AUDIT_REPORT_TRANSPARENCY_WITNESS_ID"
RAW_WITNESS_PRIVATE_KEY_BYTES = 32
RAW_WITNESS_SIGNATURE_BYTES = 64

TRANSPARENCY_WITNESS_STATE_VERSION = 1
TRANSPARENCY_WITNESS_STATE_TYPE = "audit_report_transparency_witness_state"
MAX_TRANSPARENCY_WITNESS_STATE_BYTES = 64 * 1024
MAX_TRANSPARENCY_WITNESS_STATEMENT_BYTES = 128 * 1024
TRANSPARENCY_WITNESS_FILE_MODE = 0o600
MAX_WITNESS_CLOCK_SKEW = timedelta(minutes=5)

_CONFIG_MESSAGE = "The transparency witness key is not configured safely."
_SIGNATURE_MESSAGE = "The transparency witness statement is invalid."
_STATE_MESSAGE = "The transparency witness state could not be verified or updated safely."
_ROLLBACK_MESSAGE = "The transparency witness checkpoint would roll back tree size."
_SPLIT_MESSAGE = "The transparency witness observed conflicting checkpoint roots."


class _WitnessModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class TransparencyWitnessStatementPayload(_WitnessModel):
    statement_version: Literal[TRANSPARENCY_WITNESS_STATEMENT_VERSION]
    statement_type: Literal[TRANSPARENCY_WITNESS_STATEMENT_TYPE]
    log_id: str = Field(min_length=1, max_length=128)
    witness_id: str = Field(min_length=1, max_length=128)
    checkpoint_sha256: str
    tree_size: int = Field(ge=1)
    root_hash: str
    log_signing_key_id: str = Field(min_length=1, max_length=128)
    observed_at: datetime
    previous_witnessed_tree_size: int | None
    previous_witnessed_root_hash: str | None
    consistency_proof_sha256: str | None

    @field_validator("witness_id")
    @classmethod
    def _validate_witness_id(cls, value: str) -> str:
        if not is_valid_witness_id(value):
            raise ValueError("invalid witness id")
        return value

    @field_validator("checkpoint_sha256", "root_hash", "previous_witnessed_root_hash", "consistency_proof_sha256")
    @classmethod
    def _validate_hash(cls, value: str | None) -> str | None:
        if value is not None and not is_valid_sha256_digest(value):
            raise ValueError("invalid hash")
        return value

    @field_validator("observed_at")
    @classmethod
    def _validate_time(cls, value: datetime) -> datetime:
        return normalize_aware_datetime(value)

    @model_validator(mode="after")
    def _validate_previous(self) -> TransparencyWitnessStatementPayload:
        has_size = self.previous_witnessed_tree_size is not None
        has_hash = self.previous_witnessed_root_hash is not None
        if has_size != has_hash:
            raise ValueError("previous witness state incomplete")
        if self.previous_witnessed_tree_size is not None and self.previous_witnessed_tree_size < 1:
            raise ValueError("invalid previous tree size")
        return self


class TransparencyWitnessStatementEnvelope(_WitnessModel):
    statement: TransparencyWitnessStatementPayload
    algorithm: Literal[TRANSPARENCY_WITNESS_SIGNATURE_ALGORITHM]
    signature_b64: str
    signed_at: datetime

    @field_validator("signature_b64")
    @classmethod
    def _validate_signature(cls, value: str) -> str:
        _decode_b64(value, expected_size=RAW_WITNESS_SIGNATURE_BYTES)
        return value

    @field_validator("signed_at")
    @classmethod
    def _validate_signed_at(cls, value: datetime) -> datetime:
        return normalize_aware_datetime(value)


class TransparencyWitnessStatePayload(_WitnessModel):
    state_version: Literal[TRANSPARENCY_WITNESS_STATE_VERSION]
    state_type: Literal[TRANSPARENCY_WITNESS_STATE_TYPE]
    log_id: str = Field(min_length=1, max_length=128)
    witness_id: str = Field(min_length=1, max_length=128)
    highest_tree_size: int = Field(ge=1)
    highest_root_hash: str
    highest_checkpoint_sha256: str
    log_signing_key_id: str = Field(min_length=1, max_length=128)
    updated_at: datetime

    @field_validator("witness_id")
    @classmethod
    def _validate_witness_id(cls, value: str) -> str:
        if not is_valid_witness_id(value):
            raise ValueError("invalid witness id")
        return value

    @field_validator("highest_root_hash", "highest_checkpoint_sha256")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid hash")
        return value

    @field_validator("updated_at")
    @classmethod
    def _validate_updated_at(cls, value: datetime) -> datetime:
        return normalize_aware_datetime(value)


@dataclass(frozen=True)
class TransparencyWitnessPrivateKey:
    witness_id: str
    private_key_bytes: bytes
    public_key_bytes: bytes
    public_key_fingerprint: str

    def __repr__(self) -> str:
        return (
            "TransparencyWitnessPrivateKey("
            f"witness_id={self.witness_id!r}, public_key_fingerprint={self.public_key_fingerprint!r})"
        )


@dataclass(frozen=True)
class TransparencyWitnessStatementCreationResult:
    envelope: TransparencyWitnessStatementEnvelope
    state: TransparencyWitnessStatePayload
    state_updated: bool


@dataclass(frozen=True)
class TransparencyWitnessStatementVerificationResult:
    witness_id: str
    log_id: str
    checkpoint_sha256: str
    tree_size: int
    root_hash: str
    observed_at: datetime
    log_signing_key_id: str


def witness_state_lock_path_for(state_path: Path) -> Path:
    if not isinstance(state_path, Path):
        raise TypeError("state_path must be a Path")
    return state_path.with_name(f"{state_path.name}.lock")


def load_transparency_witness_private_key(*, environ: dict[str, str] | os._Environ[str]) -> TransparencyWitnessPrivateKey:
    if not hasattr(environ, "__getitem__"):
        raise TypeError("environ must be a mapping")
    witness_id = environ.get(TRANSPARENCY_WITNESS_ID_ENV_NAME)  # type: ignore[attr-defined]
    if not is_valid_witness_id(witness_id):
        raise TransparencyWitnessConfigurationError(_CONFIG_MESSAGE)
    private_bytes = _env_b64(environ, TRANSPARENCY_WITNESS_PRIVATE_KEY_ENV_NAME, RAW_WITNESS_PRIVATE_KEY_BYTES)
    public_bytes = _env_b64(environ, TRANSPARENCY_WITNESS_PUBLIC_KEY_ENV_NAME, RAW_WITNESS_PUBLIC_KEY_BYTES)
    private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
    derived_public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    if derived_public != public_bytes:
        raise TransparencyWitnessConfigurationError(_CONFIG_MESSAGE)
    return TransparencyWitnessPrivateKey(
        witness_id=witness_id,  # type: ignore[arg-type]
        private_key_bytes=private_bytes,
        public_key_bytes=public_bytes,
        public_key_fingerprint=hashlib.sha256(public_bytes).hexdigest(),
    )


def canonicalize_witness_statement(statement: TransparencyWitnessStatementPayload) -> bytes:
    return json.dumps(
        statement.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def witness_statement_digest(envelope: TransparencyWitnessStatementEnvelope) -> str:
    return hashlib.sha256(
        json.dumps(envelope.model_dump(mode="json"), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def create_transparency_witness_statement(
    *,
    checkpoint_path: Path,
    output_path: Path,
    witness_state_path: Path,
    observed_at: datetime,
    consistency_proof_path: Path | None = None,
    log_path: Path | None = None,
    log_state_path: Path | None = None,
    environ: dict[str, str] | os._Environ[str] = os.environ,
) -> TransparencyWitnessStatementCreationResult:
    checkpoint = verify_transparency_checkpoint(
        checkpoint_path=checkpoint_path,
        log_path=log_path,
        log_state_path=log_state_path,
        mode=(
            TransparencyCheckpointVerificationMode.VERIFY_AGAINST_LOG
            if log_path is not None or log_state_path is not None
            else TransparencyCheckpointVerificationMode.SIGNATURE_ONLY
        ),
    )
    key = load_transparency_witness_private_key(environ=environ)
    observed = normalize_aware_datetime(observed_at)
    lock_fd = _open_lock(witness_state_lock_path_for(witness_state_path))
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        stored = load_transparency_witness_state(path=witness_state_path)
        consistency_digest = None
        if stored is not None:
            _validate_checkpoint_against_state(checkpoint=checkpoint, stored=stored, witness_id=key.witness_id)
            if _state_matches_checkpoint(checkpoint=checkpoint, stored=stored, witness_id=key.witness_id):
                if output_path.exists():
                    envelope = _load_matching_existing_statement(
                        output_path=output_path,
                        checkpoint=checkpoint,
                        key=key,
                    )
                else:
                    statement = _build_witness_statement(
                        checkpoint=checkpoint,
                        witness_id=key.witness_id,
                        observed_at=observed,
                        stored=stored,
                        consistency_digest=None,
                    )
                    envelope = _sign_statement(statement=statement, key=key, signed_at=observed)
                    export_transparency_witness_statement(path=output_path, envelope=envelope)
                return TransparencyWitnessStatementCreationResult(
                    envelope=envelope,
                    state=stored,
                    state_updated=False,
                )
            if checkpoint.tree_size > stored.highest_tree_size:
                if consistency_proof_path is None:
                    raise TransparencyWitnessStateError(_STATE_MESSAGE)
                proof = load_transparency_consistency_proof(path=consistency_proof_path)
                old = _CheckpointLike(
                    log_id=stored.log_id,
                    tree_size=stored.highest_tree_size,
                    root_hash=stored.highest_root_hash,
                )
                verify_checkpoint_consistency_proof(old_checkpoint=old, new_checkpoint=checkpoint, proof=proof)
                consistency_digest = transparency_consistency_proof_digest(proof)
        statement = _build_witness_statement(
            checkpoint=checkpoint,
            witness_id=key.witness_id,
            observed_at=observed,
            stored=stored,
            consistency_digest=consistency_digest,
        )
        envelope = _sign_statement(statement=statement, key=key, signed_at=observed)
        current = build_transparency_witness_state(checkpoint=checkpoint, witness_id=key.witness_id, updated_at=observed)
        export_transparency_witness_statement(path=output_path, envelope=envelope)
        export_transparency_witness_state(path=witness_state_path, state=current)
        return TransparencyWitnessStatementCreationResult(
            envelope=envelope,
            state=current,
            state_updated=True,
        )
    finally:
        _close_lock(lock_fd)


def verify_transparency_witness_statement(
    *,
    statement_path: Path,
    checkpoint: TransparencyCheckpointVerificationResult,
    trust_store: TransparencyWitnessTrustStorePayload,
    verification_time: datetime,
    revoked_witness_policy: RevokedWitnessPolicy = RevokedWitnessPolicy.REJECT,
    maximum_clock_skew: timedelta = MAX_WITNESS_CLOCK_SKEW,
) -> TransparencyWitnessStatementVerificationResult:
    envelope = load_transparency_witness_statement(path=statement_path)
    statement = envelope.statement
    if (
        statement.log_id != checkpoint.log_id
        or statement.checkpoint_sha256 != checkpoint.checkpoint_sha256
        or statement.tree_size != checkpoint.tree_size
        or statement.root_hash != checkpoint.root_hash
        or statement.log_signing_key_id != checkpoint.log_signing_key_id
        or trust_store.log_id != checkpoint.log_id
    ):
        raise TransparencyWitnessSignatureError(_SIGNATURE_MESSAGE)
    witness = trust_store.get_witness(statement.witness_id)
    ensure_witness_trusted_for_verification(
        witness=witness,
        observed_at=statement.observed_at,
        verification_time=verification_time,
        revoked_witness_policy=revoked_witness_policy,
        maximum_clock_skew=maximum_clock_skew,
    )
    public_key = Ed25519PublicKey.from_public_bytes(witness.public_key_bytes())
    try:
        public_key.verify(
            _decode_b64(envelope.signature_b64, expected_size=RAW_WITNESS_SIGNATURE_BYTES),
            _statement_message(statement),
        )
    except InvalidSignature as error:
        raise TransparencyWitnessSignatureError(_SIGNATURE_MESSAGE) from error
    return TransparencyWitnessStatementVerificationResult(
        witness_id=statement.witness_id,
        log_id=statement.log_id,
        checkpoint_sha256=statement.checkpoint_sha256,
        tree_size=statement.tree_size,
        root_hash=statement.root_hash,
        observed_at=statement.observed_at,
        log_signing_key_id=statement.log_signing_key_id,
    )


def load_transparency_witness_statement(*, path: Path) -> TransparencyWitnessStatementEnvelope:
    return TransparencyWitnessStatementEnvelope.model_validate_json(json.dumps(_load_json(path=path, max_bytes=MAX_TRANSPARENCY_WITNESS_STATEMENT_BYTES)))


def export_transparency_witness_statement(*, path: Path, envelope: TransparencyWitnessStatementEnvelope) -> None:
    if not isinstance(envelope, TransparencyWitnessStatementEnvelope):
        raise TypeError("envelope must be a TransparencyWitnessStatementEnvelope")
    _atomic_export(path=path, text=json.dumps(envelope.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=False))


def load_transparency_witness_state(*, path: Path) -> TransparencyWitnessStatePayload | None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink() or path.is_dir():
        raise TransparencyWitnessStateError(_STATE_MESSAGE)
    if not path.exists():
        return None
    try:
        if not path.is_file() or path.stat().st_size > MAX_TRANSPARENCY_WITNESS_STATE_BYTES:
            raise TransparencyWitnessStateError(_STATE_MESSAGE)
        return TransparencyWitnessStatePayload.model_validate_json(json.dumps(_loads_no_duplicate_keys(path.read_text(encoding="utf-8"))))
    except OSError as error:
        raise TransparencyWitnessStateError(_STATE_MESSAGE) from error
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise TransparencyWitnessStateError(_STATE_MESSAGE) from error


def export_transparency_witness_state(*, path: Path, state: TransparencyWitnessStatePayload) -> None:
    if not isinstance(state, TransparencyWitnessStatePayload):
        raise TypeError("state must be a TransparencyWitnessStatePayload")
    _atomic_export(path=path, text=json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=False))


def build_transparency_witness_state(
    *,
    checkpoint: TransparencyCheckpointVerificationResult,
    witness_id: str,
    updated_at: datetime,
) -> TransparencyWitnessStatePayload:
    return TransparencyWitnessStatePayload(
        state_version=TRANSPARENCY_WITNESS_STATE_VERSION,
        state_type=TRANSPARENCY_WITNESS_STATE_TYPE,
        log_id=checkpoint.log_id,
        witness_id=witness_id,
        highest_tree_size=checkpoint.tree_size,
        highest_root_hash=checkpoint.root_hash,
        highest_checkpoint_sha256=checkpoint.checkpoint_sha256,
        log_signing_key_id=checkpoint.log_signing_key_id,
        updated_at=normalize_aware_datetime(updated_at),
    )


def _build_witness_statement(
    *,
    checkpoint: TransparencyCheckpointVerificationResult,
    witness_id: str,
    observed_at: datetime,
    stored: TransparencyWitnessStatePayload | None,
    consistency_digest: str | None,
) -> TransparencyWitnessStatementPayload:
    return TransparencyWitnessStatementPayload(
        statement_version=TRANSPARENCY_WITNESS_STATEMENT_VERSION,
        statement_type=TRANSPARENCY_WITNESS_STATEMENT_TYPE,
        log_id=checkpoint.log_id,
        witness_id=witness_id,
        checkpoint_sha256=checkpoint.checkpoint_sha256,
        tree_size=checkpoint.tree_size,
        root_hash=checkpoint.root_hash,
        log_signing_key_id=checkpoint.log_signing_key_id,
        observed_at=normalize_aware_datetime(observed_at),
        previous_witnessed_tree_size=stored.highest_tree_size if stored is not None else None,
        previous_witnessed_root_hash=stored.highest_root_hash if stored is not None else None,
        consistency_proof_sha256=consistency_digest,
    )


def _state_matches_checkpoint(
    *,
    checkpoint: TransparencyCheckpointVerificationResult,
    stored: TransparencyWitnessStatePayload,
    witness_id: str,
) -> bool:
    return (
        stored.log_id == checkpoint.log_id
        and stored.witness_id == witness_id
        and stored.highest_tree_size == checkpoint.tree_size
        and stored.highest_root_hash == checkpoint.root_hash
        and stored.highest_checkpoint_sha256 == checkpoint.checkpoint_sha256
        and stored.log_signing_key_id == checkpoint.log_signing_key_id
    )


def _load_matching_existing_statement(
    *,
    output_path: Path,
    checkpoint: TransparencyCheckpointVerificationResult,
    key: TransparencyWitnessPrivateKey,
) -> TransparencyWitnessStatementEnvelope:
    envelope = load_transparency_witness_statement(path=output_path)
    statement = envelope.statement
    if (
        statement.log_id != checkpoint.log_id
        or statement.witness_id != key.witness_id
        or statement.checkpoint_sha256 != checkpoint.checkpoint_sha256
        or statement.tree_size != checkpoint.tree_size
        or statement.root_hash != checkpoint.root_hash
        or statement.log_signing_key_id != checkpoint.log_signing_key_id
    ):
        raise TransparencyWitnessSignatureError(_SIGNATURE_MESSAGE)
    public_key = Ed25519PublicKey.from_public_bytes(key.public_key_bytes)
    try:
        public_key.verify(
            _decode_b64(envelope.signature_b64, expected_size=RAW_WITNESS_SIGNATURE_BYTES),
            _statement_message(statement),
        )
    except InvalidSignature as error:
        raise TransparencyWitnessSignatureError(_SIGNATURE_MESSAGE) from error
    return envelope


@dataclass(frozen=True)
class _CheckpointLike:
    log_id: str
    tree_size: int
    root_hash: str


def _validate_checkpoint_against_state(
    *,
    checkpoint: TransparencyCheckpointVerificationResult,
    stored: TransparencyWitnessStatePayload,
    witness_id: str,
) -> None:
    if stored.log_id != checkpoint.log_id or stored.witness_id != witness_id:
        raise TransparencyWitnessSplitViewError(_SPLIT_MESSAGE)
    if checkpoint.tree_size < stored.highest_tree_size:
        raise TransparencyWitnessRollbackError(_ROLLBACK_MESSAGE)
    if checkpoint.tree_size == stored.highest_tree_size and (
        stored.highest_root_hash != checkpoint.root_hash
        or stored.highest_checkpoint_sha256 != checkpoint.checkpoint_sha256
        or stored.log_signing_key_id != checkpoint.log_signing_key_id
    ):
        raise TransparencyWitnessSplitViewError(_SPLIT_MESSAGE)


def _sign_statement(
    *,
    statement: TransparencyWitnessStatementPayload,
    key: TransparencyWitnessPrivateKey,
    signed_at: datetime,
) -> TransparencyWitnessStatementEnvelope:
    private_key = Ed25519PrivateKey.from_private_bytes(key.private_key_bytes)
    signature = private_key.sign(_statement_message(statement))
    return TransparencyWitnessStatementEnvelope(
        statement=statement,
        algorithm=TRANSPARENCY_WITNESS_SIGNATURE_ALGORITHM,
        signature_b64=base64.b64encode(signature).decode("ascii"),
        signed_at=normalize_aware_datetime(signed_at),
    )


def _statement_message(statement: TransparencyWitnessStatementPayload) -> bytes:
    return TRANSPARENCY_WITNESS_SIGNATURE_DOMAIN + b"\0" + canonicalize_witness_statement(statement)


def _load_json(*, path: Path, max_bytes: int) -> object:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink() or path.is_dir():
        raise TransparencyWitnessSignatureError(_SIGNATURE_MESSAGE)
    try:
        if not path.is_file() or path.stat().st_size > max_bytes:
            raise TransparencyWitnessSignatureError(_SIGNATURE_MESSAGE)
        return _loads_no_duplicate_keys(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise TransparencyWitnessSignatureError(_SIGNATURE_MESSAGE) from error
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise TransparencyWitnessSignatureError(_SIGNATURE_MESSAGE) from error


def _atomic_export(*, path: Path, text: str) -> None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink() or path.is_dir():
        raise TransparencyWitnessStateError(_STATE_MESSAGE)
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
            os.chmod(temp_path, TRANSPARENCY_WITNESS_FILE_MODE)
        os.replace(temp_path, path)
        replaced = True
        dir_fd = os.open(path.parent, os.O_RDONLY)
        os.fsync(dir_fd)
    except OSError as error:
        raise TransparencyWitnessStateError(_STATE_MESSAGE) from error
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
            raise TransparencyWitnessStateError(_STATE_MESSAGE)
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, TRANSPARENCY_WITNESS_FILE_MODE)
        os.chmod(lock_path, TRANSPARENCY_WITNESS_FILE_MODE)
        return fd
    except OSError as error:
        raise TransparencyWitnessStateError(_STATE_MESSAGE) from error


def _close_lock(fd: int) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


def _env_b64(environ: dict[str, str] | os._Environ[str], name: str, expected_size: int) -> bytes:
    value = environ.get(name)  # type: ignore[attr-defined]
    if not value:
        raise TransparencyWitnessConfigurationError(_CONFIG_MESSAGE)
    return _decode_b64(value, expected_size=expected_size)


def _decode_b64(value: object, *, expected_size: int) -> bytes:
    if not isinstance(value, str) or not value:
        raise TransparencyWitnessConfigurationError(_CONFIG_MESSAGE)
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError, ValueError) as error:
        raise TransparencyWitnessConfigurationError(_CONFIG_MESSAGE) from error
    if len(decoded) != expected_size:
        raise TransparencyWitnessConfigurationError(_CONFIG_MESSAGE)
    return decoded


def _loads_no_duplicate_keys(text: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TransparencyWitnessSignatureError(_SIGNATURE_MESSAGE)
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)
