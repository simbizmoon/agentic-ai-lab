"""Cross-signed Root Ed25519 transition manifests."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal, Self

from cryptography.exceptions import InvalidSignature
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

from app.authentication_keyring import is_valid_key_id
from app.exceptions import (
    RootTransitionDigestMismatchError,
    RootTransitionExpiredError,
    RootTransitionExportError,
    RootTransitionFromFutureError,
    RootTransitionMetadataMismatchError,
    RootTransitionReadError,
    RootTransitionSignatureVerificationError,
    RootTransitionValidationError,
)
from app.report_integrity import is_valid_sha256_digest
from app.root_signature_trust import (
    RAW_ED25519_PUBLIC_KEY_BYTES,
    RootSigningPrivateKey,
    TrustedRootSigningPublicKey,
    fingerprint_public_key,
)
from app.signature_trust import ED25519_SIGNATURE_BYTES

ROOT_TRANSITION_VERSION = 1
ROOT_TRANSITION_TYPE = "audit_report_root_key_transition"
ROOT_TRANSITION_GENERATION = 1
ROOT_TRANSITION_SIGNATURE_VERSION = 1
ROOT_TRANSITION_SIGNATURE_ALGORITHM = "ed25519-root-transition-v1"
ROOT_TRANSITION_OLD_SIGNATURE_TYPE = "root_transition_old_root_ed25519"
ROOT_TRANSITION_NEW_SIGNATURE_TYPE = "root_transition_new_root_ed25519"
ROOT_TRANSITION_SIGNATURE_DOMAIN_SEPARATOR = (
    b"agentic-ai-lab:"
    b"root-key-transition:"
    b"ed25519:"
    b"v1"
)
MAX_ROOT_TRANSITION_CLOCK_SKEW = timedelta(minutes=5)
MAX_ROOT_TRANSITION_BYTES = 256 * 1024
MAX_ROOT_TRANSITION_SIGNATURE_BYTES = 64 * 1024

_VALIDATION_MESSAGE = "The root transition manifest failed validation."
_READ_MESSAGE = "Failed to read the root transition manifest."
_EXPORT_MESSAGE = "Failed to export the root transition manifest."
_SIGNATURE_MESSAGE = "The root transition signature could not be verified."
_DIGEST_MESSAGE = "The root transition digest does not match."
_METADATA_MESSAGE = "The root transition metadata is inconsistent."
_EXPIRED_MESSAGE = "The root transition manifest has expired."
_FUTURE_MESSAGE = "The root transition manifest time is too far in the future."


class RootTransitionSignerRole(str, Enum):
    PREVIOUS_ROOT = "previous_root"
    NEXT_ROOT = "next_root"


class RootTransitionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RootTransitionKeyEntry(RootTransitionModel):
    epoch: int = Field(ge=1)
    key_id: str
    public_key_b64: str
    public_key_fingerprint: str

    @field_validator("key_id")
    @classmethod
    def _validate_key_id(cls, value: str) -> str:
        if not is_valid_key_id(value):
            raise ValueError("invalid key id")
        return value

    @field_validator("public_key_b64")
    @classmethod
    def _validate_public_key(cls, value: str) -> str:
        _decode_public_key_b64(value)
        return value

    @field_validator("public_key_fingerprint")
    @classmethod
    def _validate_fingerprint(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid fingerprint")
        return value

    @model_validator(mode="after")
    def _validate_fingerprint_match(self) -> Self:
        public_key = _decode_public_key_b64(self.public_key_b64)
        if not hmac.compare_digest(self.public_key_fingerprint, fingerprint_public_key(public_key)):
            raise ValueError("fingerprint mismatch")
        return self


class RootTransitionManifestPayload(RootTransitionModel):
    transition_version: Literal[ROOT_TRANSITION_VERSION]
    transition_type: Literal[ROOT_TRANSITION_TYPE]
    transition_generation: Literal[ROOT_TRANSITION_GENERATION]
    issued_at: datetime
    valid_from: datetime
    valid_until: datetime
    previous_root: RootTransitionKeyEntry
    next_root: RootTransitionKeyEntry

    @field_validator("issued_at", "valid_from", "valid_until")
    @classmethod
    def _validate_datetime(cls, value: datetime) -> datetime:
        return _normalize_aware_datetime(value)

    @model_validator(mode="after")
    def _validate_transition(self) -> Self:
        if self.next_root.epoch != self.previous_root.epoch + 1:
            raise ValueError("next root epoch must increment by one")
        if self.previous_root.key_id == self.next_root.key_id:
            raise ValueError("root key ids must differ")
        if hmac.compare_digest(_entry_public_key_bytes(self.previous_root), _entry_public_key_bytes(self.next_root)):
            raise ValueError("root public keys must differ")
        if hmac.compare_digest(self.previous_root.public_key_fingerprint, self.next_root.public_key_fingerprint):
            raise ValueError("root fingerprints must differ")
        if self.valid_until <= self.valid_from:
            raise ValueError("invalid validity window")
        if self.issued_at > self.valid_until:
            raise ValueError("issued_at must not exceed valid_until")
        return self


class RootTransitionSignaturePayload(RootTransitionModel):
    signature_version: Literal[ROOT_TRANSITION_SIGNATURE_VERSION]
    signature_type: str
    algorithm: Literal[ROOT_TRANSITION_SIGNATURE_ALGORITHM]
    signer_role: RootTransitionSignerRole
    signer_epoch: int = Field(ge=1)
    signer_key_id: str
    signer_public_key_fingerprint: str
    transition_version: Literal[ROOT_TRANSITION_VERSION]
    transition_generation: Literal[ROOT_TRANSITION_GENERATION]
    signed_at: datetime
    transition_sha256: str
    signature_b64: str
    filename: str

    @field_validator("signer_key_id")
    @classmethod
    def _validate_key_id(cls, value: str) -> str:
        if not is_valid_key_id(value):
            raise ValueError("invalid key id")
        return value

    @field_validator("signer_public_key_fingerprint", "transition_sha256")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid digest")
        return value

    @field_validator("signed_at")
    @classmethod
    def _validate_signed_at(cls, value: datetime) -> datetime:
        return _normalize_aware_datetime(value)

    @field_validator("signature_b64")
    @classmethod
    def _validate_signature(cls, value: str) -> str:
        signature = _decode_signature_b64(value)
        if len(signature) != ED25519_SIGNATURE_BYTES:
            raise ValueError("invalid signature length")
        return value

    @field_validator("filename")
    @classmethod
    def _validate_filename(cls, value: str) -> str:
        if not _is_safe_json_filename(value):
            raise ValueError("invalid filename")
        return value

    @model_validator(mode="after")
    def _validate_role_type(self) -> Self:
        expected = (
            ROOT_TRANSITION_OLD_SIGNATURE_TYPE
            if self.signer_role is RootTransitionSignerRole.PREVIOUS_ROOT
            else ROOT_TRANSITION_NEW_SIGNATURE_TYPE
        )
        if self.signature_type != expected:
            raise ValueError("signature type does not match signer role")
        return self


@dataclass(frozen=True)
class RootTransitionVerificationResult:
    transition_version: int
    transition_generation: int
    issued_at: datetime
    valid_from: datetime
    valid_until: datetime
    previous_root_epoch: int
    previous_root_key_id: str
    previous_root_fingerprint: str
    next_root_epoch: int
    next_root_key_id: str
    next_root_fingerprint: str
    transition_sha256: str
    is_active_for_application: bool


def canonicalize_root_transition(transition: RootTransitionManifestPayload) -> bytes:
    if not isinstance(transition, RootTransitionManifestPayload):
        raise TypeError("transition must be a RootTransitionManifestPayload")
    return json.dumps(
        transition.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def format_root_transition_json(transition: RootTransitionManifestPayload) -> str:
    if not isinstance(transition, RootTransitionManifestPayload):
        raise TypeError("transition must be a RootTransitionManifestPayload")
    return json.dumps(transition.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=False)


def format_root_transition_signature_json(signature: RootTransitionSignaturePayload) -> str:
    if not isinstance(signature, RootTransitionSignaturePayload):
        raise TypeError("signature must be a RootTransitionSignaturePayload")
    return json.dumps(signature.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=False)


def validate_root_transition_json(json_text: str) -> RootTransitionManifestPayload:
    if not isinstance(json_text, str):
        raise TypeError("json_text must be a str")
    try:
        payload = _loads_no_duplicate_keys(json_text)
        if not isinstance(payload, dict):
            raise RootTransitionValidationError(_VALIDATION_MESSAGE)
        return RootTransitionManifestPayload.model_validate_json(json.dumps(payload))
    except RootTransitionValidationError:
        raise
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise RootTransitionValidationError(_VALIDATION_MESSAGE) from error


def validate_root_transition_signature_json(json_text: str) -> RootTransitionSignaturePayload:
    if not isinstance(json_text, str):
        raise TypeError("json_text must be a str")
    try:
        payload = _loads_no_duplicate_keys(json_text)
        if not isinstance(payload, dict):
            raise RootTransitionValidationError(_VALIDATION_MESSAGE)
        return RootTransitionSignaturePayload.model_validate_json(json.dumps(payload))
    except RootTransitionValidationError:
        raise
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise RootTransitionValidationError(_VALIDATION_MESSAGE) from error


def build_root_transition_signature_message(
    *,
    canonical_transition_bytes: bytes,
    transition_sha256: str,
    transition_version: int,
    transition_generation: int,
    previous_root_epoch: int,
    previous_root_key_id: str,
    next_root_epoch: int,
    next_root_key_id: str,
) -> bytes:
    if not isinstance(canonical_transition_bytes, bytes):
        raise TypeError("canonical_transition_bytes must be bytes")
    if not is_valid_sha256_digest(transition_sha256):
        raise RootTransitionValidationError(_VALIDATION_MESSAGE)
    for value in (transition_version, transition_generation, previous_root_epoch, next_root_epoch):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise RootTransitionValidationError(_VALIDATION_MESSAGE)
    if not is_valid_key_id(previous_root_key_id) or not is_valid_key_id(next_root_key_id):
        raise RootTransitionValidationError(_VALIDATION_MESSAGE)
    return b"\0".join(
        (
            ROOT_TRANSITION_SIGNATURE_DOMAIN_SEPARATOR,
            str(transition_version).encode("ascii"),
            str(transition_generation).encode("ascii"),
            str(previous_root_epoch).encode("ascii"),
            previous_root_key_id.encode("ascii"),
            str(next_root_epoch).encode("ascii"),
            next_root_key_id.encode("ascii"),
            transition_sha256.encode("ascii"),
            canonical_transition_bytes,
        )
    )


def build_root_transition_manifest(
    *,
    issued_at: datetime,
    valid_from: datetime,
    valid_until: datetime,
    previous_root_public_key: TrustedRootSigningPublicKey,
    previous_root_epoch: int,
    next_root_public_key: TrustedRootSigningPublicKey,
    next_root_epoch: int,
) -> RootTransitionManifestPayload:
    if not isinstance(previous_root_public_key, TrustedRootSigningPublicKey):
        raise TypeError("previous_root_public_key must be a TrustedRootSigningPublicKey")
    if not isinstance(next_root_public_key, TrustedRootSigningPublicKey):
        raise TypeError("next_root_public_key must be a TrustedRootSigningPublicKey")
    try:
        return RootTransitionManifestPayload(
            transition_version=ROOT_TRANSITION_VERSION,
            transition_type=ROOT_TRANSITION_TYPE,
            transition_generation=ROOT_TRANSITION_GENERATION,
            issued_at=issued_at,
            valid_from=valid_from,
            valid_until=valid_until,
            previous_root=_entry_from_public_key(previous_root_public_key, previous_root_epoch),
            next_root=_entry_from_public_key(next_root_public_key, next_root_epoch),
        )
    except ValidationError as error:
        raise RootTransitionValidationError(_VALIDATION_MESSAGE) from error


def sign_root_transition(
    *,
    transition: RootTransitionManifestPayload,
    previous_root_private_key: RootSigningPrivateKey,
    next_root_private_key: RootSigningPrivateKey,
    signed_at: datetime,
    filename: str,
) -> tuple[RootTransitionSignaturePayload, RootTransitionSignaturePayload]:
    if not isinstance(transition, RootTransitionManifestPayload):
        raise TypeError("transition must be a RootTransitionManifestPayload")
    if not isinstance(previous_root_private_key, RootSigningPrivateKey):
        raise TypeError("previous_root_private_key must be a RootSigningPrivateKey")
    if not isinstance(next_root_private_key, RootSigningPrivateKey):
        raise TypeError("next_root_private_key must be a RootSigningPrivateKey")
    if not _is_safe_json_filename(filename):
        raise RootTransitionValidationError(_VALIDATION_MESSAGE)
    _ensure_private_key_matches_entry(previous_root_private_key, transition.previous_root)
    _ensure_private_key_matches_entry(next_root_private_key, transition.next_root)
    signed_at = _normalize_aware_datetime(signed_at)
    canonical = canonicalize_root_transition(transition)
    transition_sha256 = hashlib.sha256(canonical).hexdigest()
    message = _signature_message_for_transition(transition, canonical, transition_sha256)
    previous_signature = Ed25519PrivateKey.from_private_bytes(previous_root_private_key.private_key_bytes).sign(message)
    next_signature = Ed25519PrivateKey.from_private_bytes(next_root_private_key.private_key_bytes).sign(message)
    return (
        _signature_payload(
            role=RootTransitionSignerRole.PREVIOUS_ROOT,
            key=previous_root_private_key,
            entry=transition.previous_root,
            transition=transition,
            signed_at=signed_at,
            transition_sha256=transition_sha256,
            signature=previous_signature,
            filename=filename,
        ),
        _signature_payload(
            role=RootTransitionSignerRole.NEXT_ROOT,
            key=next_root_private_key,
            entry=transition.next_root,
            transition=transition,
            signed_at=signed_at,
            transition_sha256=transition_sha256,
            signature=next_signature,
            filename=filename,
        ),
    )


def previous_root_signature_path_for(transition_path: Path) -> Path:
    if not isinstance(transition_path, Path):
        raise TypeError("transition_path must be a Path")
    if transition_path.suffix.lower() != ".json":
        raise RootTransitionValidationError(_VALIDATION_MESSAGE)
    return transition_path.with_name(f"{transition_path.name}.previous-root.sig")


def next_root_signature_path_for(transition_path: Path) -> Path:
    if not isinstance(transition_path, Path):
        raise TypeError("transition_path must be a Path")
    if transition_path.suffix.lower() != ".json":
        raise RootTransitionValidationError(_VALIDATION_MESSAGE)
    return transition_path.with_name(f"{transition_path.name}.next-root.sig")


def export_root_transition_manifest(*, path: Path, transition: RootTransitionManifestPayload) -> None:
    _export_json_file(path=path, text=format_root_transition_json(transition), suffix=".json")


def export_root_transition_signature(*, path: Path, signature: RootTransitionSignaturePayload) -> None:
    _export_json_file(path=path, text=format_root_transition_signature_json(signature), suffix=".sig")


def verify_root_transition(
    *,
    transition_path: Path,
    current_root: TrustedRootSigningPublicKey,
    current_root_epoch: int,
    verification_time: datetime,
    previous_signature_path: Path | None = None,
    next_signature_path: Path | None = None,
    maximum_clock_skew: timedelta = MAX_ROOT_TRANSITION_CLOCK_SKEW,
) -> RootTransitionVerificationResult:
    if not isinstance(current_root, TrustedRootSigningPublicKey):
        raise TypeError("current_root must be a TrustedRootSigningPublicKey")
    if not isinstance(current_root_epoch, int) or isinstance(current_root_epoch, bool) or current_root_epoch < 1:
        raise RootTransitionValidationError(_VALIDATION_MESSAGE)
    verification_time = _normalize_aware_datetime(verification_time)
    if not isinstance(maximum_clock_skew, timedelta) or maximum_clock_skew < timedelta(0):
        raise ValueError("maximum_clock_skew must be non-negative")

    transition = validate_root_transition_json(_read_text_file(transition_path, MAX_ROOT_TRANSITION_BYTES))
    _ensure_current_root_matches_transition(
        transition=transition,
        current_root=current_root,
        current_root_epoch=current_root_epoch,
    )
    canonical = canonicalize_root_transition(transition)
    transition_sha256 = hashlib.sha256(canonical).hexdigest()
    message = _signature_message_for_transition(transition, canonical, transition_sha256)

    previous_signature = validate_root_transition_signature_json(
        _read_text_file(previous_signature_path or previous_root_signature_path_for(transition_path), MAX_ROOT_TRANSITION_SIGNATURE_BYTES)
    )
    next_signature = validate_root_transition_signature_json(
        _read_text_file(next_signature_path or next_root_signature_path_for(transition_path), MAX_ROOT_TRANSITION_SIGNATURE_BYTES)
    )
    _validate_signature_payload(
        signature=previous_signature,
        transition=transition,
        entry=transition.previous_root,
        role=RootTransitionSignerRole.PREVIOUS_ROOT,
        filename=transition_path.name,
        transition_sha256=transition_sha256,
    )
    _validate_signature_payload(
        signature=next_signature,
        transition=transition,
        entry=transition.next_root,
        role=RootTransitionSignerRole.NEXT_ROOT,
        filename=transition_path.name,
        transition_sha256=transition_sha256,
    )
    _verify_signature(
        public_key_bytes=current_root.public_key_bytes,
        signature_b64=previous_signature.signature_b64,
        message=message,
    )
    _verify_signature(
        public_key_bytes=_entry_public_key_bytes(transition.next_root),
        signature_b64=next_signature.signature_b64,
        message=message,
    )
    _validate_transition_time_policy(
        transition=transition,
        signatures=(previous_signature, next_signature),
        verification_time=verification_time,
        maximum_clock_skew=maximum_clock_skew,
    )
    return RootTransitionVerificationResult(
        transition_version=transition.transition_version,
        transition_generation=transition.transition_generation,
        issued_at=transition.issued_at,
        valid_from=transition.valid_from,
        valid_until=transition.valid_until,
        previous_root_epoch=transition.previous_root.epoch,
        previous_root_key_id=transition.previous_root.key_id,
        previous_root_fingerprint=transition.previous_root.public_key_fingerprint,
        next_root_epoch=transition.next_root.epoch,
        next_root_key_id=transition.next_root.key_id,
        next_root_fingerprint=transition.next_root.public_key_fingerprint,
        transition_sha256=transition_sha256,
        is_active_for_application=transition.valid_from <= verification_time < transition.valid_until,
    )


def _entry_from_public_key(public_key: TrustedRootSigningPublicKey, epoch: int) -> RootTransitionKeyEntry:
    return RootTransitionKeyEntry(
        epoch=epoch,
        key_id=public_key.key_id,
        public_key_b64=base64.b64encode(public_key.public_key_bytes).decode("ascii"),
        public_key_fingerprint=public_key.public_key_fingerprint,
    )


def _signature_payload(
    *,
    role: RootTransitionSignerRole,
    key: RootSigningPrivateKey,
    entry: RootTransitionKeyEntry,
    transition: RootTransitionManifestPayload,
    signed_at: datetime,
    transition_sha256: str,
    signature: bytes,
    filename: str,
) -> RootTransitionSignaturePayload:
    if len(signature) != ED25519_SIGNATURE_BYTES:
        raise RootTransitionValidationError(_VALIDATION_MESSAGE)
    return RootTransitionSignaturePayload(
        signature_version=ROOT_TRANSITION_SIGNATURE_VERSION,
        signature_type=ROOT_TRANSITION_OLD_SIGNATURE_TYPE
        if role is RootTransitionSignerRole.PREVIOUS_ROOT
        else ROOT_TRANSITION_NEW_SIGNATURE_TYPE,
        algorithm=ROOT_TRANSITION_SIGNATURE_ALGORITHM,
        signer_role=role,
        signer_epoch=entry.epoch,
        signer_key_id=key.key_id,
        signer_public_key_fingerprint=key.public_key_fingerprint,
        transition_version=transition.transition_version,
        transition_generation=transition.transition_generation,
        signed_at=signed_at,
        transition_sha256=transition_sha256,
        signature_b64=base64.b64encode(signature).decode("ascii"),
        filename=filename,
    )


def _signature_message_for_transition(
    transition: RootTransitionManifestPayload,
    canonical: bytes,
    transition_sha256: str,
) -> bytes:
    return build_root_transition_signature_message(
        canonical_transition_bytes=canonical,
        transition_sha256=transition_sha256,
        transition_version=transition.transition_version,
        transition_generation=transition.transition_generation,
        previous_root_epoch=transition.previous_root.epoch,
        previous_root_key_id=transition.previous_root.key_id,
        next_root_epoch=transition.next_root.epoch,
        next_root_key_id=transition.next_root.key_id,
    )


def _ensure_private_key_matches_entry(key: RootSigningPrivateKey, entry: RootTransitionKeyEntry) -> None:
    if key.key_id != entry.key_id:
        raise RootTransitionMetadataMismatchError(_METADATA_MESSAGE)
    if not hmac.compare_digest(key.public_key_bytes, _entry_public_key_bytes(entry)):
        raise RootTransitionMetadataMismatchError(_METADATA_MESSAGE)
    if not hmac.compare_digest(key.public_key_fingerprint, entry.public_key_fingerprint):
        raise RootTransitionMetadataMismatchError(_METADATA_MESSAGE)


def _ensure_current_root_matches_transition(
    *,
    transition: RootTransitionManifestPayload,
    current_root: TrustedRootSigningPublicKey,
    current_root_epoch: int,
) -> None:
    previous = transition.previous_root
    if previous.epoch != current_root_epoch or previous.key_id != current_root.key_id:
        raise RootTransitionMetadataMismatchError(_METADATA_MESSAGE)
    if not hmac.compare_digest(previous.public_key_fingerprint, current_root.public_key_fingerprint):
        raise RootTransitionMetadataMismatchError(_METADATA_MESSAGE)
    if not hmac.compare_digest(_entry_public_key_bytes(previous), current_root.public_key_bytes):
        raise RootTransitionMetadataMismatchError(_METADATA_MESSAGE)


def _validate_signature_payload(
    *,
    signature: RootTransitionSignaturePayload,
    transition: RootTransitionManifestPayload,
    entry: RootTransitionKeyEntry,
    role: RootTransitionSignerRole,
    filename: str,
    transition_sha256: str,
) -> None:
    if signature.signer_role is not role:
        raise RootTransitionMetadataMismatchError(_METADATA_MESSAGE)
    if signature.signer_epoch != entry.epoch or signature.signer_key_id != entry.key_id:
        raise RootTransitionMetadataMismatchError(_METADATA_MESSAGE)
    if not hmac.compare_digest(signature.signer_public_key_fingerprint, entry.public_key_fingerprint):
        raise RootTransitionMetadataMismatchError(_METADATA_MESSAGE)
    if signature.transition_version != transition.transition_version:
        raise RootTransitionMetadataMismatchError(_METADATA_MESSAGE)
    if signature.transition_generation != transition.transition_generation:
        raise RootTransitionMetadataMismatchError(_METADATA_MESSAGE)
    if signature.filename != filename:
        raise RootTransitionMetadataMismatchError(_METADATA_MESSAGE)
    if not hmac.compare_digest(signature.transition_sha256, transition_sha256):
        raise RootTransitionDigestMismatchError(_DIGEST_MESSAGE)


def _verify_signature(*, public_key_bytes: bytes, signature_b64: str, message: bytes) -> None:
    try:
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(_decode_signature_b64(signature_b64), message)
    except (InvalidSignature, ValueError) as error:
        raise RootTransitionSignatureVerificationError(_SIGNATURE_MESSAGE) from error


def _validate_transition_time_policy(
    *,
    transition: RootTransitionManifestPayload,
    signatures: tuple[RootTransitionSignaturePayload, RootTransitionSignaturePayload],
    verification_time: datetime,
    maximum_clock_skew: timedelta,
) -> None:
    if transition.issued_at > verification_time + maximum_clock_skew:
        raise RootTransitionFromFutureError(_FUTURE_MESSAGE)
    for signature in signatures:
        if signature.signed_at > verification_time + maximum_clock_skew:
            raise RootTransitionFromFutureError(_FUTURE_MESSAGE)
    if verification_time >= transition.valid_until:
        raise RootTransitionExpiredError(_EXPIRED_MESSAGE)


def _read_text_file(path: Path, max_bytes: int) -> str:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink() or not path.is_file():
        raise RootTransitionReadError(_READ_MESSAGE)
    try:
        if path.stat().st_size > max_bytes:
            raise RootTransitionValidationError(_VALIDATION_MESSAGE)
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise RootTransitionReadError(_READ_MESSAGE) from error


def _export_json_file(*, path: Path, text: str, suffix: str) -> None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.suffix.lower() != suffix:
        raise RootTransitionValidationError(_VALIDATION_MESSAGE)
    if path.exists() and (path.is_dir() or path.is_symlink()):
        raise RootTransitionValidationError(_VALIDATION_MESSAGE)
    temp_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(text.rstrip("\n") + "\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, path)
        temp_path = None
    except OSError as error:
        raise RootTransitionExportError(_EXPORT_MESSAGE) from error
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _loads_no_duplicate_keys(json_text: str) -> object:
    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RootTransitionValidationError(_VALIDATION_MESSAGE)
            result[key] = value
        return result

    return json.loads(json_text, object_pairs_hook=hook)


def _entry_public_key_bytes(entry: RootTransitionKeyEntry) -> bytes:
    return _decode_public_key_b64(entry.public_key_b64)


def _decode_public_key_b64(value: str) -> bytes:
    public_key = _decode_b64(value)
    if len(public_key) != RAW_ED25519_PUBLIC_KEY_BYTES:
        raise ValueError("invalid public key length")
    try:
        Ed25519PublicKey.from_public_bytes(public_key)
    except ValueError as error:
        raise ValueError("invalid public key") from error
    return public_key


def _decode_signature_b64(value: str) -> bytes:
    signature = _decode_b64(value)
    if len(signature) != ED25519_SIGNATURE_BYTES:
        raise ValueError("invalid signature length")
    return signature


def _decode_b64(value: object) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("invalid base64")
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError, ValueError) as error:
        raise ValueError("invalid base64") from error


def _normalize_aware_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("datetime required")  # noqa: TRY004
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone required")
    return value.astimezone(UTC)


def _is_safe_json_filename(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.endswith(".json")
        and value.strip() == value
        and value not in {".", ".."}
        and "/" not in value
        and "\\" not in value
        and "\0" not in value
        and Path(value).name == value
    )
