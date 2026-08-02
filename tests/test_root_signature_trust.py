from __future__ import annotations

import base64
from dataclasses import FrozenInstanceError

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.exceptions import (
    InvalidRootSigningPrivateKeyError,
    InvalidRootSigningPublicKeyError,
    MissingRootSigningPrivateKeyError,
    MissingRootSigningPublicKeyError,
    RootSigningKeyIdError,
    RootSigningKeyMismatchError,
)
from app.root_signature_trust import (
    RAW_ED25519_PRIVATE_KEY_BYTES,
    RAW_ED25519_PUBLIC_KEY_BYTES,
    ROOT_ED25519_KEY_ID_ENV_NAME,
    ROOT_ED25519_PRIVATE_KEY_ENV_NAME,
    ROOT_ED25519_PUBLIC_KEY_ENV_NAME,
    RootSigningPrivateKey,
    TrustedRootSigningPublicKey,
    ensure_root_key_pair_matches,
    fingerprint_public_key,
    load_root_signing_private_key,
    load_trusted_root_public_key,
)

PRIVATE_TEXT = "PRIVATE-ROOT-KEY"


def private_bytes() -> bytes:
    return Ed25519PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def public_bytes(secret: bytes) -> bytes:
    return Ed25519PrivateKey.from_private_bytes(secret).public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def test_load_root_private_key_derives_public_key_and_hides_secret() -> None:
    secret = private_bytes()
    loaded = load_root_signing_private_key(
        environ={
            ROOT_ED25519_PRIVATE_KEY_ENV_NAME: b64(secret),
            ROOT_ED25519_KEY_ID_ENV_NAME: "root-key",
        }
    )

    assert loaded.key_id == "root-key"
    assert loaded.private_key_bytes == secret
    assert loaded.public_key_bytes == public_bytes(secret)
    assert len(loaded.private_key_bytes) == RAW_ED25519_PRIVATE_KEY_BYTES
    assert len(loaded.public_key_bytes) == RAW_ED25519_PUBLIC_KEY_BYTES
    assert secret not in repr(loaded).encode()


def test_load_trusted_root_public_key() -> None:
    secret = private_bytes()
    public = public_bytes(secret)

    loaded = load_trusted_root_public_key(
        environ={
            ROOT_ED25519_PUBLIC_KEY_ENV_NAME: b64(public),
            ROOT_ED25519_KEY_ID_ENV_NAME: "root-key",
        }
    )

    assert loaded.key_id == "root-key"
    assert loaded.public_key_bytes == public
    assert loaded.public_key_fingerprint == fingerprint_public_key(public)


def test_root_key_pair_match_uses_same_public_key() -> None:
    secret = private_bytes()
    private = RootSigningPrivateKey(
        "root-key",
        secret,
        public_bytes(secret),
        fingerprint_public_key(public_bytes(secret)),
    )
    public = TrustedRootSigningPublicKey(
        "root-key",
        public_bytes(secret),
        fingerprint_public_key(public_bytes(secret)),
    )

    ensure_root_key_pair_matches(private_key=private, public_key=public)


def test_root_key_pair_mismatch_is_rejected() -> None:
    first = private_bytes()
    second = private_bytes()
    private = RootSigningPrivateKey(
        "root-key",
        first,
        public_bytes(first),
        fingerprint_public_key(public_bytes(first)),
    )
    public = TrustedRootSigningPublicKey(
        "root-key",
        public_bytes(second),
        fingerprint_public_key(public_bytes(second)),
    )

    with pytest.raises(RootSigningKeyMismatchError):
        ensure_root_key_pair_matches(private_key=private, public_key=public)


def test_root_private_missing_and_invalid_values_hide_raw_environment() -> None:
    with pytest.raises(MissingRootSigningPrivateKeyError):
        load_root_signing_private_key(environ={})

    with pytest.raises(InvalidRootSigningPrivateKeyError) as exc_info:
        load_root_signing_private_key(
            environ={
                ROOT_ED25519_PRIVATE_KEY_ENV_NAME: PRIVATE_TEXT,
                ROOT_ED25519_KEY_ID_ENV_NAME: "root-key",
            }
        )

    assert PRIVATE_TEXT not in str(exc_info.value)


def test_root_public_missing_and_invalid_values_hide_raw_environment() -> None:
    with pytest.raises(MissingRootSigningPublicKeyError):
        load_trusted_root_public_key(environ={})

    with pytest.raises(InvalidRootSigningPublicKeyError) as exc_info:
        load_trusted_root_public_key(
            environ={
                ROOT_ED25519_PUBLIC_KEY_ENV_NAME: PRIVATE_TEXT,
                ROOT_ED25519_KEY_ID_ENV_NAME: "root-key",
            }
        )

    assert PRIVATE_TEXT not in str(exc_info.value)


def test_root_key_id_validation_and_frozen_model() -> None:
    secret = private_bytes()
    with pytest.raises(RootSigningKeyIdError):
        RootSigningPrivateKey(
            "bad key",
            secret,
            public_bytes(secret),
            fingerprint_public_key(public_bytes(secret)),
        )

    loaded = load_root_signing_private_key(
        environ={
            ROOT_ED25519_PRIVATE_KEY_ENV_NAME: b64(secret),
            ROOT_ED25519_KEY_ID_ENV_NAME: "root-key",
        }
    )
    with pytest.raises(FrozenInstanceError):
        loaded.key_id = "changed"  # type: ignore[misc]
