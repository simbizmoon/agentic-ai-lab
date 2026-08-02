from __future__ import annotations

import base64
import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

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
from app.signature_trust import (
    ED25519_PRIVATE_KEY_ENV_NAME,
    ED25519_PUBLIC_TRUST_STORE_ENV_NAME,
    ED25519_RAW_PRIVATE_KEY_BYTES,
    ED25519_RAW_PUBLIC_KEY_BYTES,
    ED25519_SIGNING_KEY_ID_ENV_NAME,
    ArchiveSignatureTrustStore,
    ArchiveSigningPrivateKey,
    RevokedSignatureKeyPolicy,
    SignatureKeyStatus,
    TrustedArchiveSigningPublicKey,
    ensure_private_key_trusted_for_signing,
    ensure_public_key_trusted_for_verification,
    fingerprint_public_key,
    load_archive_signature_trust_store,
    load_archive_signing_private_key,
)

VALID_FROM = datetime(2026, 8, 1, tzinfo=UTC)
SIGNED_AT = datetime(2026, 8, 2, tzinfo=UTC)
VERIFY_TIME = datetime(2026, 8, 2, 0, 1, tzinfo=UTC)
PRIVATE_SECRET_TEXT = "SUPER-SECRET-ED25519-PRIVATE-KEY"


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


def private_key(key_id: str = "sig-key") -> ArchiveSigningPrivateKey:
    secret = private_bytes()
    public = public_bytes(secret)
    return ArchiveSigningPrivateKey(
        key_id=key_id,
        private_key_bytes=secret,
        public_key_bytes=public,
        public_key_fingerprint=fingerprint_public_key(public),
    )


def trusted_key(
    signing_key: ArchiveSigningPrivateKey,
    *,
    status: SignatureKeyStatus = SignatureKeyStatus.ACTIVE,
    valid_from: datetime = VALID_FROM,
    valid_until: datetime | None = None,
    revoked_at: datetime | None = None,
) -> TrustedArchiveSigningPublicKey:
    return TrustedArchiveSigningPublicKey(
        key_id=signing_key.key_id,
        public_key_bytes=signing_key.public_key_bytes,
        public_key_fingerprint=signing_key.public_key_fingerprint,
        status=status,
        valid_from=valid_from,
        valid_until=valid_until,
        revoked_at=revoked_at,
    )


def trust_store_payload(key: TrustedArchiveSigningPublicKey) -> str:
    return json.dumps(
        {
            "keys": [
                {
                    "key_id": key.key_id,
                    "public_key_b64": b64(key.public_key_bytes),
                    "status": key.status.value,
                    "valid_from": key.valid_from.isoformat(),
                    "valid_until": key.valid_until.isoformat() if key.valid_until else None,
                    "revoked_at": key.revoked_at.isoformat() if key.revoked_at else None,
                }
            ]
        }
    )


def test_signature_key_status_values() -> None:
    assert SignatureKeyStatus.ACTIVE.value == "active"
    assert SignatureKeyStatus.VERIFY_ONLY.value == "verify_only"
    assert SignatureKeyStatus.REVOKED.value == "revoked"


def test_revoked_signature_policy_values() -> None:
    assert RevokedSignatureKeyPolicy.REJECT.value == "reject"
    assert RevokedSignatureKeyPolicy.ALLOW_PRE_REVOCATION.value == "allow_pre_revocation"


def test_private_key_model_validates_lengths_and_hides_secret() -> None:
    key = private_key()

    assert len(key.private_key_bytes) == ED25519_RAW_PRIVATE_KEY_BYTES
    assert len(key.public_key_bytes) == ED25519_RAW_PUBLIC_KEY_BYTES
    assert key.private_key_bytes not in repr(key).encode()
    assert key.public_key_bytes not in repr(key).encode()


def test_private_key_rejects_bad_key_id() -> None:
    secret = private_bytes()
    with pytest.raises(InvalidArchiveSigningKeyIdError):
        ArchiveSigningPrivateKey("bad id", secret, public_bytes(secret), fingerprint_public_key(public_bytes(secret)))


def test_private_key_rejects_wrong_private_length() -> None:
    with pytest.raises(InvalidArchiveSigningPrivateKeyError):
        ArchiveSigningPrivateKey("sig-key", b"x" * 31, b"p" * 32, "0" * 64)


def test_private_key_rejects_public_mismatch() -> None:
    first = private_bytes()
    second_public = public_bytes(private_bytes())
    with pytest.raises(InvalidArchiveSigningPrivateKeyError):
        ArchiveSigningPrivateKey(
            "sig-key",
            first,
            second_public,
            fingerprint_public_key(second_public),
        )


def test_trusted_key_validates_state_and_normalizes_utc() -> None:
    key = private_key()
    trusted = TrustedArchiveSigningPublicKey(
        key.key_id,
        key.public_key_bytes,
        key.public_key_fingerprint,
        SignatureKeyStatus.ACTIVE,
        datetime(2026, 8, 1, 9, tzinfo=UTC),
    )

    assert trusted.valid_from.tzinfo is UTC


@pytest.mark.parametrize("status", [SignatureKeyStatus.ACTIVE, SignatureKeyStatus.VERIFY_ONLY])
def test_trusted_key_rejects_revoked_at_for_non_revoked(status: SignatureKeyStatus) -> None:
    key = private_key()
    with pytest.raises(InvalidArchiveSignatureTrustStoreError):
        trusted_key(key, status=status, revoked_at=SIGNED_AT)


def test_trusted_key_requires_revoked_at_for_revoked() -> None:
    key = private_key()
    with pytest.raises(InvalidArchiveSignatureTrustStoreError):
        trusted_key(key, status=SignatureKeyStatus.REVOKED)


def test_trust_store_rejects_duplicate_key_ids() -> None:
    key = private_key()
    with pytest.raises(DuplicateArchiveSigningKeyIdError):
        ArchiveSignatureTrustStore(keys=(trusted_key(key), trusted_key(key)))


def test_trust_store_get_key_unknown() -> None:
    with pytest.raises(UnknownArchiveSigningKeyError):
        ArchiveSignatureTrustStore(keys=()).get_key("missing")


def test_load_private_key_from_environment() -> None:
    secret = private_bytes()
    loaded = load_archive_signing_private_key(
        environ={
            ED25519_PRIVATE_KEY_ENV_NAME: b64(secret),
            ED25519_SIGNING_KEY_ID_ENV_NAME: "sig-key",
        }
    )

    assert loaded.key_id == "sig-key"
    assert loaded.private_key_bytes == secret
    assert loaded.public_key_bytes == public_bytes(secret)


def test_load_private_key_rejects_missing_environment() -> None:
    with pytest.raises(MissingArchiveSigningPrivateKeyError):
        load_archive_signing_private_key(environ={})


@pytest.mark.parametrize("value", ["not-base64", b64(b"x" * 31)])
def test_load_private_key_rejects_invalid_secret(value: str) -> None:
    with pytest.raises(InvalidArchiveSigningPrivateKeyError) as exc_info:
        load_archive_signing_private_key(
            environ={
                ED25519_PRIVATE_KEY_ENV_NAME: value,
                ED25519_SIGNING_KEY_ID_ENV_NAME: "sig-key",
            }
        )

    assert PRIVATE_SECRET_TEXT not in str(exc_info.value)


def test_load_trust_store_from_environment() -> None:
    key = private_key()
    trusted = trusted_key(key)
    loaded = load_archive_signature_trust_store(
        environ={ED25519_PUBLIC_TRUST_STORE_ENV_NAME: trust_store_payload(trusted)}
    )

    assert loaded.get_key(key.key_id).public_key_bytes == key.public_key_bytes


def test_load_trust_store_rejects_malformed_json_without_raw_value() -> None:
    with pytest.raises(InvalidArchiveSignatureTrustStoreError) as exc_info:
        load_archive_signature_trust_store(
            environ={ED25519_PUBLIC_TRUST_STORE_ENV_NAME: f"{{{PRIVATE_SECRET_TEXT}"}
        )

    assert PRIVATE_SECRET_TEXT not in str(exc_info.value)


def test_private_key_must_be_active_for_signing() -> None:
    key = private_key()
    store = ArchiveSignatureTrustStore(
        keys=(trusted_key(key, status=SignatureKeyStatus.VERIFY_ONLY),)
    )

    with pytest.raises(ArchiveSigningKeyNotActiveError):
        ensure_private_key_trusted_for_signing(
            signing_key=key,
            trust_store=store,
            signed_at=SIGNED_AT,
        )


def test_private_key_must_be_valid_at_signing_time() -> None:
    key = private_key()
    store = ArchiveSignatureTrustStore(keys=(trusted_key(key, valid_from=SIGNED_AT + timedelta(days=1)),))

    with pytest.raises(ArchiveSigningKeyNotValidError):
        ensure_private_key_trusted_for_signing(
            signing_key=key,
            trust_store=store,
            signed_at=SIGNED_AT,
        )


def test_private_key_fingerprint_must_match_trust_store() -> None:
    key = private_key()
    other = private_key(key.key_id)
    store = ArchiveSignatureTrustStore(keys=(trusted_key(other),))

    with pytest.raises(ArchiveSigningKeyFingerprintMismatchError):
        ensure_private_key_trusted_for_signing(
            signing_key=key,
            trust_store=store,
            signed_at=SIGNED_AT,
        )


def test_public_active_and_verify_only_keys_are_trusted_for_verification() -> None:
    key = private_key()
    for status in (SignatureKeyStatus.ACTIVE, SignatureKeyStatus.VERIFY_ONLY):
        ensure_public_key_trusted_for_verification(
            key=trusted_key(key, status=status),
            signed_at=SIGNED_AT,
            verification_time=VERIFY_TIME,
            revoked_key_policy=RevokedSignatureKeyPolicy.REJECT,
            maximum_clock_skew=timedelta(minutes=5),
        )


def test_revoked_key_rejected_by_default() -> None:
    key = private_key()
    with pytest.raises(RejectedArchiveSigningKeyError):
        ensure_public_key_trusted_for_verification(
            key=trusted_key(
                key,
                status=SignatureKeyStatus.REVOKED,
                revoked_at=SIGNED_AT + timedelta(days=1),
            ),
            signed_at=SIGNED_AT,
            verification_time=VERIFY_TIME,
            revoked_key_policy=RevokedSignatureKeyPolicy.REJECT,
            maximum_clock_skew=timedelta(minutes=5),
        )


def test_revoked_key_can_allow_pre_revocation_signature() -> None:
    key = private_key()
    ensure_public_key_trusted_for_verification(
        key=trusted_key(
            key,
            status=SignatureKeyStatus.REVOKED,
            revoked_at=SIGNED_AT + timedelta(days=1),
        ),
        signed_at=SIGNED_AT,
        verification_time=VERIFY_TIME,
        revoked_key_policy=RevokedSignatureKeyPolicy.ALLOW_PRE_REVOCATION,
        maximum_clock_skew=timedelta(minutes=5),
    )


def test_revoked_key_rejects_revocation_boundary() -> None:
    key = private_key()
    with pytest.raises(RejectedArchiveSigningKeyError):
        ensure_public_key_trusted_for_verification(
            key=trusted_key(key, status=SignatureKeyStatus.REVOKED, revoked_at=SIGNED_AT),
            signed_at=SIGNED_AT,
            verification_time=VERIFY_TIME,
            revoked_key_policy=RevokedSignatureKeyPolicy.ALLOW_PRE_REVOCATION,
            maximum_clock_skew=timedelta(minutes=5),
        )


def test_future_signature_beyond_skew_is_rejected() -> None:
    key = private_key()
    with pytest.raises(ArchiveSignatureFromFutureError):
        ensure_public_key_trusted_for_verification(
            key=trusted_key(key),
            signed_at=VERIFY_TIME + timedelta(minutes=6),
            verification_time=VERIFY_TIME,
            revoked_key_policy=RevokedSignatureKeyPolicy.REJECT,
            maximum_clock_skew=timedelta(minutes=5),
        )


def test_trust_store_is_frozen() -> None:
    store = ArchiveSignatureTrustStore(keys=())
    with pytest.raises(FrozenInstanceError):
        store.keys = ()
