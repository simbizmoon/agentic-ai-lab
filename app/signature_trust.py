"""Ed25519 signing key and public trust store helpers for archive signatures."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.authentication_keyring import is_valid_key_id
from app.exceptions import (
    ArchiveSignatureFromFutureError,
    ArchiveSigningKeyFingerprintMismatchError,
    ArchiveSigningKeyNotActiveError,
    ArchiveSigningKeyNotValidError,
    DuplicateArchiveSigningKeyIdError,
    InvalidArchiveSignatureTrustStoreError,
    InvalidArchiveSigningKeyIdError,
    InvalidArchiveSigningPrivateKeyError,
    MissingArchiveSigningPrivateKeyError,
    RejectedArchiveSigningKeyError,
    UnknownArchiveSigningKeyError,
)

ED25519_PRIVATE_KEY_ENV_NAME = "AUDIT_REPORT_ED25519_PRIVATE_KEY_B64"
ED25519_SIGNING_KEY_ID_ENV_NAME = "AUDIT_REPORT_ED25519_SIGNING_KEY_ID"
ED25519_PUBLIC_TRUST_STORE_ENV_NAME = "AUDIT_REPORT_ED25519_PUBLIC_TRUST_STORE_JSON"

ED25519_RAW_PRIVATE_KEY_BYTES = 32
ED25519_RAW_PUBLIC_KEY_BYTES = 32
ED25519_SIGNATURE_BYTES = 64

_MISSING_PRIVATE_KEY_MESSAGE = "The audit report archive signing private key is missing."
_INVALID_PRIVATE_KEY_MESSAGE = "The audit report archive signing private key is invalid."
_INVALID_KEY_ID_MESSAGE = "The audit report archive signing key ID is invalid."
_INVALID_TRUST_STORE_MESSAGE = "The audit report archive signature trust store is invalid."
_DUPLICATE_KEY_ID_MESSAGE = "Archive signing key IDs must be unique."
_UNKNOWN_KEY_MESSAGE = "The archive signing key ID is not available."
_NOT_ACTIVE_MESSAGE = "The archive signing key is not active for signing."
_NOT_VALID_MESSAGE = "The archive signing key was not valid at signing time."
_REJECTED_MESSAGE = "The archive signing key is revoked."
_FUTURE_SIGNATURE_MESSAGE = "The archive signature time is too far in the future."
_FINGERPRINT_MISMATCH_MESSAGE = "The archive signing key fingerprint does not match."


class SignatureKeyStatus(str, Enum):
    ACTIVE = "active"
    VERIFY_ONLY = "verify_only"
    REVOKED = "revoked"


class RevokedSignatureKeyPolicy(str, Enum):
    REJECT = "reject"
    ALLOW_PRE_REVOCATION = "allow_pre_revocation"


@dataclass(frozen=True)
class ArchiveSigningPrivateKey:
    key_id: str
    private_key_bytes: bytes = field(repr=False)
    public_key_bytes: bytes = field(repr=False)
    public_key_fingerprint: str

    def __post_init__(self) -> None:
        if not is_valid_key_id(self.key_id):
            raise InvalidArchiveSigningKeyIdError(_INVALID_KEY_ID_MESSAGE)
        if not isinstance(self.private_key_bytes, bytes):
            raise InvalidArchiveSigningPrivateKeyError(_INVALID_PRIVATE_KEY_MESSAGE)
        if len(self.private_key_bytes) != ED25519_RAW_PRIVATE_KEY_BYTES:
            raise InvalidArchiveSigningPrivateKeyError(_INVALID_PRIVATE_KEY_MESSAGE)
        if not isinstance(self.public_key_bytes, bytes):
            raise InvalidArchiveSigningPrivateKeyError(_INVALID_PRIVATE_KEY_MESSAGE)
        if len(self.public_key_bytes) != ED25519_RAW_PUBLIC_KEY_BYTES:
            raise InvalidArchiveSigningPrivateKeyError(_INVALID_PRIVATE_KEY_MESSAGE)
        derived_public_key = _derive_public_key_bytes(self.private_key_bytes)
        if derived_public_key != self.public_key_bytes:
            raise InvalidArchiveSigningPrivateKeyError(_INVALID_PRIVATE_KEY_MESSAGE)
        expected_fingerprint = fingerprint_public_key(self.public_key_bytes)
        if self.public_key_fingerprint != expected_fingerprint:
            raise ArchiveSigningKeyFingerprintMismatchError(_FINGERPRINT_MISMATCH_MESSAGE)


@dataclass(frozen=True)
class TrustedArchiveSigningPublicKey:
    key_id: str
    public_key_bytes: bytes = field(repr=False)
    public_key_fingerprint: str
    status: SignatureKeyStatus
    valid_from: datetime
    valid_until: datetime | None = None
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        if not is_valid_key_id(self.key_id):
            raise InvalidArchiveSigningKeyIdError(_INVALID_KEY_ID_MESSAGE)
        if not isinstance(self.public_key_bytes, bytes):
            raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
        if len(self.public_key_bytes) != ED25519_RAW_PUBLIC_KEY_BYTES:
            raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
        if self.public_key_fingerprint != fingerprint_public_key(self.public_key_bytes):
            raise ArchiveSigningKeyFingerprintMismatchError(_FINGERPRINT_MISMATCH_MESSAGE)
        if not isinstance(self.status, SignatureKeyStatus):
            raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)

        valid_from = _normalize_aware_datetime(self.valid_from)
        valid_until = _normalize_optional_aware_datetime(self.valid_until)
        revoked_at = _normalize_optional_aware_datetime(self.revoked_at)
        if valid_until is not None and valid_until <= valid_from:
            raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
        if revoked_at is not None and revoked_at < valid_from:
            raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
        if self.status in {SignatureKeyStatus.ACTIVE, SignatureKeyStatus.VERIFY_ONLY} and revoked_at is not None:
            raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
        if self.status is SignatureKeyStatus.REVOKED and revoked_at is None:
            raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)

        object.__setattr__(self, "valid_from", valid_from)
        object.__setattr__(self, "valid_until", valid_until)
        object.__setattr__(self, "revoked_at", revoked_at)


@dataclass(frozen=True)
class ArchiveSignatureTrustStore:
    keys: tuple[TrustedArchiveSigningPublicKey, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.keys, tuple):
            raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
        seen: set[str] = set()
        for key in self.keys:
            if not isinstance(key, TrustedArchiveSigningPublicKey):
                raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
            if key.key_id in seen:
                raise DuplicateArchiveSigningKeyIdError(_DUPLICATE_KEY_ID_MESSAGE)
            seen.add(key.key_id)

    def get_key(self, key_id: str) -> TrustedArchiveSigningPublicKey:
        if not is_valid_key_id(key_id):
            raise InvalidArchiveSigningKeyIdError(_INVALID_KEY_ID_MESSAGE)
        for key in self.keys:
            if key.key_id == key_id:
                return key
        raise UnknownArchiveSigningKeyError(_UNKNOWN_KEY_MESSAGE)


def fingerprint_public_key(public_key_bytes: bytes) -> str:
    if not isinstance(public_key_bytes, bytes):
        raise TypeError("public_key_bytes must be bytes")
    return hashlib.sha256(public_key_bytes).hexdigest()


def load_archive_signing_private_key(
    *,
    environ: Mapping[str, str],
) -> ArchiveSigningPrivateKey:
    if not isinstance(environ, Mapping):
        raise TypeError("environ must be a Mapping")
    if (
        ED25519_PRIVATE_KEY_ENV_NAME not in environ
        or ED25519_SIGNING_KEY_ID_ENV_NAME not in environ
        or not environ[ED25519_PRIVATE_KEY_ENV_NAME]
        or not environ[ED25519_SIGNING_KEY_ID_ENV_NAME]
    ):
        raise MissingArchiveSigningPrivateKeyError(_MISSING_PRIVATE_KEY_MESSAGE)
    key_id = environ[ED25519_SIGNING_KEY_ID_ENV_NAME]
    if not is_valid_key_id(key_id):
        raise InvalidArchiveSigningKeyIdError(_INVALID_KEY_ID_MESSAGE)
    private_key_bytes = _decode_private_key_b64(environ[ED25519_PRIVATE_KEY_ENV_NAME])
    public_key_bytes = _derive_public_key_bytes(private_key_bytes)
    return ArchiveSigningPrivateKey(
        key_id=key_id,
        private_key_bytes=private_key_bytes,
        public_key_bytes=public_key_bytes,
        public_key_fingerprint=fingerprint_public_key(public_key_bytes),
    )


def load_archive_signature_trust_store(
    *,
    environ: Mapping[str, str],
) -> ArchiveSignatureTrustStore:
    if not isinstance(environ, Mapping):
        raise TypeError("environ must be a Mapping")
    if ED25519_PUBLIC_TRUST_STORE_ENV_NAME not in environ or not environ[ED25519_PUBLIC_TRUST_STORE_ENV_NAME]:
        raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    return _parse_public_trust_store_json(environ[ED25519_PUBLIC_TRUST_STORE_ENV_NAME])


def ensure_private_key_trusted_for_signing(
    *,
    signing_key: ArchiveSigningPrivateKey,
    trust_store: ArchiveSignatureTrustStore,
    signed_at: datetime,
) -> TrustedArchiveSigningPublicKey:
    if not isinstance(signing_key, ArchiveSigningPrivateKey):
        raise TypeError("signing_key must be an ArchiveSigningPrivateKey")
    signed_at = _normalize_aware_datetime(signed_at)
    key = trust_store.get_key(signing_key.key_id)
    if key.status is not SignatureKeyStatus.ACTIVE:
        raise ArchiveSigningKeyNotActiveError(_NOT_ACTIVE_MESSAGE)
    if signed_at < key.valid_from or (key.valid_until is not None and signed_at >= key.valid_until):
        raise ArchiveSigningKeyNotValidError(_NOT_VALID_MESSAGE)
    if key.public_key_bytes != signing_key.public_key_bytes:
        raise ArchiveSigningKeyFingerprintMismatchError(_FINGERPRINT_MISMATCH_MESSAGE)
    if key.public_key_fingerprint != signing_key.public_key_fingerprint:
        raise ArchiveSigningKeyFingerprintMismatchError(_FINGERPRINT_MISMATCH_MESSAGE)
    return key


def ensure_public_key_trusted_for_verification(
    *,
    key: TrustedArchiveSigningPublicKey,
    signed_at: datetime,
    verification_time: datetime,
    revoked_key_policy: RevokedSignatureKeyPolicy,
    maximum_clock_skew: timedelta,
) -> None:
    if not isinstance(key, TrustedArchiveSigningPublicKey):
        raise TypeError("key must be a TrustedArchiveSigningPublicKey")
    signed_at = _normalize_aware_datetime(signed_at)
    verification_time = _normalize_aware_datetime(verification_time)
    if not isinstance(maximum_clock_skew, timedelta) or maximum_clock_skew < timedelta(0):
        raise ValueError("maximum_clock_skew must be non-negative")
    if not isinstance(revoked_key_policy, RevokedSignatureKeyPolicy):
        raise TypeError("revoked_key_policy must be a RevokedSignatureKeyPolicy")

    if signed_at > verification_time + maximum_clock_skew:
        raise ArchiveSignatureFromFutureError(_FUTURE_SIGNATURE_MESSAGE)
    if signed_at < key.valid_from:
        raise ArchiveSigningKeyNotValidError(_NOT_VALID_MESSAGE)
    if key.valid_until is not None and signed_at >= key.valid_until:
        raise ArchiveSigningKeyNotValidError(_NOT_VALID_MESSAGE)

    if key.status in {SignatureKeyStatus.ACTIVE, SignatureKeyStatus.VERIFY_ONLY}:
        return
    if revoked_key_policy is RevokedSignatureKeyPolicy.REJECT:
        raise RejectedArchiveSigningKeyError(_REJECTED_MESSAGE)
    if key.revoked_at is None or signed_at >= key.revoked_at:
        raise RejectedArchiveSigningKeyError(_REJECTED_MESSAGE)


def parse_aware_datetime(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE) from error
    return _normalize_aware_datetime(parsed)


def _parse_public_trust_store_json(value: str) -> ArchiveSignatureTrustStore:
    if not isinstance(value, str) or not value:
        raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE) from error
    if not isinstance(payload, dict) or set(payload) != {"keys"}:
        raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    keys = payload["keys"]
    if not isinstance(keys, list):
        raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    return ArchiveSignatureTrustStore(keys=tuple(_parse_key_item(item) for item in keys))


def _parse_key_item(value: object) -> TrustedArchiveSigningPublicKey:
    if not isinstance(value, dict):
        raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    required = {"key_id", "public_key_b64", "status", "valid_from", "valid_until", "revoked_at"}
    if set(value) != required:
        raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    key_id = value["key_id"]
    if not is_valid_key_id(key_id):
        raise InvalidArchiveSigningKeyIdError(_INVALID_KEY_ID_MESSAGE)
    try:
        status = SignatureKeyStatus(value["status"])
    except ValueError as error:
        raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE) from error
    public_key_bytes = _decode_public_key_b64(value["public_key_b64"])
    return TrustedArchiveSigningPublicKey(
        key_id=key_id,
        public_key_bytes=public_key_bytes,
        public_key_fingerprint=fingerprint_public_key(public_key_bytes),
        status=status,
        valid_from=parse_aware_datetime(value["valid_from"]),
        valid_until=parse_aware_datetime(value["valid_until"]) if value["valid_until"] is not None else None,
        revoked_at=parse_aware_datetime(value["revoked_at"]) if value["revoked_at"] is not None else None,
    )


def _decode_private_key_b64(value: object) -> bytes:
    secret = _decode_b64(value, InvalidArchiveSigningPrivateKeyError, _INVALID_PRIVATE_KEY_MESSAGE)
    if len(secret) != ED25519_RAW_PRIVATE_KEY_BYTES:
        raise InvalidArchiveSigningPrivateKeyError(_INVALID_PRIVATE_KEY_MESSAGE)
    try:
        Ed25519PrivateKey.from_private_bytes(secret)
    except ValueError as error:
        raise InvalidArchiveSigningPrivateKeyError(_INVALID_PRIVATE_KEY_MESSAGE) from error
    return secret


def _decode_public_key_b64(value: object) -> bytes:
    public_key = _decode_b64(value, InvalidArchiveSignatureTrustStoreError, _INVALID_TRUST_STORE_MESSAGE)
    if len(public_key) != ED25519_RAW_PUBLIC_KEY_BYTES:
        raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    return public_key


def _decode_b64(value: object, exception_type: type[Exception], message: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise exception_type(message)
    try:
        encoded = value.encode("ascii")
        return base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError, UnicodeEncodeError) as error:
        raise exception_type(message) from error


def _derive_public_key_bytes(private_key_bytes: bytes) -> bytes:
    try:
        private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    except ValueError as error:
        raise InvalidArchiveSigningPrivateKeyError(_INVALID_PRIVATE_KEY_MESSAGE) from error
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _normalize_optional_aware_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return _normalize_aware_datetime(value)


def _normalize_aware_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidArchiveSignatureTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    return value.astimezone(UTC)
