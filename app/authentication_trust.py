"""Authentication trust store and policy for audit report HMAC."""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

from app.authentication_keyring import (
    HMAC_KEY_ENV_NAME,
    HMAC_KEY_ID_ENV_NAME,
    MINIMUM_HMAC_KEY_BYTES,
    is_valid_key_id,
)
from app.exceptions import (
    AuthenticationFromFutureError,
    AuthenticationKeyNotValidAtSigningTimeError,
    DuplicateAuthenticationKeyIdError,
    InvalidAuthenticationKeyError,
    InvalidAuthenticationKeyIdError,
    InvalidAuthenticationTrustStoreError,
    MultipleActiveAuthenticationKeysError,
    NoActiveAuthenticationKeyError,
    RejectedAuthenticationKeyError,
    UnknownAuthenticationKeyError,
)

AUTHENTICATION_TRUST_STORE_ENV_NAME = "AUDIT_REPORT_HMAC_TRUST_STORE_JSON"
SINGLE_KEY_VALID_FROM_ENV_NAME = "AUDIT_REPORT_HMAC_KEY_VALID_FROM"

_INVALID_TRUST_STORE_MESSAGE = "The audit report authentication trust store is invalid."
_INVALID_KEY_MESSAGE = "The audit report authentication key is invalid."
_INVALID_KEY_ID_MESSAGE = "The audit report authentication key ID is invalid."
_DUPLICATE_KEY_ID_MESSAGE = "Authentication key IDs must be unique."
_NO_ACTIVE_KEY_MESSAGE = "No active authentication key is valid for signing."
_MULTIPLE_ACTIVE_KEYS_MESSAGE = "Multiple active authentication keys are valid for signing."
_NOT_VALID_AT_SIGNING_MESSAGE = "The authentication key was not valid at signing time."
_REVOKED_KEY_MESSAGE = "The authentication key is revoked."
_FUTURE_AUTHENTICATION_MESSAGE = "The authentication time is too far in the future."


class AuthenticationKeyStatus(str, Enum):
    ACTIVE = "active"
    VERIFY_ONLY = "verify_only"
    REVOKED = "revoked"


class RevokedKeyPolicy(str, Enum):
    REJECT = "reject"
    ALLOW_PRE_REVOCATION = "allow_pre_revocation"


@dataclass(frozen=True)
class TrustedAuthenticationKey:
    key_id: str
    secret: bytes = field(repr=False)
    status: AuthenticationKeyStatus
    valid_from: datetime
    valid_until: datetime | None = None
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        if not is_valid_key_id(self.key_id):
            raise InvalidAuthenticationKeyIdError(_INVALID_KEY_ID_MESSAGE)
        if not isinstance(self.secret, bytes):
            raise InvalidAuthenticationKeyError(_INVALID_KEY_MESSAGE)
        if len(self.secret) < MINIMUM_HMAC_KEY_BYTES:
            raise InvalidAuthenticationKeyError(_INVALID_KEY_MESSAGE)
        if not isinstance(self.status, AuthenticationKeyStatus):
            raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)

        valid_from = _normalize_aware_datetime(self.valid_from)
        valid_until = _normalize_optional_aware_datetime(self.valid_until)
        revoked_at = _normalize_optional_aware_datetime(self.revoked_at)

        if valid_until is not None and valid_until <= valid_from:
            raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
        if revoked_at is not None and revoked_at < valid_from:
            raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
        if (
            self.status in {AuthenticationKeyStatus.ACTIVE, AuthenticationKeyStatus.VERIFY_ONLY}
            and revoked_at is not None
        ):
            raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
        if self.status is AuthenticationKeyStatus.REVOKED and revoked_at is None:
            raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)

        object.__setattr__(self, "valid_from", valid_from)
        object.__setattr__(self, "valid_until", valid_until)
        object.__setattr__(self, "revoked_at", revoked_at)


@dataclass(frozen=True)
class AuthenticationTrustStore:
    keys: tuple[TrustedAuthenticationKey, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.keys, tuple):
            raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
        seen: set[str] = set()
        for key in self.keys:
            if not isinstance(key, TrustedAuthenticationKey):
                raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
            if key.key_id in seen:
                raise DuplicateAuthenticationKeyIdError(_DUPLICATE_KEY_ID_MESSAGE)
            seen.add(key.key_id)

    def get_key(self, key_id: str) -> TrustedAuthenticationKey:
        if not is_valid_key_id(key_id):
            raise InvalidAuthenticationKeyIdError(_INVALID_KEY_ID_MESSAGE)
        for key in self.keys:
            if key.key_id == key_id:
                return key
        raise UnknownAuthenticationKeyError("The authentication key ID is not available.")


def parse_aware_datetime(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE) from error
    return _normalize_aware_datetime(parsed)


def load_authentication_trust_store(
    *,
    environ: Mapping[str, str],
) -> AuthenticationTrustStore:
    if not isinstance(environ, Mapping):
        raise TypeError("environ must be a Mapping")

    if AUTHENTICATION_TRUST_STORE_ENV_NAME in environ:
        return _parse_trust_store_json(environ[AUTHENTICATION_TRUST_STORE_ENV_NAME])

    required = (HMAC_KEY_ENV_NAME, HMAC_KEY_ID_ENV_NAME, SINGLE_KEY_VALID_FROM_ENV_NAME)
    if any(name not in environ or not environ[name] for name in required):
        raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)

    key_id = environ[HMAC_KEY_ID_ENV_NAME]
    if not is_valid_key_id(key_id):
        raise InvalidAuthenticationKeyIdError(_INVALID_KEY_ID_MESSAGE)

    key = TrustedAuthenticationKey(
        key_id=key_id,
        secret=_decode_secret_b64(environ[HMAC_KEY_ENV_NAME]),
        status=AuthenticationKeyStatus.ACTIVE,
        valid_from=parse_aware_datetime(environ[SINGLE_KEY_VALID_FROM_ENV_NAME]),
        valid_until=None,
        revoked_at=None,
    )
    return AuthenticationTrustStore(keys=(key,))


def select_signing_key(
    *,
    trust_store: AuthenticationTrustStore,
    authenticated_at: datetime,
) -> TrustedAuthenticationKey:
    authenticated_at = _normalize_aware_datetime(authenticated_at)
    candidates = [
        key
        for key in trust_store.keys
        if key.status is AuthenticationKeyStatus.ACTIVE
        and key.valid_from <= authenticated_at
        and (key.valid_until is None or authenticated_at < key.valid_until)
    ]
    if not candidates:
        raise NoActiveAuthenticationKeyError(_NO_ACTIVE_KEY_MESSAGE)
    if len(candidates) > 1:
        raise MultipleActiveAuthenticationKeysError(_MULTIPLE_ACTIVE_KEYS_MESSAGE)
    return candidates[0]


def ensure_key_trusted_for_verification(
    *,
    key: TrustedAuthenticationKey,
    authenticated_at: datetime,
    verification_time: datetime,
    revoked_key_policy: RevokedKeyPolicy,
    maximum_clock_skew: timedelta,
) -> None:
    authenticated_at = _normalize_aware_datetime(authenticated_at)
    verification_time = _normalize_aware_datetime(verification_time)
    if not isinstance(maximum_clock_skew, timedelta) or maximum_clock_skew < timedelta(0):
        raise ValueError("maximum_clock_skew must be non-negative")
    if not isinstance(revoked_key_policy, RevokedKeyPolicy):
        raise TypeError("revoked_key_policy must be a RevokedKeyPolicy")

    if authenticated_at > verification_time + maximum_clock_skew:
        raise AuthenticationFromFutureError(_FUTURE_AUTHENTICATION_MESSAGE)
    if authenticated_at < key.valid_from:
        raise AuthenticationKeyNotValidAtSigningTimeError(_NOT_VALID_AT_SIGNING_MESSAGE)
    if key.valid_until is not None and authenticated_at >= key.valid_until:
        raise AuthenticationKeyNotValidAtSigningTimeError(_NOT_VALID_AT_SIGNING_MESSAGE)

    if key.status in {AuthenticationKeyStatus.ACTIVE, AuthenticationKeyStatus.VERIFY_ONLY}:
        return

    if revoked_key_policy is RevokedKeyPolicy.REJECT:
        raise RejectedAuthenticationKeyError(_REVOKED_KEY_MESSAGE)
    if key.revoked_at is None or authenticated_at >= key.revoked_at:
        raise RejectedAuthenticationKeyError(_REVOKED_KEY_MESSAGE)


def _parse_trust_store_json(value: str) -> AuthenticationTrustStore:
    if not isinstance(value, str) or not value:
        raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE) from error
    if not isinstance(payload, dict):
        raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    if set(payload) != {"keys"}:
        raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    keys = payload["keys"]
    if not isinstance(keys, list):
        raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    return AuthenticationTrustStore(keys=tuple(_parse_key_item(item) for item in keys))


def _parse_key_item(value: object) -> TrustedAuthenticationKey:
    if not isinstance(value, dict):
        raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    required = {"key_id", "secret_b64", "status", "valid_from", "valid_until", "revoked_at"}
    if set(value) != required:
        raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    key_id = value["key_id"]
    if not is_valid_key_id(key_id):
        raise InvalidAuthenticationKeyIdError(_INVALID_KEY_ID_MESSAGE)
    try:
        status = AuthenticationKeyStatus(value["status"])
    except ValueError as error:
        raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE) from error
    return TrustedAuthenticationKey(
        key_id=key_id,
        secret=_decode_secret_b64(value["secret_b64"]),
        status=status,
        valid_from=parse_aware_datetime(value["valid_from"]),
        valid_until=parse_aware_datetime(value["valid_until"]) if value["valid_until"] is not None else None,
        revoked_at=parse_aware_datetime(value["revoked_at"]) if value["revoked_at"] is not None else None,
    )


def _decode_secret_b64(value: object) -> bytes:
    if not isinstance(value, str) or not value:
        raise InvalidAuthenticationKeyError(_INVALID_KEY_MESSAGE)
    try:
        encoded = value.encode("ascii")
        secret = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError, UnicodeEncodeError) as error:
        raise InvalidAuthenticationKeyError(_INVALID_KEY_MESSAGE) from error
    if len(secret) < MINIMUM_HMAC_KEY_BYTES:
        raise InvalidAuthenticationKeyError(_INVALID_KEY_MESSAGE)
    return secret


def _normalize_optional_aware_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return _normalize_aware_datetime(value)


def _normalize_aware_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidAuthenticationTrustStoreError(_INVALID_TRUST_STORE_MESSAGE)
    return value.astimezone(UTC)
