"""Local split-view evidence for transparency checkpoint gossip."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.exceptions import (
    TransparencySplitViewEvidenceConflictError,
    TransparencySplitViewEvidenceError,
)
from app.report_integrity import is_valid_sha256_digest
from app.transparency_checkpoint import (
    TransparencyCheckpointVerificationMode,
    TransparencyCheckpointVerificationResult,
    verify_transparency_checkpoint,
)
from app.transparency_witness import (
    MAX_WITNESS_CLOCK_SKEW,
    RAW_WITNESS_SIGNATURE_BYTES,
    TRANSPARENCY_WITNESS_SIGNATURE_ALGORITHM,
    TransparencyWitnessPrivateKey,
    load_transparency_witness_private_key,
)
from app.transparency_witness_trust import (
    RevokedWitnessPolicy,
    TransparencyWitnessTrustStorePayload,
    ensure_witness_trusted_for_verification,
    is_valid_witness_id,
    normalize_aware_datetime,
)

TRANSPARENCY_SPLIT_VIEW_EVIDENCE_VERSION = 1
TRANSPARENCY_SPLIT_VIEW_EVIDENCE_TYPE = "audit_report_transparency_split_view_evidence"
TRANSPARENCY_SPLIT_VIEW_EVIDENCE_DOMAIN = b"agentic-ai-lab:transparency-split-view-evidence:ed25519:v1"
MAX_TRANSPARENCY_SPLIT_VIEW_EVIDENCE_BYTES = 128 * 1024
TRANSPARENCY_EVIDENCE_FILE_MODE = 0o600

_MESSAGE = "The transparency split-view evidence is invalid."
_CONFLICT_MESSAGE = "The transparency split-view evidence conflicts with an existing file."


class _EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class TransparencySplitViewEvidencePayload(_EvidenceModel):
    evidence_version: Literal[TRANSPARENCY_SPLIT_VIEW_EVIDENCE_VERSION]
    evidence_type: Literal[TRANSPARENCY_SPLIT_VIEW_EVIDENCE_TYPE]
    log_id: str = Field(min_length=1, max_length=128)
    tree_size: int = Field(ge=1)
    first_checkpoint_sha256: str
    first_root_hash: str
    first_log_signing_key_id: str = Field(min_length=1, max_length=128)
    second_checkpoint_sha256: str
    second_root_hash: str
    second_log_signing_key_id: str = Field(min_length=1, max_length=128)
    detected_by_witness_id: str = Field(min_length=1, max_length=128)
    detected_at: datetime

    @field_validator("first_checkpoint_sha256", "first_root_hash", "second_checkpoint_sha256", "second_root_hash")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid hash")
        return value

    @field_validator("detected_by_witness_id")
    @classmethod
    def _validate_witness_id(cls, value: str) -> str:
        if not is_valid_witness_id(value):
            raise ValueError("invalid witness id")
        return value

    @field_validator("detected_at")
    @classmethod
    def _validate_time(cls, value: datetime) -> datetime:
        return normalize_aware_datetime(value)


class TransparencySplitViewEvidenceEnvelope(_EvidenceModel):
    evidence: TransparencySplitViewEvidencePayload
    algorithm: Literal[TRANSPARENCY_WITNESS_SIGNATURE_ALGORITHM]
    signature_b64: str
    signed_at: datetime

    @field_validator("signed_at")
    @classmethod
    def _validate_signed_at(cls, value: datetime) -> datetime:
        return normalize_aware_datetime(value)


@dataclass(frozen=True)
class TransparencySplitViewEvidenceVerificationResult:
    evidence_id: str
    log_id: str
    tree_size: int
    witness_id: str
    detected_at: datetime


def create_transparency_split_view_evidence(
    *,
    checkpoint_path: Path,
    conflicting_checkpoint_path: Path,
    output_path: Path,
    detected_at: datetime,
    environ: dict[str, str] | os._Environ[str] = os.environ,
) -> TransparencySplitViewEvidenceEnvelope:
    first = verify_transparency_checkpoint(
        checkpoint_path=checkpoint_path,
        log_path=None,
        log_state_path=None,
        mode=TransparencyCheckpointVerificationMode.SIGNATURE_ONLY,
    )
    second = verify_transparency_checkpoint(
        checkpoint_path=conflicting_checkpoint_path,
        log_path=None,
        log_state_path=None,
        mode=TransparencyCheckpointVerificationMode.SIGNATURE_ONLY,
    )
    first, second = _normalize_checkpoint_pair(first, second)
    if output_path.exists():
        witness_id, public_key_bytes = _load_witness_public_identity(environ=environ)
        envelope = load_transparency_split_view_evidence(path=output_path)
        _validate_existing_evidence(
            envelope=envelope,
            first=first,
            second=second,
            witness_id=witness_id,
            public_key_bytes=public_key_bytes,
        )
        return envelope
    key = load_transparency_witness_private_key(environ=environ)
    payload = _build_evidence_payload(
        first=first,
        second=second,
        witness_id=key.witness_id,
        detected_at=detected_at,
    )
    envelope = _sign_evidence(evidence=payload, key=key, signed_at=detected_at)
    export_transparency_split_view_evidence(path=output_path, envelope=envelope)
    return envelope


def verify_transparency_split_view_evidence(
    *,
    evidence_path: Path,
    trust_store: TransparencyWitnessTrustStorePayload,
    verification_time: datetime,
    revoked_witness_policy: RevokedWitnessPolicy = RevokedWitnessPolicy.REJECT,
    maximum_clock_skew: timedelta = MAX_WITNESS_CLOCK_SKEW,
) -> TransparencySplitViewEvidenceVerificationResult:
    envelope = load_transparency_split_view_evidence(path=evidence_path)
    evidence = envelope.evidence
    if evidence.log_id != trust_store.log_id:
        raise TransparencySplitViewEvidenceError(_MESSAGE)
    witness = trust_store.get_witness(evidence.detected_by_witness_id)
    ensure_witness_trusted_for_verification(
        witness=witness,
        observed_at=evidence.detected_at,
        verification_time=verification_time,
        revoked_witness_policy=revoked_witness_policy,
        maximum_clock_skew=maximum_clock_skew,
    )
    public_key = Ed25519PublicKey.from_public_bytes(witness.public_key_bytes())
    try:
        public_key.verify(base64.b64decode(envelope.signature_b64.encode("ascii"), validate=True), _evidence_message(evidence))
    except Exception as error:
        raise TransparencySplitViewEvidenceError(_MESSAGE) from error
    return TransparencySplitViewEvidenceVerificationResult(
        evidence_id=transparency_split_view_evidence_id(envelope),
        log_id=evidence.log_id,
        tree_size=evidence.tree_size,
        witness_id=evidence.detected_by_witness_id,
        detected_at=evidence.detected_at,
    )


def transparency_split_view_evidence_id(envelope: TransparencySplitViewEvidenceEnvelope) -> str:
    evidence = envelope.evidence
    stable_payload = {
        "detected_by_witness_id": evidence.detected_by_witness_id,
        "first_checkpoint_sha256": evidence.first_checkpoint_sha256,
        "first_root_hash": evidence.first_root_hash,
        "log_id": evidence.log_id,
        "second_checkpoint_sha256": evidence.second_checkpoint_sha256,
        "second_root_hash": evidence.second_root_hash,
        "tree_size": evidence.tree_size,
    }
    return hashlib.sha256(
        json.dumps(
            stable_payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def load_transparency_split_view_evidence(*, path: Path) -> TransparencySplitViewEvidenceEnvelope:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink() or path.is_dir():
        raise TransparencySplitViewEvidenceError(_MESSAGE)
    try:
        if not path.is_file() or path.stat().st_size > MAX_TRANSPARENCY_SPLIT_VIEW_EVIDENCE_BYTES:
            raise TransparencySplitViewEvidenceError(_MESSAGE)
        payload = _loads_no_duplicate_keys(path.read_text(encoding="utf-8"))
        return TransparencySplitViewEvidenceEnvelope.model_validate_json(json.dumps(payload))
    except OSError as error:
        raise TransparencySplitViewEvidenceError(_MESSAGE) from error
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise TransparencySplitViewEvidenceError(_MESSAGE) from error


def export_transparency_split_view_evidence(*, path: Path, envelope: TransparencySplitViewEvidenceEnvelope) -> None:
    text = json.dumps(envelope.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=False)
    if path.exists():
        try:
            if path.read_text(encoding="utf-8").rstrip("\n") == text.rstrip("\n"):
                return
        except OSError as error:
            raise TransparencySplitViewEvidenceError(_MESSAGE) from error
        raise TransparencySplitViewEvidenceConflictError(_CONFLICT_MESSAGE)
    _atomic_export(path=path, text=text)


def _normalize_checkpoint_pair(
    first: TransparencyCheckpointVerificationResult,
    second: TransparencyCheckpointVerificationResult,
) -> tuple[TransparencyCheckpointVerificationResult, TransparencyCheckpointVerificationResult]:
    if first.log_id != second.log_id or first.tree_size != second.tree_size:
        raise TransparencySplitViewEvidenceError(_MESSAGE)
    if first.root_hash == second.root_hash or first.checkpoint_sha256 == second.checkpoint_sha256:
        raise TransparencySplitViewEvidenceError(_MESSAGE)
    ordered = sorted((first, second), key=lambda checkpoint: checkpoint.checkpoint_sha256)
    return ordered[0], ordered[1]


def _build_evidence_payload(
    *,
    first: TransparencyCheckpointVerificationResult,
    second: TransparencyCheckpointVerificationResult,
    witness_id: str,
    detected_at: datetime,
) -> TransparencySplitViewEvidencePayload:
    return TransparencySplitViewEvidencePayload(
        evidence_version=TRANSPARENCY_SPLIT_VIEW_EVIDENCE_VERSION,
        evidence_type=TRANSPARENCY_SPLIT_VIEW_EVIDENCE_TYPE,
        log_id=first.log_id,
        tree_size=first.tree_size,
        first_checkpoint_sha256=first.checkpoint_sha256,
        first_root_hash=first.root_hash,
        first_log_signing_key_id=first.log_signing_key_id,
        second_checkpoint_sha256=second.checkpoint_sha256,
        second_root_hash=second.root_hash,
        second_log_signing_key_id=second.log_signing_key_id,
        detected_by_witness_id=witness_id,
        detected_at=normalize_aware_datetime(detected_at),
    )


def _load_witness_public_identity(*, environ: dict[str, str] | os._Environ[str]) -> tuple[str, bytes]:
    witness_id = environ.get("AUDIT_REPORT_TRANSPARENCY_WITNESS_ID")  # type: ignore[attr-defined]
    if not is_valid_witness_id(witness_id):
        raise TransparencySplitViewEvidenceConflictError(_CONFLICT_MESSAGE)
    public_value = environ.get("AUDIT_REPORT_TRANSPARENCY_WITNESS_ED25519_PUBLIC_KEY_B64")  # type: ignore[attr-defined]
    public_key_bytes = _decode_public_key(public_value)
    return witness_id, public_key_bytes  # type: ignore[return-value]


def _decode_public_key(value: object) -> bytes:
    if not isinstance(value, str) or not value:
        raise TransparencySplitViewEvidenceConflictError(_CONFLICT_MESSAGE)
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError, ValueError) as error:
        raise TransparencySplitViewEvidenceConflictError(_CONFLICT_MESSAGE) from error
    if len(decoded) != 32:
        raise TransparencySplitViewEvidenceConflictError(_CONFLICT_MESSAGE)
    return decoded


def _validate_existing_evidence(
    *,
    envelope: TransparencySplitViewEvidenceEnvelope,
    first: TransparencyCheckpointVerificationResult,
    second: TransparencyCheckpointVerificationResult,
    witness_id: str,
    public_key_bytes: bytes,
) -> None:
    expected = _build_evidence_payload(
        first=first,
        second=second,
        witness_id=witness_id,
        detected_at=envelope.evidence.detected_at,
    )
    evidence = envelope.evidence
    if (
        evidence.evidence_version != expected.evidence_version
        or evidence.evidence_type != expected.evidence_type
        or evidence.log_id != expected.log_id
        or evidence.tree_size != expected.tree_size
        or evidence.first_checkpoint_sha256 != expected.first_checkpoint_sha256
        or evidence.first_root_hash != expected.first_root_hash
        or evidence.first_log_signing_key_id != expected.first_log_signing_key_id
        or evidence.second_checkpoint_sha256 != expected.second_checkpoint_sha256
        or evidence.second_root_hash != expected.second_root_hash
        or evidence.second_log_signing_key_id != expected.second_log_signing_key_id
        or evidence.detected_by_witness_id != expected.detected_by_witness_id
        or envelope.algorithm != TRANSPARENCY_WITNESS_SIGNATURE_ALGORITHM
    ):
        raise TransparencySplitViewEvidenceConflictError(_CONFLICT_MESSAGE)
    public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
    try:
        public_key.verify(
            base64.b64decode(envelope.signature_b64.encode("ascii"), validate=True),
            _evidence_message(evidence),
        )
    except Exception as error:
        raise TransparencySplitViewEvidenceConflictError(_CONFLICT_MESSAGE) from error


def _sign_evidence(
    *,
    evidence: TransparencySplitViewEvidencePayload,
    key: TransparencyWitnessPrivateKey,
    signed_at: datetime,
) -> TransparencySplitViewEvidenceEnvelope:
    signature = Ed25519PrivateKey.from_private_bytes(key.private_key_bytes).sign(_evidence_message(evidence))
    if len(signature) != RAW_WITNESS_SIGNATURE_BYTES:
        raise TransparencySplitViewEvidenceError(_MESSAGE)
    return TransparencySplitViewEvidenceEnvelope(
        evidence=evidence,
        algorithm=TRANSPARENCY_WITNESS_SIGNATURE_ALGORITHM,
        signature_b64=base64.b64encode(signature).decode("ascii"),
        signed_at=normalize_aware_datetime(signed_at),
    )


def _evidence_message(evidence: TransparencySplitViewEvidencePayload) -> bytes:
    return TRANSPARENCY_SPLIT_VIEW_EVIDENCE_DOMAIN + b"\0" + _canonicalize(evidence)


def _canonicalize(model: BaseModel) -> bytes:
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _atomic_export(*, path: Path, text: str) -> None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink() or path.is_dir():
        raise TransparencySplitViewEvidenceError(_MESSAGE)
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
            os.chmod(temp_path, TRANSPARENCY_EVIDENCE_FILE_MODE)
        os.replace(temp_path, path)
        replaced = True
        dir_fd = os.open(path.parent, os.O_RDONLY)
        os.fsync(dir_fd)
    except OSError as error:
        raise TransparencySplitViewEvidenceError(_MESSAGE) from error
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
                raise TransparencySplitViewEvidenceError(_MESSAGE)
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)
