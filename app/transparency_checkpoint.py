"""Signed checkpoints for the local transparency log Merkle tree."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
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
    TransparencyCheckpointExportError,
    TransparencyCheckpointLogMismatchError,
    TransparencyCheckpointReadError,
    TransparencyCheckpointSignatureError,
    TransparencyCheckpointValidationError,
    TransparencyConsistencyProofMismatchError,
    TransparencyInclusionProofMismatchError,
)
from app.report_integrity import is_valid_sha256_digest
from app.transparency_log import TransparencyLogInclusionResult, verify_transparency_log
from app.transparency_merkle import (
    CONSISTENCY_PROOF_TYPE,
    INCLUSION_PROOF_TYPE,
    TRANSPARENCY_MERKLE_VERSION,
    TransparencyConsistencyProofPayload,
    TransparencyInclusionProofPayload,
    calculate_root_from_inclusion_proof,
    calculate_transparency_merkle_root,
    generate_consistency_path,
    generate_inclusion_audit_path,
    verify_consistency_path,
)

TRANSPARENCY_CHECKPOINT_VERSION = 1
TRANSPARENCY_CHECKPOINT_TYPE = "audit_report_transparency_checkpoint"
TRANSPARENCY_CHECKPOINT_SIGNATURE_VERSION = 1
TRANSPARENCY_CHECKPOINT_SIGNATURE_TYPE = "audit_report_transparency_checkpoint_signature"
TRANSPARENCY_CHECKPOINT_SIGNATURE_DOMAIN = b"agentic-ai-lab:transparency-checkpoint:ed25519:v1"
TRANSPARENCY_CHECKPOINT_SIGNATURE_ALGORITHM = "ed25519-transparency-checkpoint-v1"

TRANSPARENCY_LOG_ID_ENV_NAME = "AUDIT_REPORT_TRANSPARENCY_LOG_ID"
TRANSPARENCY_LOG_PRIVATE_KEY_ENV_NAME = "AUDIT_REPORT_TRANSPARENCY_LOG_ED25519_PRIVATE_KEY_B64"
TRANSPARENCY_LOG_PUBLIC_KEY_ENV_NAME = "AUDIT_REPORT_TRANSPARENCY_LOG_ED25519_PUBLIC_KEY_B64"
TRANSPARENCY_LOG_KEY_ID_ENV_NAME = "AUDIT_REPORT_TRANSPARENCY_LOG_ED25519_KEY_ID"
RAW_ED25519_PRIVATE_KEY_BYTES = 32
RAW_ED25519_PUBLIC_KEY_BYTES = 32
CHECKPOINT_FILE_MODE = 0o600
MAX_TRANSPARENCY_CHECKPOINT_BYTES = 256 * 1024

_READ_MESSAGE = "Failed to read the transparency checkpoint."
_VALIDATION_MESSAGE = "The transparency checkpoint is invalid."
_SIGNATURE_MESSAGE = "The transparency checkpoint signature is invalid."
_EXPORT_MESSAGE = "Failed to export the transparency checkpoint."
_LOG_MISMATCH_MESSAGE = "The transparency checkpoint does not match the log."
_INCLUSION_MESSAGE = "The transparency inclusion proof does not match."
_CONSISTENCY_MESSAGE = "The transparency consistency proof does not match."


class TransparencyCheckpointVerificationMode(str, Enum):
    SIGNATURE_ONLY = "signature_only"
    VERIFY_AGAINST_LOG = "verify_against_log"


class TransparencyCheckpointModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class TransparencyCheckpointPayload(TransparencyCheckpointModel):
    checkpoint_version: Literal[TRANSPARENCY_CHECKPOINT_VERSION]
    checkpoint_type: Literal[TRANSPARENCY_CHECKPOINT_TYPE]
    log_id: str = Field(min_length=1, max_length=128)
    tree_size: int = Field(ge=1)
    root_hash: str
    first_sequence: int = Field(ge=1)
    last_sequence: int = Field(ge=1)
    last_entry_hash: str
    issued_at: datetime
    log_signing_key_id: str = Field(min_length=1, max_length=128)

    @field_validator("root_hash", "last_entry_hash")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid hash")
        return value

    @field_validator("issued_at")
    @classmethod
    def _validate_time(cls, value: datetime) -> datetime:
        return _normalize_aware_datetime(value)

    @model_validator(mode="after")
    def _validate_sequences(self) -> TransparencyCheckpointPayload:
        if self.first_sequence != 1 or self.last_sequence != self.tree_size:
            raise ValueError("sequence mismatch")
        return self


class TransparencyCheckpointSignaturePayload(TransparencyCheckpointModel):
    signature_version: Literal[TRANSPARENCY_CHECKPOINT_SIGNATURE_VERSION]
    signature_type: Literal[TRANSPARENCY_CHECKPOINT_SIGNATURE_TYPE]
    algorithm: Literal[TRANSPARENCY_CHECKPOINT_SIGNATURE_ALGORITHM]
    log_id: str = Field(min_length=1, max_length=128)
    log_signing_key_id: str = Field(min_length=1, max_length=128)
    checkpoint_sha256: str
    signature_b64: str
    signed_at: datetime

    @field_validator("checkpoint_sha256")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid hash")
        return value

    @field_validator("signature_b64")
    @classmethod
    def _validate_signature(cls, value: str) -> str:
        _decode_b64(value, expected_size=64)
        return value

    @field_validator("signed_at")
    @classmethod
    def _validate_time(cls, value: datetime) -> datetime:
        return _normalize_aware_datetime(value)


@dataclass(frozen=True)
class TransparencyCheckpointCreationResult:
    checkpoint: TransparencyCheckpointPayload
    signature: TransparencyCheckpointSignaturePayload
    checkpoint_sha256: str


@dataclass(frozen=True)
class TransparencyCheckpointVerificationResult:
    checkpoint_version: int
    log_id: str
    tree_size: int
    root_hash: str
    last_entry_hash: str
    issued_at: datetime
    log_signing_key_id: str
    checkpoint_sha256: str


@dataclass(frozen=True)
class TransparencyInclusionProofVerificationResult:
    log_id: str
    sequence: int
    leaf_index: int
    tree_size: int
    entry_hash: str
    root_hash: str


@dataclass(frozen=True)
class TransparencyConsistencyProofVerificationResult:
    log_id: str
    old_tree_size: int
    new_tree_size: int
    old_root_hash: str
    new_root_hash: str


def checkpoint_signature_path_for(checkpoint_path: Path) -> Path:
    if not isinstance(checkpoint_path, Path):
        raise TypeError("checkpoint_path must be a Path")
    return checkpoint_path.with_name(f"{checkpoint_path.name}.sig")


def canonicalize_transparency_checkpoint(checkpoint: TransparencyCheckpointPayload) -> bytes:
    return _canonicalize_model(checkpoint)


def transparency_checkpoint_digest(checkpoint: TransparencyCheckpointPayload) -> str:
    return hashlib.sha256(canonicalize_transparency_checkpoint(checkpoint)).hexdigest()


def create_transparency_checkpoint(
    *,
    output_path: Path,
    log_path: Path,
    log_state_path: Path,
    log_id: str,
    issued_at: datetime,
) -> TransparencyCheckpointCreationResult:
    private_key, public_key, key_id = _load_key_pair_from_environment()
    verification = verify_transparency_log(log_path=log_path, state_path=log_state_path)
    if verification.entry_count < 1 or verification.last_sequence is None or verification.last_entry_hash is None:
        raise TransparencyCheckpointValidationError(_VALIDATION_MESSAGE)
    root_hash = calculate_transparency_merkle_root(verification.entry_hashes)
    checkpoint = TransparencyCheckpointPayload(
        checkpoint_version=TRANSPARENCY_CHECKPOINT_VERSION,
        checkpoint_type=TRANSPARENCY_CHECKPOINT_TYPE,
        log_id=log_id,
        tree_size=verification.entry_count,
        root_hash=root_hash,
        first_sequence=1,
        last_sequence=verification.last_sequence,
        last_entry_hash=verification.last_entry_hash,
        issued_at=_normalize_aware_datetime(issued_at),
        log_signing_key_id=key_id,
    )
    checkpoint_sha256 = transparency_checkpoint_digest(checkpoint)
    signature_bytes = _sign_checkpoint(private_key=private_key, checkpoint=checkpoint)
    signature = TransparencyCheckpointSignaturePayload(
        signature_version=TRANSPARENCY_CHECKPOINT_SIGNATURE_VERSION,
        signature_type=TRANSPARENCY_CHECKPOINT_SIGNATURE_TYPE,
        algorithm=TRANSPARENCY_CHECKPOINT_SIGNATURE_ALGORITHM,
        log_id=log_id,
        log_signing_key_id=key_id,
        checkpoint_sha256=checkpoint_sha256,
        signature_b64=base64.b64encode(signature_bytes).decode("ascii"),
        signed_at=_normalize_aware_datetime(issued_at),
    )
    _verify_signature(public_key=public_key, checkpoint=checkpoint, signature=signature)
    _export_checkpoint_pair(checkpoint_path=output_path, checkpoint=checkpoint, signature=signature)
    return TransparencyCheckpointCreationResult(checkpoint=checkpoint, signature=signature, checkpoint_sha256=checkpoint_sha256)


def verify_transparency_checkpoint(
    *,
    checkpoint_path: Path,
    log_path: Path | None,
    log_state_path: Path | None,
    mode: TransparencyCheckpointVerificationMode,
) -> TransparencyCheckpointVerificationResult:
    checkpoint = load_transparency_checkpoint(path=checkpoint_path)
    signature = load_transparency_checkpoint_signature(path=checkpoint_signature_path_for(checkpoint_path))
    public_key, key_id, log_id = _load_public_key_from_environment()
    if checkpoint.log_id != log_id or signature.log_id != log_id or checkpoint.log_signing_key_id != key_id or signature.log_signing_key_id != key_id:
        raise TransparencyCheckpointSignatureError(_SIGNATURE_MESSAGE)
    _verify_signature(public_key=public_key, checkpoint=checkpoint, signature=signature)
    checkpoint_sha256 = transparency_checkpoint_digest(checkpoint)
    if signature.checkpoint_sha256 != checkpoint_sha256:
        raise TransparencyCheckpointSignatureError(_SIGNATURE_MESSAGE)
    result = TransparencyCheckpointVerificationResult(
        checkpoint_version=checkpoint.checkpoint_version,
        log_id=checkpoint.log_id,
        tree_size=checkpoint.tree_size,
        root_hash=checkpoint.root_hash,
        last_entry_hash=checkpoint.last_entry_hash,
        issued_at=checkpoint.issued_at,
        log_signing_key_id=checkpoint.log_signing_key_id,
        checkpoint_sha256=checkpoint_sha256,
    )
    if TransparencyCheckpointVerificationMode(mode) is TransparencyCheckpointVerificationMode.VERIFY_AGAINST_LOG:
        if log_path is None or log_state_path is None:
            raise TransparencyCheckpointLogMismatchError(_LOG_MISMATCH_MESSAGE)
        verification = verify_transparency_log(log_path=log_path, state_path=log_state_path)
        if (
            verification.entry_count != checkpoint.tree_size
            or verification.last_entry_hash != checkpoint.last_entry_hash
            or calculate_transparency_merkle_root(verification.entry_hashes) != checkpoint.root_hash
        ):
            raise TransparencyCheckpointLogMismatchError(_LOG_MISMATCH_MESSAGE)
    return result


def load_transparency_checkpoint(*, path: Path) -> TransparencyCheckpointPayload:
    return TransparencyCheckpointPayload.model_validate_json(json.dumps(_load_json(path=path)))


def load_transparency_checkpoint_signature(*, path: Path) -> TransparencyCheckpointSignaturePayload:
    return TransparencyCheckpointSignaturePayload.model_validate_json(json.dumps(_load_json(path=path)))


def generate_checkpoint_inclusion_proof(
    *,
    checkpoint: TransparencyCheckpointVerificationResult,
    log_path: Path,
    log_state_path: Path,
    inclusion: TransparencyLogInclusionResult,
    issued_at: datetime,
) -> TransparencyInclusionProofPayload:
    verification = verify_transparency_log(log_path=log_path, state_path=log_state_path)
    if verification.entry_count != checkpoint.tree_size or verification.last_entry_hash != checkpoint.last_entry_hash:
        raise TransparencyCheckpointLogMismatchError(_LOG_MISMATCH_MESSAGE)
    leaf_index = inclusion.sequence - 1
    if leaf_index < 0 or leaf_index >= len(verification.entry_hashes) or verification.entry_hashes[leaf_index] != inclusion.entry_hash:
        raise TransparencyInclusionProofMismatchError(_INCLUSION_MESSAGE)
    return TransparencyInclusionProofPayload(
        proof_version=TRANSPARENCY_MERKLE_VERSION,
        proof_type=INCLUSION_PROOF_TYPE,
        log_id=checkpoint.log_id,
        tree_size=checkpoint.tree_size,
        leaf_index=leaf_index,
        sequence=inclusion.sequence,
        entry_hash=inclusion.entry_hash,
        root_hash=checkpoint.root_hash,
        audit_path=generate_inclusion_audit_path(entry_hashes=verification.entry_hashes, leaf_index=leaf_index),
        issued_at=_normalize_aware_datetime(issued_at),
    )


def verify_checkpoint_inclusion_proof(
    *,
    checkpoint: TransparencyCheckpointVerificationResult,
    proof: TransparencyInclusionProofPayload,
) -> TransparencyInclusionProofVerificationResult:
    if proof.log_id != checkpoint.log_id or proof.tree_size != checkpoint.tree_size or proof.root_hash != checkpoint.root_hash:
        raise TransparencyInclusionProofMismatchError(_INCLUSION_MESSAGE)
    calculated = calculate_root_from_inclusion_proof(
        entry_hash=proof.entry_hash,
        leaf_index=proof.leaf_index,
        tree_size=proof.tree_size,
        audit_path=proof.audit_path,
    )
    if calculated != checkpoint.root_hash:
        raise TransparencyInclusionProofMismatchError(_INCLUSION_MESSAGE)
    return TransparencyInclusionProofVerificationResult(
        log_id=proof.log_id,
        sequence=proof.sequence,
        leaf_index=proof.leaf_index,
        tree_size=proof.tree_size,
        entry_hash=proof.entry_hash,
        root_hash=proof.root_hash,
    )


def generate_checkpoint_consistency_proof(
    *,
    old_checkpoint: TransparencyCheckpointVerificationResult,
    new_checkpoint: TransparencyCheckpointVerificationResult,
    log_path: Path,
    log_state_path: Path,
    issued_at: datetime,
) -> TransparencyConsistencyProofPayload:
    verification = verify_transparency_log(log_path=log_path, state_path=log_state_path)
    if old_checkpoint.log_id != new_checkpoint.log_id or verification.entry_count != new_checkpoint.tree_size:
        raise TransparencyCheckpointLogMismatchError(_LOG_MISMATCH_MESSAGE)
    return TransparencyConsistencyProofPayload(
        proof_version=TRANSPARENCY_MERKLE_VERSION,
        proof_type=CONSISTENCY_PROOF_TYPE,
        log_id=new_checkpoint.log_id,
        old_tree_size=old_checkpoint.tree_size,
        new_tree_size=new_checkpoint.tree_size,
        old_root_hash=old_checkpoint.root_hash,
        new_root_hash=new_checkpoint.root_hash,
        consistency_path=generate_consistency_path(
            entry_hashes=verification.entry_hashes,
            old_tree_size=old_checkpoint.tree_size,
            new_tree_size=new_checkpoint.tree_size,
        ),
        issued_at=_normalize_aware_datetime(issued_at),
    )


def verify_checkpoint_consistency_proof(
    *,
    old_checkpoint: TransparencyCheckpointVerificationResult,
    new_checkpoint: TransparencyCheckpointVerificationResult,
    proof: TransparencyConsistencyProofPayload,
) -> TransparencyConsistencyProofVerificationResult:
    if (
        proof.log_id != old_checkpoint.log_id
        or proof.log_id != new_checkpoint.log_id
        or proof.old_tree_size != old_checkpoint.tree_size
        or proof.new_tree_size != new_checkpoint.tree_size
        or proof.old_root_hash != old_checkpoint.root_hash
        or proof.new_root_hash != new_checkpoint.root_hash
    ):
        raise TransparencyConsistencyProofMismatchError(_CONSISTENCY_MESSAGE)
    if not verify_consistency_path(
        old_tree_size=proof.old_tree_size,
        new_tree_size=proof.new_tree_size,
        old_root_hash=proof.old_root_hash,
        new_root_hash=proof.new_root_hash,
        consistency_path=proof.consistency_path,
    ):
        raise TransparencyConsistencyProofMismatchError(_CONSISTENCY_MESSAGE)
    return TransparencyConsistencyProofVerificationResult(
        log_id=proof.log_id,
        old_tree_size=proof.old_tree_size,
        new_tree_size=proof.new_tree_size,
        old_root_hash=proof.old_root_hash,
        new_root_hash=proof.new_root_hash,
    )


def _export_checkpoint_pair(
    *,
    checkpoint_path: Path,
    checkpoint: TransparencyCheckpointPayload,
    signature: TransparencyCheckpointSignaturePayload,
) -> None:
    signature_path = checkpoint_signature_path_for(checkpoint_path)
    checkpoint_text = json.dumps(checkpoint.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=False)
    signature_text = json.dumps(signature.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=False)
    _atomic_export_many(((checkpoint_path, checkpoint_text), (signature_path, signature_text)))


def _atomic_export_many(files: tuple[tuple[Path, str], ...]) -> None:
    temp_paths: list[tuple[Path, Path]] = []
    dir_fd: int | None = None
    try:
        for path, text in files:
            if path.is_symlink() or path.is_dir():
                raise TransparencyCheckpointValidationError(_VALIDATION_MESSAGE)
            path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp") as tmp:
                temp = Path(tmp.name)
                tmp.write(text.rstrip("\n") + "\n")
                tmp.flush()
                os.fsync(tmp.fileno())
                os.chmod(temp, CHECKPOINT_FILE_MODE)
            temp_paths.append((temp, path))
        for temp, path in temp_paths:
            os.replace(temp, path)
        if files:
            dir_fd = os.open(files[0][0].parent, os.O_RDONLY)
            os.fsync(dir_fd)
    except OSError as error:
        raise TransparencyCheckpointExportError(_EXPORT_MESSAGE) from error
    finally:
        if dir_fd is not None:
            try:
                os.close(dir_fd)
            except OSError:
                pass
        for temp, path in temp_paths:
            if temp.exists() and not path.exists():
                try:
                    temp.unlink(missing_ok=True)
                except OSError:
                    pass


def _load_json(*, path: Path) -> object:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink() or path.is_dir():
        raise TransparencyCheckpointValidationError(_VALIDATION_MESSAGE)
    try:
        if not path.is_file() or path.stat().st_size > MAX_TRANSPARENCY_CHECKPOINT_BYTES:
            raise TransparencyCheckpointValidationError(_VALIDATION_MESSAGE)
        return _loads_no_duplicate_keys(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise TransparencyCheckpointReadError(_READ_MESSAGE) from error
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise TransparencyCheckpointValidationError(_VALIDATION_MESSAGE) from error


def _sign_checkpoint(*, private_key: Ed25519PrivateKey, checkpoint: TransparencyCheckpointPayload) -> bytes:
    return private_key.sign(TRANSPARENCY_CHECKPOINT_SIGNATURE_DOMAIN + b"\0" + canonicalize_transparency_checkpoint(checkpoint))


def _verify_signature(
    *,
    public_key: Ed25519PublicKey,
    checkpoint: TransparencyCheckpointPayload,
    signature: TransparencyCheckpointSignaturePayload,
) -> None:
    try:
        public_key.verify(
            _decode_b64(signature.signature_b64, expected_size=64),
            TRANSPARENCY_CHECKPOINT_SIGNATURE_DOMAIN + b"\0" + canonicalize_transparency_checkpoint(checkpoint),
        )
    except InvalidSignature as error:
        raise TransparencyCheckpointSignatureError(_SIGNATURE_MESSAGE) from error


def _load_key_pair_from_environment() -> tuple[Ed25519PrivateKey, Ed25519PublicKey, str]:
    private_bytes = _env_b64(TRANSPARENCY_LOG_PRIVATE_KEY_ENV_NAME, expected_size=RAW_ED25519_PRIVATE_KEY_BYTES)
    public_bytes = _env_b64(TRANSPARENCY_LOG_PUBLIC_KEY_ENV_NAME, expected_size=RAW_ED25519_PUBLIC_KEY_BYTES)
    key_id = _env_text(TRANSPARENCY_LOG_KEY_ID_ENV_NAME)
    private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
    derived_public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    if derived_public != public_bytes:
        raise TransparencyCheckpointSignatureError(_SIGNATURE_MESSAGE)
    return private_key, Ed25519PublicKey.from_public_bytes(public_bytes), key_id


def _load_public_key_from_environment() -> tuple[Ed25519PublicKey, str, str]:
    public_bytes = _env_b64(TRANSPARENCY_LOG_PUBLIC_KEY_ENV_NAME, expected_size=RAW_ED25519_PUBLIC_KEY_BYTES)
    return Ed25519PublicKey.from_public_bytes(public_bytes), _env_text(TRANSPARENCY_LOG_KEY_ID_ENV_NAME), _env_text(TRANSPARENCY_LOG_ID_ENV_NAME)


def _env_text(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise TransparencyCheckpointSignatureError(_SIGNATURE_MESSAGE)
    return value


def _env_b64(name: str, *, expected_size: int) -> bytes:
    value = os.environ.get(name)
    if not value:
        raise TransparencyCheckpointSignatureError(_SIGNATURE_MESSAGE)
    return _decode_b64(value, expected_size=expected_size)


def _decode_b64(value: object, *, expected_size: int) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("invalid base64")
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError, ValueError) as error:
        raise ValueError("invalid base64") from error
    if len(decoded) != expected_size:
        raise ValueError("invalid length")
    return decoded


def _canonicalize_model(model: BaseModel) -> bytes:
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _loads_no_duplicate_keys(text: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TransparencyCheckpointValidationError(_VALIDATION_MESSAGE)
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)


def _normalize_aware_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("datetime required")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone required")
    return value.astimezone(UTC)
