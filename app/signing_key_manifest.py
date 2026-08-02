"""Signed public-key manifests for archive Ed25519 signing keys."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
    SigningKeyManifestDigestMismatchError,
    SigningKeyManifestExpiredError,
    SigningKeyManifestExportError,
    SigningKeyManifestFromFutureError,
    SigningKeyManifestMetadataMismatchError,
    SigningKeyManifestNotYetValidError,
    SigningKeyManifestReadError,
    SigningKeyManifestRollbackError,
    SigningKeyManifestSignatureVerificationError,
    SigningKeyManifestValidationError,
)
from app.manifest_trust_state import (
    ManifestTrustStateDecision,
    ManifestTrustStateMode,
    apply_manifest_trust_state,
)
from app.report_integrity import is_valid_sha256_digest
from app.root_signature_trust import RootSigningPrivateKey, TrustedRootSigningPublicKey
from app.root_trust_state import (
    RootTrustStatePayload,
    trusted_root_public_key_from_state,
)
from app.signature_trust import (
    ED25519_RAW_PUBLIC_KEY_BYTES,
    ED25519_SIGNATURE_BYTES,
    ArchiveSignatureTrustStore,
    SignatureKeyStatus,
    TrustedArchiveSigningPublicKey,
    fingerprint_public_key,
)

SIGNING_KEY_MANIFEST_VERSION = 1
SIGNING_KEY_MANIFEST_TYPE = "audit_report_archive_signing_keys"
KEY_MANIFEST_SIGNATURE_VERSION = 1
KEY_MANIFEST_SIGNATURE_TYPE = "archive_signing_key_manifest_ed25519"
KEY_MANIFEST_SIGNATURE_ALGORITHM = "ed25519-key-manifest-v1"
KEY_MANIFEST_SIGNATURE_DOMAIN_SEPARATOR = (
    b"agentic-ai-lab:"
    b"archive-signing-key-manifest:"
    b"ed25519:"
    b"v1"
)
MAX_KEY_MANIFEST_CLOCK_SKEW = timedelta(minutes=5)
MAX_SIGNING_KEY_MANIFEST_BYTES = 256 * 1024
MAX_SIGNING_KEY_MANIFEST_SIGNATURE_BYTES = 64 * 1024
MAX_SIGNING_KEY_MANIFEST_KEYS = 100
SIGNING_KEY_MANIFEST_PATH_ENV_NAME = "AUDIT_REPORT_SIGNING_KEY_MANIFEST_PATH"
MIN_SIGNING_KEY_MANIFEST_GENERATION_ENV_NAME = "AUDIT_REPORT_MIN_SIGNING_KEY_MANIFEST_GENERATION"

_VALIDATION_MESSAGE = "The archive signing key manifest failed validation."
_READ_MESSAGE = "Failed to read the archive signing key manifest."
_EXPORT_MESSAGE = "Failed to export the archive signing key manifest."
_SIGNATURE_MESSAGE = "The archive signing key manifest signature could not be verified."
_DIGEST_MESSAGE = "The archive signing key manifest digest does not match."
_METADATA_MESSAGE = "The archive signing key manifest metadata is inconsistent."
_ROLLBACK_MESSAGE = "The archive signing key manifest generation is too old."
_NOT_YET_VALID_MESSAGE = "The archive signing key manifest is not yet valid."
_EXPIRED_MESSAGE = "The archive signing key manifest has expired."
_FUTURE_MESSAGE = "The archive signing key manifest time is too far in the future."


class SigningKeyManifestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SigningKeyManifestIssuer(SigningKeyManifestModel):
    root_key_id: str
    root_key_fingerprint: str

    @field_validator("root_key_id")
    @classmethod
    def _validate_key_id(cls, value: str) -> str:
        if not is_valid_key_id(value):
            raise ValueError("invalid root key id")
        return value

    @field_validator("root_key_fingerprint")
    @classmethod
    def _validate_fingerprint(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid root key fingerprint")
        return value


class SigningKeyManifestEntry(SigningKeyManifestModel):
    key_id: str
    public_key_b64: str
    public_key_fingerprint: str
    status: SignatureKeyStatus
    valid_from: datetime
    valid_until: datetime | None
    revoked_at: datetime | None

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
            raise ValueError("invalid public key fingerprint")
        return value

    @field_validator("valid_from", "valid_until", "revoked_at")
    @classmethod
    def _validate_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _normalize_aware_datetime(value)

    @model_validator(mode="after")
    def _validate_entry(self) -> Self:
        public_key = _decode_public_key_b64(self.public_key_b64)
        if not hmac.compare_digest(self.public_key_fingerprint, fingerprint_public_key(public_key)):
            raise ValueError("fingerprint mismatch")
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("invalid validity window")
        if self.revoked_at is not None and self.revoked_at < self.valid_from:
            raise ValueError("invalid revocation time")
        if self.status in {SignatureKeyStatus.ACTIVE, SignatureKeyStatus.VERIFY_ONLY} and self.revoked_at is not None:
            raise ValueError("non-revoked status cannot have revoked_at")
        if self.status is SignatureKeyStatus.REVOKED and self.revoked_at is None:
            raise ValueError("revoked status requires revoked_at")
        return self


class SigningKeyManifestPayload(SigningKeyManifestModel):
    manifest_version: Literal[SIGNING_KEY_MANIFEST_VERSION]
    manifest_type: Literal[SIGNING_KEY_MANIFEST_TYPE]
    generation: int = Field(ge=1)
    issued_at: datetime
    valid_from: datetime
    valid_until: datetime
    issuer: SigningKeyManifestIssuer
    keys: list[SigningKeyManifestEntry] = Field(min_length=1, max_length=MAX_SIGNING_KEY_MANIFEST_KEYS)

    @field_validator("issued_at", "valid_from", "valid_until")
    @classmethod
    def _validate_datetime(cls, value: datetime) -> datetime:
        return _normalize_aware_datetime(value)

    @model_validator(mode="after")
    def _validate_manifest(self) -> Self:
        if self.valid_until <= self.valid_from:
            raise ValueError("invalid manifest validity window")
        if self.issued_at > self.valid_until:
            raise ValueError("issued_at must not be after valid_until")
        key_ids: set[str] = set()
        fingerprints: set[str] = set()
        public_keys: set[bytes] = set()
        active_count = 0
        for key in self.keys:
            public_key = _decode_public_key_b64(key.public_key_b64)
            if key.key_id in key_ids:
                raise ValueError("duplicate key id")
            if key.public_key_fingerprint in fingerprints:
                raise ValueError("duplicate fingerprint")
            if public_key in public_keys:
                raise ValueError("duplicate public key")
            key_ids.add(key.key_id)
            fingerprints.add(key.public_key_fingerprint)
            public_keys.add(public_key)
            if key.status is SignatureKeyStatus.ACTIVE:
                active_count += 1
        if active_count != 1:
            raise ValueError("manifest requires exactly one active key")
        return self


class SigningKeyManifestSignaturePayload(SigningKeyManifestModel):
    signature_version: Literal[KEY_MANIFEST_SIGNATURE_VERSION]
    signature_type: Literal[KEY_MANIFEST_SIGNATURE_TYPE]
    algorithm: Literal[KEY_MANIFEST_SIGNATURE_ALGORITHM]
    root_key_id: str
    root_key_fingerprint: str
    manifest_version: Literal[SIGNING_KEY_MANIFEST_VERSION]
    generation: int = Field(ge=1)
    signed_at: datetime
    manifest_sha256: str
    signature_b64: str
    filename: str

    @field_validator("root_key_id")
    @classmethod
    def _validate_key_id(cls, value: str) -> str:
        if not is_valid_key_id(value):
            raise ValueError("invalid root key id")
        return value

    @field_validator("root_key_fingerprint", "manifest_sha256")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid sha256")
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


@dataclass(frozen=True)
class SigningKeyManifestVerificationResult:
    manifest_version: int
    generation: int
    issued_at: datetime
    valid_from: datetime
    valid_until: datetime
    root_key_id: str
    root_key_fingerprint: str
    active_key_id: str
    key_count: int
    manifest_sha256: str


@dataclass(frozen=True)
class VerifiedSigningKeyManifest:
    result: SigningKeyManifestVerificationResult
    trust_store: ArchiveSignatureTrustStore


def canonicalize_signing_key_manifest(manifest: SigningKeyManifestPayload) -> bytes:
    if not isinstance(manifest, SigningKeyManifestPayload):
        raise TypeError("manifest must be a SigningKeyManifestPayload")
    return json.dumps(
        manifest.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def format_signing_key_manifest_json(manifest: SigningKeyManifestPayload) -> str:
    if not isinstance(manifest, SigningKeyManifestPayload):
        raise TypeError("manifest must be a SigningKeyManifestPayload")
    return json.dumps(
        manifest.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    )


def format_signing_key_manifest_signature_json(signature: SigningKeyManifestSignaturePayload) -> str:
    if not isinstance(signature, SigningKeyManifestSignaturePayload):
        raise TypeError("signature must be a SigningKeyManifestSignaturePayload")
    return json.dumps(
        signature.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    )


def validate_signing_key_manifest_json(json_text: str) -> SigningKeyManifestPayload:
    if not isinstance(json_text, str):
        raise TypeError("json_text must be a str")
    try:
        payload = _loads_no_duplicate_keys(json_text)
        if not isinstance(payload, dict):
            raise SigningKeyManifestValidationError(_VALIDATION_MESSAGE)
        return SigningKeyManifestPayload.model_validate_json(json.dumps(payload))
    except SigningKeyManifestValidationError:
        raise
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise SigningKeyManifestValidationError(_VALIDATION_MESSAGE) from error


def validate_signing_key_manifest_signature_json(json_text: str) -> SigningKeyManifestSignaturePayload:
    if not isinstance(json_text, str):
        raise TypeError("json_text must be a str")
    try:
        payload = _loads_no_duplicate_keys(json_text)
        if not isinstance(payload, dict):
            raise SigningKeyManifestValidationError(_VALIDATION_MESSAGE)
        return SigningKeyManifestSignaturePayload.model_validate_json(json.dumps(payload))
    except SigningKeyManifestValidationError:
        raise
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise SigningKeyManifestValidationError(_VALIDATION_MESSAGE) from error


def build_key_manifest_signature_message(
    *,
    canonical_manifest_bytes: bytes,
    manifest_sha256: str,
    root_key_id: str,
    manifest_version: int,
    generation: int,
) -> bytes:
    if not isinstance(canonical_manifest_bytes, bytes):
        raise TypeError("canonical_manifest_bytes must be bytes")
    if not is_valid_sha256_digest(manifest_sha256):
        raise SigningKeyManifestValidationError(_VALIDATION_MESSAGE)
    if not is_valid_key_id(root_key_id):
        raise SigningKeyManifestValidationError(_VALIDATION_MESSAGE)
    if not isinstance(manifest_version, int) or isinstance(manifest_version, bool) or manifest_version < 1:
        raise SigningKeyManifestValidationError(_VALIDATION_MESSAGE)
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 1:
        raise SigningKeyManifestValidationError(_VALIDATION_MESSAGE)
    return b"\0".join(
        (
            KEY_MANIFEST_SIGNATURE_DOMAIN_SEPARATOR,
            root_key_id.encode("ascii"),
            str(manifest_version).encode("ascii"),
            str(generation).encode("ascii"),
            manifest_sha256.encode("ascii"),
            canonical_manifest_bytes,
        )
    )


def build_signing_key_manifest(
    *,
    generation: int,
    issued_at: datetime,
    valid_from: datetime,
    valid_until: datetime,
    root_public_key: TrustedRootSigningPublicKey,
    keys: tuple[TrustedArchiveSigningPublicKey, ...],
) -> SigningKeyManifestPayload:
    if not isinstance(root_public_key, TrustedRootSigningPublicKey):
        raise TypeError("root_public_key must be a TrustedRootSigningPublicKey")
    if not isinstance(keys, tuple):
        raise TypeError("keys must be a tuple")
    return SigningKeyManifestPayload(
        manifest_version=SIGNING_KEY_MANIFEST_VERSION,
        manifest_type=SIGNING_KEY_MANIFEST_TYPE,
        generation=generation,
        issued_at=issued_at,
        valid_from=valid_from,
        valid_until=valid_until,
        issuer=SigningKeyManifestIssuer(
            root_key_id=root_public_key.key_id,
            root_key_fingerprint=root_public_key.public_key_fingerprint,
        ),
        keys=[_entry_from_trusted_key(key) for key in keys],
    )


def sign_signing_key_manifest(
    *,
    manifest: SigningKeyManifestPayload,
    root_private_key: RootSigningPrivateKey,
    signed_at: datetime,
    filename: str,
) -> SigningKeyManifestSignaturePayload:
    if not isinstance(root_private_key, RootSigningPrivateKey):
        raise TypeError("root_private_key must be a RootSigningPrivateKey")
    if manifest.issuer.root_key_id != root_private_key.key_id:
        raise SigningKeyManifestMetadataMismatchError(_METADATA_MESSAGE)
    if not hmac.compare_digest(
        manifest.issuer.root_key_fingerprint,
        root_private_key.public_key_fingerprint,
    ):
        raise SigningKeyManifestMetadataMismatchError(_METADATA_MESSAGE)
    if not _is_safe_json_filename(filename):
        raise SigningKeyManifestValidationError(_VALIDATION_MESSAGE)
    signed_at = _normalize_aware_datetime(signed_at)
    canonical = canonicalize_signing_key_manifest(manifest)
    manifest_sha256 = hashlib.sha256(canonical).hexdigest()
    message = build_key_manifest_signature_message(
        canonical_manifest_bytes=canonical,
        manifest_sha256=manifest_sha256,
        root_key_id=root_private_key.key_id,
        manifest_version=manifest.manifest_version,
        generation=manifest.generation,
    )
    signature = Ed25519PrivateKey.from_private_bytes(root_private_key.private_key_bytes).sign(message)
    if len(signature) != ED25519_SIGNATURE_BYTES:
        raise SigningKeyManifestValidationError(_VALIDATION_MESSAGE)
    return SigningKeyManifestSignaturePayload(
        signature_version=KEY_MANIFEST_SIGNATURE_VERSION,
        signature_type=KEY_MANIFEST_SIGNATURE_TYPE,
        algorithm=KEY_MANIFEST_SIGNATURE_ALGORITHM,
        root_key_id=root_private_key.key_id,
        root_key_fingerprint=root_private_key.public_key_fingerprint,
        manifest_version=manifest.manifest_version,
        generation=manifest.generation,
        signed_at=signed_at,
        manifest_sha256=manifest_sha256,
        signature_b64=base64.b64encode(signature).decode("ascii"),
        filename=filename,
    )


def export_signing_key_manifest(*, path: Path, manifest: SigningKeyManifestPayload) -> None:
    _export_json_file(path=path, text=format_signing_key_manifest_json(manifest), suffix=".json")


def export_signing_key_manifest_signature(
    *,
    path: Path,
    signature: SigningKeyManifestSignaturePayload,
) -> None:
    _export_json_file(path=path, text=format_signing_key_manifest_signature_json(signature), suffix=".sig")


def signing_key_manifest_signature_path_for(manifest_path: Path) -> Path:
    if not isinstance(manifest_path, Path):
        raise TypeError("manifest_path must be a Path")
    if manifest_path.suffix.lower() != ".json":
        raise SigningKeyManifestValidationError(_VALIDATION_MESSAGE)
    return manifest_path.with_name(f"{manifest_path.name}.sig")


def verify_signing_key_manifest(
    *,
    manifest_path: Path,
    root_public_key: TrustedRootSigningPublicKey,
    verification_time: datetime,
    minimum_generation: int = 1,
    signature_path: Path | None = None,
    maximum_clock_skew: timedelta = MAX_KEY_MANIFEST_CLOCK_SKEW,
) -> VerifiedSigningKeyManifest:
    if not isinstance(root_public_key, TrustedRootSigningPublicKey):
        raise TypeError("root_public_key must be a TrustedRootSigningPublicKey")
    verification_time = _normalize_aware_datetime(verification_time)
    if not isinstance(maximum_clock_skew, timedelta) or maximum_clock_skew < timedelta(0):
        raise ValueError("maximum_clock_skew must be non-negative")
    if not isinstance(minimum_generation, int) or isinstance(minimum_generation, bool) or minimum_generation < 1:
        raise SigningKeyManifestValidationError(_VALIDATION_MESSAGE)
    manifest_text = _read_text_file(manifest_path, MAX_SIGNING_KEY_MANIFEST_BYTES)
    manifest = validate_signing_key_manifest_json(manifest_text)
    effective_signature_path = signature_path or signing_key_manifest_signature_path_for(manifest_path)
    signature_text = _read_text_file(effective_signature_path, MAX_SIGNING_KEY_MANIFEST_SIGNATURE_BYTES)
    signature = validate_signing_key_manifest_signature_json(signature_text)

    if manifest.issuer.root_key_id != root_public_key.key_id:
        raise SigningKeyManifestMetadataMismatchError(_METADATA_MESSAGE)
    if not hmac.compare_digest(manifest.issuer.root_key_fingerprint, root_public_key.public_key_fingerprint):
        raise SigningKeyManifestMetadataMismatchError(_METADATA_MESSAGE)

    canonical = canonicalize_signing_key_manifest(manifest)
    manifest_sha256 = hashlib.sha256(canonical).hexdigest()
    if not hmac.compare_digest(signature.manifest_sha256, manifest_sha256):
        raise SigningKeyManifestDigestMismatchError(_DIGEST_MESSAGE)
    _validate_signature_metadata(signature, manifest, root_public_key, manifest_path.name)

    raw_signature = _decode_signature_b64(signature.signature_b64)
    message = build_key_manifest_signature_message(
        canonical_manifest_bytes=canonical,
        manifest_sha256=manifest_sha256,
        root_key_id=signature.root_key_id,
        manifest_version=signature.manifest_version,
        generation=signature.generation,
    )
    try:
        Ed25519PublicKey.from_public_bytes(root_public_key.public_key_bytes).verify(raw_signature, message)
    except (InvalidSignature, ValueError) as error:
        raise SigningKeyManifestSignatureVerificationError(_SIGNATURE_MESSAGE) from error

    _validate_manifest_time_policy(
        manifest=manifest,
        signature=signature,
        verification_time=verification_time,
        maximum_clock_skew=maximum_clock_skew,
    )
    if manifest.generation < minimum_generation:
        raise SigningKeyManifestRollbackError(_ROLLBACK_MESSAGE)

    trust_store = ArchiveSignatureTrustStore(keys=tuple(_trusted_key_from_entry(entry) for entry in manifest.keys))
    active_key_id = next(key.key_id for key in trust_store.keys if key.status is SignatureKeyStatus.ACTIVE)
    return VerifiedSigningKeyManifest(
        result=SigningKeyManifestVerificationResult(
            manifest_version=manifest.manifest_version,
            generation=manifest.generation,
            issued_at=manifest.issued_at,
            valid_from=manifest.valid_from,
            valid_until=manifest.valid_until,
            root_key_id=root_public_key.key_id,
            root_key_fingerprint=root_public_key.public_key_fingerprint,
            active_key_id=active_key_id,
            key_count=len(trust_store.keys),
            manifest_sha256=manifest_sha256,
        ),
        trust_store=trust_store,
    )


def verify_signing_key_manifest_with_state(
    *,
    manifest_path: Path,
    root_public_key: TrustedRootSigningPublicKey,
    verification_time: datetime,
    state_path: Path | None,
    minimum_generation: int = 1,
    state_mode: ManifestTrustStateMode = ManifestTrustStateMode.UPDATE,
    require_existing_state: bool = False,
    signature_path: Path | None = None,
    maximum_clock_skew: timedelta = MAX_KEY_MANIFEST_CLOCK_SKEW,
) -> tuple[VerifiedSigningKeyManifest, ManifestTrustStateDecision]:
    verified_manifest = verify_signing_key_manifest(
        manifest_path=manifest_path,
        root_public_key=root_public_key,
        verification_time=verification_time,
        minimum_generation=minimum_generation,
        signature_path=signature_path,
        maximum_clock_skew=maximum_clock_skew,
    )
    state_decision = apply_manifest_trust_state(
        verified_manifest=verified_manifest,
        state_path=state_path,
        verified_at=verification_time,
        configured_minimum_generation=minimum_generation,
        mode=state_mode,
        require_existing_state=require_existing_state,
    )
    return verified_manifest, state_decision


def verify_signing_key_manifest_with_root_state(
    *,
    manifest_path: Path,
    root_state: RootTrustStatePayload,
    verification_time: datetime,
    state_path: Path | None,
    minimum_generation: int = 1,
    state_mode: ManifestTrustStateMode = ManifestTrustStateMode.UPDATE,
    require_existing_state: bool = False,
    signature_path: Path | None = None,
    maximum_clock_skew: timedelta = MAX_KEY_MANIFEST_CLOCK_SKEW,
) -> tuple[VerifiedSigningKeyManifest, ManifestTrustStateDecision]:
    if not isinstance(root_state, RootTrustStatePayload):
        raise TypeError("root_state must be a RootTrustStatePayload")
    return verify_signing_key_manifest_with_state(
        manifest_path=manifest_path,
        root_public_key=trusted_root_public_key_from_state(root_state),
        verification_time=verification_time,
        state_path=state_path,
        minimum_generation=minimum_generation,
        state_mode=state_mode,
        require_existing_state=require_existing_state,
        signature_path=signature_path,
        maximum_clock_skew=maximum_clock_skew,
    )


def _entry_from_trusted_key(key: TrustedArchiveSigningPublicKey) -> SigningKeyManifestEntry:
    if not isinstance(key, TrustedArchiveSigningPublicKey):
        raise TypeError("key must be a TrustedArchiveSigningPublicKey")
    return SigningKeyManifestEntry(
        key_id=key.key_id,
        public_key_b64=base64.b64encode(key.public_key_bytes).decode("ascii"),
        public_key_fingerprint=key.public_key_fingerprint,
        status=key.status,
        valid_from=key.valid_from,
        valid_until=key.valid_until,
        revoked_at=key.revoked_at,
    )


def _trusted_key_from_entry(entry: SigningKeyManifestEntry) -> TrustedArchiveSigningPublicKey:
    return TrustedArchiveSigningPublicKey(
        key_id=entry.key_id,
        public_key_bytes=_decode_public_key_b64(entry.public_key_b64),
        public_key_fingerprint=entry.public_key_fingerprint,
        status=entry.status,
        valid_from=entry.valid_from,
        valid_until=entry.valid_until,
        revoked_at=entry.revoked_at,
    )


def _validate_signature_metadata(
    signature: SigningKeyManifestSignaturePayload,
    manifest: SigningKeyManifestPayload,
    root_public_key: TrustedRootSigningPublicKey,
    filename: str,
) -> None:
    if signature.root_key_id != root_public_key.key_id:
        raise SigningKeyManifestMetadataMismatchError(_METADATA_MESSAGE)
    if not hmac.compare_digest(signature.root_key_fingerprint, root_public_key.public_key_fingerprint):
        raise SigningKeyManifestMetadataMismatchError(_METADATA_MESSAGE)
    if signature.manifest_version != manifest.manifest_version:
        raise SigningKeyManifestMetadataMismatchError(_METADATA_MESSAGE)
    if signature.generation != manifest.generation:
        raise SigningKeyManifestMetadataMismatchError(_METADATA_MESSAGE)
    if signature.filename != filename:
        raise SigningKeyManifestMetadataMismatchError(_METADATA_MESSAGE)


def _validate_manifest_time_policy(
    *,
    manifest: SigningKeyManifestPayload,
    signature: SigningKeyManifestSignaturePayload,
    verification_time: datetime,
    maximum_clock_skew: timedelta,
) -> None:
    if manifest.issued_at > verification_time + maximum_clock_skew:
        raise SigningKeyManifestFromFutureError(_FUTURE_MESSAGE)
    if signature.signed_at > verification_time + maximum_clock_skew:
        raise SigningKeyManifestFromFutureError(_FUTURE_MESSAGE)
    if verification_time < manifest.valid_from:
        raise SigningKeyManifestNotYetValidError(_NOT_YET_VALID_MESSAGE)
    if verification_time >= manifest.valid_until:
        raise SigningKeyManifestExpiredError(_EXPIRED_MESSAGE)


def _read_text_file(path: Path, max_bytes: int) -> str:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink() or not path.is_file():
        raise SigningKeyManifestReadError(_READ_MESSAGE)
    try:
        if path.stat().st_size > max_bytes:
            raise SigningKeyManifestValidationError(_VALIDATION_MESSAGE)
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise SigningKeyManifestReadError(_READ_MESSAGE) from error


def _export_json_file(*, path: Path, text: str, suffix: str) -> None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.suffix.lower() != suffix:
        raise SigningKeyManifestValidationError(_VALIDATION_MESSAGE)
    if path.exists() and (path.is_dir() or path.is_symlink()):
        raise SigningKeyManifestValidationError(_VALIDATION_MESSAGE)
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
        raise SigningKeyManifestExportError(_EXPORT_MESSAGE) from error
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
                raise SigningKeyManifestValidationError(_VALIDATION_MESSAGE)
            result[key] = value
        return result

    return json.loads(json_text, object_pairs_hook=hook)


def _decode_public_key_b64(value: str) -> bytes:
    public_key = _decode_b64(value)
    if len(public_key) != ED25519_RAW_PUBLIC_KEY_BYTES:
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


def verify_signing_key_manifest_with_root_state_and_transparency(
    *,
    manifest_path: Path,
    root_state: RootTrustStatePayload,
    verification_time: datetime,
    state_path: Path | None,
    transparency_log_path: Path,
    transparency_state_path: Path,
    transparency_mode,
    minimum_generation: int = 1,
    state_mode: ManifestTrustStateMode = ManifestTrustStateMode.UPDATE,
    require_existing_state: bool = False,
    signature_path: Path | None = None,
    maximum_clock_skew: timedelta = MAX_KEY_MANIFEST_CLOCK_SKEW,
):
    from app.transparency_log import (
        TransparencyLogMode,
        register_verified_artifact,
        require_transparency_entry,
        transparency_artifact_from_verified_signing_key_manifest,
        verify_transparency_log,
    )

    verified_manifest, state_decision = verify_signing_key_manifest_with_root_state(
        manifest_path=manifest_path,
        root_state=root_state,
        verification_time=verification_time,
        state_path=state_path,
        minimum_generation=minimum_generation,
        state_mode=state_mode,
        require_existing_state=require_existing_state,
        signature_path=signature_path,
        maximum_clock_skew=maximum_clock_skew,
    )
    artifact = transparency_artifact_from_verified_signing_key_manifest(verified_manifest.result)
    mode = TransparencyLogMode(transparency_mode)
    if mode is TransparencyLogMode.REGISTER_IF_MISSING:
        log_result = register_verified_artifact(
            log_path=transparency_log_path,
            state_path=transparency_state_path,
            artifact=artifact,
            recorded_at=verification_time,
        )
        inclusion = log_result.inclusion
    else:
        verification = verify_transparency_log(
            log_path=transparency_log_path,
            state_path=transparency_state_path,
        )
        inclusion = require_transparency_entry(verification_result=verification, artifact=artifact)
    return verified_manifest, state_decision, inclusion
