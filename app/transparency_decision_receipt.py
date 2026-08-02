"""Signed transparency trust decision receipts."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
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
    TransparencyDecisionPolicyError,
    TransparencyDecisionReceiptConflictError,
    TransparencyDecisionReceiptError,
    TransparencyDecisionReceiptSignatureError,
)
from app.report_integrity import is_valid_sha256_digest
from app.transparency_offline_verifier import TransparencyOfflineVerificationResult
from app.transparency_witness_trust import normalize_aware_datetime

TRANSPARENCY_TRUST_DECISION_RECEIPT_VERSION = 1
TRANSPARENCY_TRUST_DECISION_RECEIPT_TYPE = "audit_report_transparency_trust_decision_receipt"
TRANSPARENCY_DECISION_RECEIPT_SIGNATURE_DOMAIN = (
    b"agentic-ai-lab:transparency-trust-decision-receipt:ed25519:v1"
)
TRANSPARENCY_DECISION_RECEIPT_SIGNATURE_ALGORITHM = "Ed25519"

DECISION_RECEIPT_PRIVATE_KEY_ENV_NAME = "AUDIT_REPORT_DECISION_RECEIPT_ED25519_PRIVATE_KEY_B64"
DECISION_RECEIPT_PUBLIC_KEY_ENV_NAME = "AUDIT_REPORT_DECISION_RECEIPT_ED25519_PUBLIC_KEY_B64"
DECISION_RECEIPT_KEY_ID_ENV_NAME = "AUDIT_REPORT_DECISION_RECEIPT_ED25519_KEY_ID"
DECISION_RECEIPT_PUBLIC_TRUST_STORE_ENV_NAME = "AUDIT_REPORT_DECISION_RECEIPT_PUBLIC_TRUST_STORE_JSON"
RAW_ED25519_PRIVATE_KEY_BYTES = 32
RAW_ED25519_PUBLIC_KEY_BYTES = 32
RAW_ED25519_SIGNATURE_BYTES = 64
DECISION_RECEIPT_FILE_MODE = 0o600
MAX_DECISION_RECEIPT_BYTES = 256 * 1024

_MESSAGE = "The transparency trust decision receipt is invalid."
_CONFIG_MESSAGE = "The transparency decision receipt signing key is not configured safely."
_CONFLICT_MESSAGE = "The transparency trust decision receipt conflicts with an existing file."


class TransparencyTrustDecision(str, Enum):
    TRUSTED = "trusted"
    REJECTED = "rejected"


class TransparencyRejectionCode(str, Enum):
    QUORUM_NOT_SATISFIED = "quorum_not_satisfied"
    ARTIFACT_DIGEST_MISMATCH = "artifact_digest_mismatch"
    INCLUSION_PROOF_INVALID = "inclusion_proof_invalid"
    LOCAL_POLICY_NOT_SATISFIED = "local_policy_not_satisfied"
    REVOKED_WITNESS = "revoked_witness"
    CONSISTENCY_PROOF_REQUIRED = "consistency_proof_required"
    SPLIT_VIEW_DETECTED = "split_view_detected"


class _ReceiptModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class TransparencyTrustDecisionReceiptPayload(_ReceiptModel):
    receipt_version: Literal[TRANSPARENCY_TRUST_DECISION_RECEIPT_VERSION]
    receipt_type: Literal[TRANSPARENCY_TRUST_DECISION_RECEIPT_TYPE]
    decision: TransparencyTrustDecision
    decision_core_sha256: str
    bundle_id: str
    bundle_sha256: str
    artifact_identifier: str = Field(min_length=1, max_length=256)
    artifact_sha256: str
    log_id: str = Field(min_length=1, max_length=128)
    checkpoint_sha256: str
    tree_size: int = Field(ge=1)
    root_hash: str
    required_witness_quorum: int = Field(ge=1)
    valid_witness_count: int = Field(ge=0)
    valid_witness_ids: tuple[str, ...]
    inclusion_verified: bool
    checkpoint_signature_verified: bool
    bundle_signature_verified: bool
    quorum_satisfied: bool
    policy_id: str = Field(min_length=1, max_length=128)
    verifier_version: str = Field(min_length=1, max_length=128)
    verified_at: datetime
    rejection_code: TransparencyRejectionCode | None

    @field_validator(
        "decision_core_sha256",
        "bundle_id",
        "bundle_sha256",
        "artifact_sha256",
        "checkpoint_sha256",
        "root_hash",
    )
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid digest")
        return value

    @field_validator("required_witness_quorum", "valid_witness_count")
    @classmethod
    def _validate_int(cls, value: int) -> int:
        if isinstance(value, bool):
            raise TypeError("invalid integer")
        return value

    @field_validator("verified_at")
    @classmethod
    def _validate_time(cls, value: datetime) -> datetime:
        return normalize_aware_datetime(value)

    @model_validator(mode="after")
    def _validate_decision(self) -> TransparencyTrustDecisionReceiptPayload:
        if self.decision is TransparencyTrustDecision.TRUSTED and self.rejection_code is not None:
            raise ValueError("trusted receipt cannot have rejection")
        if self.decision is TransparencyTrustDecision.REJECTED and self.rejection_code is None:
            raise ValueError("rejected receipt needs rejection")
        if self.decision_core_sha256 != calculate_decision_core_sha256(self):
            raise ValueError("decision core mismatch")
        return self


class TransparencyTrustDecisionReceiptEnvelope(_ReceiptModel):
    receipt: TransparencyTrustDecisionReceiptPayload
    algorithm: Literal[TRANSPARENCY_DECISION_RECEIPT_SIGNATURE_ALGORITHM]
    signature_b64: str
    signed_at: datetime
    signing_key_id: str = Field(min_length=1, max_length=128)

    @field_validator("signature_b64")
    @classmethod
    def _validate_signature(cls, value: str) -> str:
        _decode_b64(value, expected_size=RAW_ED25519_SIGNATURE_BYTES)
        return value

    @field_validator("signed_at")
    @classmethod
    def _validate_signed_at(cls, value: datetime) -> datetime:
        return normalize_aware_datetime(value)


@dataclass(frozen=True)
class DecisionReceiptSigningPrivateKey:
    key_id: str
    private_key_bytes: bytes
    public_key_bytes: bytes

    def __repr__(self) -> str:
        return f"DecisionReceiptSigningPrivateKey(key_id={self.key_id!r})"


@dataclass(frozen=True)
class DecisionReceiptTrustStore:
    keys: dict[str, bytes]

    def get_public_key(self, key_id: str) -> bytes:
        try:
            return self.keys[key_id]
        except KeyError as error:
            raise TransparencyDecisionReceiptSignatureError(_MESSAGE) from error


def calculate_decision_core_sha256(receipt: TransparencyTrustDecisionReceiptPayload) -> str:
    payload = receipt.model_dump(mode="json")
    payload["decision_core_sha256"] = None
    return hashlib.sha256(_canonicalize_mapping(payload)).hexdigest()


def build_trusted_decision_receipt(
    *,
    result: TransparencyOfflineVerificationResult,
    policy_id: str,
    verifier_version: str,
    verified_at: datetime,
) -> TransparencyTrustDecisionReceiptPayload:
    payload = {
        "receipt_version": TRANSPARENCY_TRUST_DECISION_RECEIPT_VERSION,
        "receipt_type": TRANSPARENCY_TRUST_DECISION_RECEIPT_TYPE,
        "decision": TransparencyTrustDecision.TRUSTED,
        "decision_core_sha256": "0" * 64,
        "bundle_id": result.bundle_id,
        "bundle_sha256": result.bundle_sha256,
        "artifact_identifier": result.artifact_identifier,
        "artifact_sha256": result.artifact_sha256,
        "log_id": result.log_id,
        "checkpoint_sha256": result.checkpoint_sha256,
        "tree_size": result.tree_size,
        "root_hash": result.root_hash,
        "required_witness_quorum": result.required_witness_quorum,
        "valid_witness_count": result.valid_witness_count,
        "valid_witness_ids": result.valid_witness_ids,
        "inclusion_verified": result.inclusion_verified,
        "checkpoint_signature_verified": result.checkpoint_signature_verified,
        "bundle_signature_verified": result.bundle_signature_verified,
        "quorum_satisfied": result.quorum_satisfied,
        "policy_id": policy_id,
        "verifier_version": verifier_version,
        "verified_at": normalize_aware_datetime(verified_at),
        "rejection_code": None,
    }
    draft = TransparencyTrustDecisionReceiptPayload.model_construct(**payload)
    payload["decision_core_sha256"] = calculate_decision_core_sha256(draft)
    return TransparencyTrustDecisionReceiptPayload.model_validate(payload)


def build_rejected_decision_receipt(
    *,
    result: TransparencyOfflineVerificationResult,
    rejection_code: TransparencyRejectionCode,
    policy_id: str,
    verifier_version: str,
    verified_at: datetime,
) -> TransparencyTrustDecisionReceiptPayload:
    trusted = build_trusted_decision_receipt(
        result=result,
        policy_id=policy_id,
        verifier_version=verifier_version,
        verified_at=verified_at,
    )
    payload = trusted.model_dump(mode="python")
    payload["decision"] = TransparencyTrustDecision.REJECTED
    payload["rejection_code"] = rejection_code
    payload["decision_core_sha256"] = "0" * 64
    draft = TransparencyTrustDecisionReceiptPayload.model_construct(**payload)
    payload["decision_core_sha256"] = calculate_decision_core_sha256(draft)
    return TransparencyTrustDecisionReceiptPayload.model_validate(payload)


def create_transparency_trust_decision_receipt(
    *,
    output_path: Path,
    receipt: TransparencyTrustDecisionReceiptPayload,
    signed_at: datetime,
    trust_store: DecisionReceiptTrustStore | None = None,
    environ: dict[str, str] | os._Environ[str] = os.environ,
) -> TransparencyTrustDecisionReceiptEnvelope:
    if output_path.exists():
        effective_trust_store = (
            trust_store
            if trust_store is not None
            else load_decision_receipt_trust_store(environ=environ)
        )

        try:
            existing_receipt = (
                verify_transparency_trust_decision_receipt(
                    receipt_path=output_path,
                    trust_store=effective_trust_store,
                )
            )
        except TransparencyDecisionReceiptError as error:
            raise TransparencyDecisionReceiptConflictError(
                _CONFLICT_MESSAGE
            ) from error

        existing_semantic = existing_receipt.model_dump(
            mode="json",
            exclude={
                "verified_at",
                "decision_core_sha256",
            },
        )
        requested_semantic = receipt.model_dump(
            mode="json",
            exclude={
                "verified_at",
                "decision_core_sha256",
            },
        )

        if existing_semantic != requested_semantic:
            raise TransparencyDecisionReceiptConflictError(
                _CONFLICT_MESSAGE
            )

        return load_transparency_trust_decision_receipt(
            path=output_path
        )

    key = load_decision_receipt_signing_private_key(
        environ=environ
    )
    envelope = sign_decision_receipt(
        receipt=receipt,
        signing_key=key,
        signed_at=signed_at,
    )
    export_transparency_trust_decision_receipt(
        path=output_path,
        envelope=envelope,
    )
    return envelope


def sign_decision_receipt(
    *,
    receipt: TransparencyTrustDecisionReceiptPayload,
    signing_key: DecisionReceiptSigningPrivateKey,
    signed_at: datetime,
) -> TransparencyTrustDecisionReceiptEnvelope:
    signature = Ed25519PrivateKey.from_private_bytes(signing_key.private_key_bytes).sign(
        TRANSPARENCY_DECISION_RECEIPT_SIGNATURE_DOMAIN + b"\0" + canonicalize_decision_receipt(receipt)
    )
    return TransparencyTrustDecisionReceiptEnvelope(
        receipt=receipt,
        algorithm=TRANSPARENCY_DECISION_RECEIPT_SIGNATURE_ALGORITHM,
        signature_b64=base64.b64encode(signature).decode("ascii"),
        signed_at=normalize_aware_datetime(signed_at),
        signing_key_id=signing_key.key_id,
    )


def verify_transparency_trust_decision_receipt(
    *,
    receipt_path: Path,
    trust_store: DecisionReceiptTrustStore,
    bundle_sha256: str | None = None,
    artifact_sha256: str | None = None,
) -> TransparencyTrustDecisionReceiptPayload:
    envelope = load_transparency_trust_decision_receipt(path=receipt_path)
    if bundle_sha256 is not None and envelope.receipt.bundle_sha256 != bundle_sha256:
        raise TransparencyDecisionReceiptSignatureError(_MESSAGE)
    if artifact_sha256 is not None and envelope.receipt.artifact_sha256 != artifact_sha256:
        raise TransparencyDecisionReceiptSignatureError(_MESSAGE)
    public_key = Ed25519PublicKey.from_public_bytes(trust_store.get_public_key(envelope.signing_key_id))
    try:
        public_key.verify(
            _decode_b64(envelope.signature_b64, expected_size=RAW_ED25519_SIGNATURE_BYTES),
            TRANSPARENCY_DECISION_RECEIPT_SIGNATURE_DOMAIN + b"\0" + canonicalize_decision_receipt(envelope.receipt),
        )
    except InvalidSignature as error:
        raise TransparencyDecisionReceiptSignatureError(_MESSAGE) from error
    return envelope.receipt


def require_trusted_decision_receipt(
    *,
    receipt: TransparencyTrustDecisionReceiptEnvelope,
    artifact_identifier: str,
    artifact_sha256: str,
    bundle_sha256: str,
    allowed_policy_ids: tuple[str, ...] | None = None,
) -> None:
    payload = receipt.receipt
    if (
        payload.decision is not TransparencyTrustDecision.TRUSTED
        or payload.artifact_identifier != artifact_identifier
        or payload.artifact_sha256 != artifact_sha256
        or payload.bundle_sha256 != bundle_sha256
    ):
        raise TransparencyDecisionPolicyError("The transparency trust decision receipt does not satisfy policy.")
    if allowed_policy_ids is not None and payload.policy_id not in allowed_policy_ids:
        raise TransparencyDecisionPolicyError("The transparency trust decision receipt does not satisfy policy.")


def load_decision_receipt_signing_private_key(
    *, environ: dict[str, str] | os._Environ[str] = os.environ
) -> DecisionReceiptSigningPrivateKey:
    private_bytes = _env_b64(environ, DECISION_RECEIPT_PRIVATE_KEY_ENV_NAME, RAW_ED25519_PRIVATE_KEY_BYTES)
    public_bytes = _env_b64(environ, DECISION_RECEIPT_PUBLIC_KEY_ENV_NAME, RAW_ED25519_PUBLIC_KEY_BYTES)
    key_id = _env_text(environ, DECISION_RECEIPT_KEY_ID_ENV_NAME)
    private = Ed25519PrivateKey.from_private_bytes(private_bytes)
    derived = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    if derived != public_bytes:
        raise TransparencyDecisionReceiptError(_CONFIG_MESSAGE)
    return DecisionReceiptSigningPrivateKey(key_id=key_id, private_key_bytes=private_bytes, public_key_bytes=public_bytes)


def load_decision_receipt_trust_store(
    *, path: Path | None = None, environ: dict[str, str] | os._Environ[str] = os.environ
) -> DecisionReceiptTrustStore:
    if path is not None:
        raw = _load_json(path=path)
    else:
        value = environ.get(DECISION_RECEIPT_PUBLIC_TRUST_STORE_ENV_NAME)  # type: ignore[attr-defined]
        if not value:
            return DecisionReceiptTrustStore(
                keys={_env_text(environ, DECISION_RECEIPT_KEY_ID_ENV_NAME): _env_b64(environ, DECISION_RECEIPT_PUBLIC_KEY_ENV_NAME, RAW_ED25519_PUBLIC_KEY_BYTES)}
            )
        raw = _loads_no_duplicate_keys(value)
    if not isinstance(raw, dict) or set(raw) != {"keys"} or not isinstance(raw["keys"], list):
        raise TransparencyDecisionReceiptError(_CONFIG_MESSAGE)
    keys: dict[str, bytes] = {}
    for item in raw["keys"]:
        if not isinstance(item, dict) or set(item) != {"key_id", "public_key_b64"}:
            raise TransparencyDecisionReceiptError(_CONFIG_MESSAGE)
        key_id = item["key_id"]
        if not isinstance(key_id, str) or not key_id:
            raise TransparencyDecisionReceiptError(_CONFIG_MESSAGE)
        keys[key_id] = _decode_b64(item["public_key_b64"], expected_size=RAW_ED25519_PUBLIC_KEY_BYTES)
    return DecisionReceiptTrustStore(keys=keys)


def canonicalize_decision_receipt(receipt: TransparencyTrustDecisionReceiptPayload) -> bytes:
    return _canonicalize_mapping(receipt.model_dump(mode="json"))


def load_transparency_trust_decision_receipt(*, path: Path) -> TransparencyTrustDecisionReceiptEnvelope:
    if path.is_symlink() or path.is_dir():
        raise TransparencyDecisionReceiptError(_MESSAGE)
    try:
        if not path.is_file() or path.stat().st_size > MAX_DECISION_RECEIPT_BYTES:
            raise TransparencyDecisionReceiptError(_MESSAGE)
        return TransparencyTrustDecisionReceiptEnvelope.model_validate_json(
            json.dumps(_loads_no_duplicate_keys(path.read_text(encoding="utf-8")))
        )
    except OSError as error:
        raise TransparencyDecisionReceiptError(_MESSAGE) from error
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise TransparencyDecisionReceiptError(_MESSAGE) from error


def export_transparency_trust_decision_receipt(
    *, path: Path, envelope: TransparencyTrustDecisionReceiptEnvelope
) -> None:
    text = json.dumps(envelope.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=False)
    if path.exists():
        try:
            existing = load_transparency_trust_decision_receipt(path=path)
        except TransparencyDecisionReceiptError as error:
            raise TransparencyDecisionReceiptConflictError(_CONFLICT_MESSAGE) from error
        if existing == envelope:
            return
        raise TransparencyDecisionReceiptConflictError(_CONFLICT_MESSAGE)
    _atomic_export(path=path, text=text)


def _atomic_export(*, path: Path, text: str) -> None:
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
            os.chmod(temp_path, DECISION_RECEIPT_FILE_MODE)
        os.replace(temp_path, path)
        replaced = True
        dir_fd = os.open(path.parent, os.O_RDONLY)
        os.fsync(dir_fd)
    except OSError as error:
        raise TransparencyDecisionReceiptError(_MESSAGE) from error
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


def _load_json(*, path: Path) -> object:
    if path.is_symlink() or path.is_dir():
        raise TransparencyDecisionReceiptError(_MESSAGE)
    try:
        if not path.is_file() or path.stat().st_size > MAX_DECISION_RECEIPT_BYTES:
            raise TransparencyDecisionReceiptError(_MESSAGE)
        return _loads_no_duplicate_keys(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise TransparencyDecisionReceiptError(_MESSAGE) from error


def _loads_no_duplicate_keys(text: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TransparencyDecisionReceiptError(_MESSAGE)
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)


def _canonicalize_mapping(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        default=_json_default,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return normalize_aware_datetime(value).isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError("unsupported value")


def _env_text(environ: dict[str, str] | os._Environ[str], name: str) -> str:
    value = environ.get(name)  # type: ignore[attr-defined]
    if not value:
        raise TransparencyDecisionReceiptError(_CONFIG_MESSAGE)
    return value


def _env_b64(environ: dict[str, str] | os._Environ[str], name: str, expected_size: int) -> bytes:
    return _decode_b64(_env_text(environ, name), expected_size=expected_size)


def _decode_b64(value: object, *, expected_size: int) -> bytes:
    if not isinstance(value, str) or not value:
        raise TransparencyDecisionReceiptError(_CONFIG_MESSAGE)
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError, ValueError) as error:
        raise TransparencyDecisionReceiptError(_CONFIG_MESSAGE) from error
    if len(decoded) != expected_size:
        raise TransparencyDecisionReceiptError(_CONFIG_MESSAGE)
    return decoded
