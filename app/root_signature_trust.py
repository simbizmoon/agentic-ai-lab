"""Root Ed25519 key loading for signing-key manifests."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass, field

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.authentication_keyring import is_valid_key_id
from app.exceptions import (
    InvalidRootSigningPrivateKeyError,
    InvalidRootSigningPublicKeyError,
    MissingRootSigningPrivateKeyError,
    MissingRootSigningPublicKeyError,
    RootSigningKeyIdError,
    RootSigningKeyMismatchError,
)

ROOT_ED25519_PRIVATE_KEY_ENV_NAME = "AUDIT_REPORT_ROOT_ED25519_PRIVATE_KEY_B64"
ROOT_ED25519_PUBLIC_KEY_ENV_NAME = "AUDIT_REPORT_ROOT_ED25519_PUBLIC_KEY_B64"
ROOT_ED25519_KEY_ID_ENV_NAME = "AUDIT_REPORT_ROOT_ED25519_KEY_ID"
RAW_ED25519_PRIVATE_KEY_BYTES = 32
RAW_ED25519_PUBLIC_KEY_BYTES = 32

_MISSING_PRIVATE_MESSAGE = "The archive signing root private key is missing."
_INVALID_PRIVATE_MESSAGE = "The archive signing root private key is invalid."
_MISSING_PUBLIC_MESSAGE = "The archive signing root public key is missing."
_INVALID_PUBLIC_MESSAGE = "The archive signing root public key is invalid."
_INVALID_KEY_ID_MESSAGE = "The archive signing root key ID is invalid."
_MISMATCH_MESSAGE = "The archive signing root key pair does not match."


@dataclass(frozen=True)
class RootSigningPrivateKey:
    key_id: str
    private_key_bytes: bytes = field(repr=False)
    public_key_bytes: bytes = field(repr=False)
    public_key_fingerprint: str

    def __post_init__(self) -> None:
        if not is_valid_key_id(self.key_id):
            raise RootSigningKeyIdError(_INVALID_KEY_ID_MESSAGE)
        if not isinstance(self.private_key_bytes, bytes):
            raise InvalidRootSigningPrivateKeyError(_INVALID_PRIVATE_MESSAGE)
        if len(self.private_key_bytes) != RAW_ED25519_PRIVATE_KEY_BYTES:
            raise InvalidRootSigningPrivateKeyError(_INVALID_PRIVATE_MESSAGE)
        if not isinstance(self.public_key_bytes, bytes):
            raise InvalidRootSigningPrivateKeyError(_INVALID_PRIVATE_MESSAGE)
        if len(self.public_key_bytes) != RAW_ED25519_PUBLIC_KEY_BYTES:
            raise InvalidRootSigningPrivateKeyError(_INVALID_PRIVATE_MESSAGE)
        derived_public = _derive_public_key_bytes(self.private_key_bytes)
        if not hmac.compare_digest(derived_public, self.public_key_bytes):
            raise InvalidRootSigningPrivateKeyError(_INVALID_PRIVATE_MESSAGE)
        expected = fingerprint_public_key(self.public_key_bytes)
        if not hmac.compare_digest(expected, self.public_key_fingerprint):
            raise InvalidRootSigningPrivateKeyError(_INVALID_PRIVATE_MESSAGE)


@dataclass(frozen=True)
class TrustedRootSigningPublicKey:
    key_id: str
    public_key_bytes: bytes = field(repr=False)
    public_key_fingerprint: str

    def __post_init__(self) -> None:
        if not is_valid_key_id(self.key_id):
            raise RootSigningKeyIdError(_INVALID_KEY_ID_MESSAGE)
        if not isinstance(self.public_key_bytes, bytes):
            raise InvalidRootSigningPublicKeyError(_INVALID_PUBLIC_MESSAGE)
        if len(self.public_key_bytes) != RAW_ED25519_PUBLIC_KEY_BYTES:
            raise InvalidRootSigningPublicKeyError(_INVALID_PUBLIC_MESSAGE)
        try:
            Ed25519PublicKey.from_public_bytes(self.public_key_bytes)
        except ValueError as error:
            raise InvalidRootSigningPublicKeyError(_INVALID_PUBLIC_MESSAGE) from error
        expected = fingerprint_public_key(self.public_key_bytes)
        if not hmac.compare_digest(expected, self.public_key_fingerprint):
            raise InvalidRootSigningPublicKeyError(_INVALID_PUBLIC_MESSAGE)


def load_root_signing_private_key(*, environ: Mapping[str, str]) -> RootSigningPrivateKey:
    if not isinstance(environ, Mapping):
        raise TypeError("environ must be a Mapping")
    if (
        ROOT_ED25519_PRIVATE_KEY_ENV_NAME not in environ
        or ROOT_ED25519_KEY_ID_ENV_NAME not in environ
        or not environ[ROOT_ED25519_PRIVATE_KEY_ENV_NAME]
        or not environ[ROOT_ED25519_KEY_ID_ENV_NAME]
    ):
        raise MissingRootSigningPrivateKeyError(_MISSING_PRIVATE_MESSAGE)
    key_id = environ[ROOT_ED25519_KEY_ID_ENV_NAME]
    if not is_valid_key_id(key_id):
        raise RootSigningKeyIdError(_INVALID_KEY_ID_MESSAGE)
    private_key_bytes = _decode_private_key_b64(environ[ROOT_ED25519_PRIVATE_KEY_ENV_NAME])
    public_key_bytes = _derive_public_key_bytes(private_key_bytes)
    return RootSigningPrivateKey(
        key_id=key_id,
        private_key_bytes=private_key_bytes,
        public_key_bytes=public_key_bytes,
        public_key_fingerprint=fingerprint_public_key(public_key_bytes),
    )


def load_trusted_root_public_key(*, environ: Mapping[str, str]) -> TrustedRootSigningPublicKey:
    if not isinstance(environ, Mapping):
        raise TypeError("environ must be a Mapping")
    if (
        ROOT_ED25519_PUBLIC_KEY_ENV_NAME not in environ
        or ROOT_ED25519_KEY_ID_ENV_NAME not in environ
        or not environ[ROOT_ED25519_PUBLIC_KEY_ENV_NAME]
        or not environ[ROOT_ED25519_KEY_ID_ENV_NAME]
    ):
        raise MissingRootSigningPublicKeyError(_MISSING_PUBLIC_MESSAGE)
    key_id = environ[ROOT_ED25519_KEY_ID_ENV_NAME]
    if not is_valid_key_id(key_id):
        raise RootSigningKeyIdError(_INVALID_KEY_ID_MESSAGE)
    public_key_bytes = _decode_public_key_b64(environ[ROOT_ED25519_PUBLIC_KEY_ENV_NAME])
    return TrustedRootSigningPublicKey(
        key_id=key_id,
        public_key_bytes=public_key_bytes,
        public_key_fingerprint=fingerprint_public_key(public_key_bytes),
    )


def ensure_root_key_pair_matches(
    *,
    private_key: RootSigningPrivateKey,
    public_key: TrustedRootSigningPublicKey,
) -> None:
    if not isinstance(private_key, RootSigningPrivateKey):
        raise TypeError("private_key must be a RootSigningPrivateKey")
    if not isinstance(public_key, TrustedRootSigningPublicKey):
        raise TypeError("public_key must be a TrustedRootSigningPublicKey")
    if private_key.key_id != public_key.key_id:
        raise RootSigningKeyMismatchError(_MISMATCH_MESSAGE)
    if not hmac.compare_digest(private_key.public_key_bytes, public_key.public_key_bytes):
        raise RootSigningKeyMismatchError(_MISMATCH_MESSAGE)
    if not hmac.compare_digest(private_key.public_key_fingerprint, public_key.public_key_fingerprint):
        raise RootSigningKeyMismatchError(_MISMATCH_MESSAGE)


def fingerprint_public_key(public_key_bytes: bytes) -> str:
    if not isinstance(public_key_bytes, bytes):
        raise TypeError("public_key_bytes must be bytes")
    return hashlib.sha256(public_key_bytes).hexdigest()


def _decode_private_key_b64(value: object) -> bytes:
    key = _decode_b64(value, InvalidRootSigningPrivateKeyError, _INVALID_PRIVATE_MESSAGE)
    if len(key) != RAW_ED25519_PRIVATE_KEY_BYTES:
        raise InvalidRootSigningPrivateKeyError(_INVALID_PRIVATE_MESSAGE)
    try:
        Ed25519PrivateKey.from_private_bytes(key)
    except ValueError as error:
        raise InvalidRootSigningPrivateKeyError(_INVALID_PRIVATE_MESSAGE) from error
    return key


def _decode_public_key_b64(value: object) -> bytes:
    key = _decode_b64(value, InvalidRootSigningPublicKeyError, _INVALID_PUBLIC_MESSAGE)
    if len(key) != RAW_ED25519_PUBLIC_KEY_BYTES:
        raise InvalidRootSigningPublicKeyError(_INVALID_PUBLIC_MESSAGE)
    try:
        Ed25519PublicKey.from_public_bytes(key)
    except ValueError as error:
        raise InvalidRootSigningPublicKeyError(_INVALID_PUBLIC_MESSAGE) from error
    return key


def _decode_b64(value: object, exception_type: type[Exception], message: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise exception_type(message)
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError, ValueError) as error:
        raise exception_type(message) from error


def _derive_public_key_bytes(private_key_bytes: bytes) -> bytes:
    try:
        private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    except ValueError as error:
        raise InvalidRootSigningPrivateKeyError(_INVALID_PRIVATE_MESSAGE) from error
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
