"""Authentication keyring loading and validation for audit report HMAC."""

from __future__ import annotations

import base64
import binascii
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.exceptions import (
    ActiveAuthenticationKeyNotFoundError,
    DuplicateAuthenticationKeyIdError,
    InvalidAuthenticationKeyError,
    InvalidAuthenticationKeyIdError,
    InvalidAuthenticationKeyringError,
    MissingAuthenticationKeyringError,
    UnknownAuthenticationKeyError,
)

HMAC_KEYRING_ENV_NAME = "AUDIT_REPORT_HMAC_KEYRING_JSON"
HMAC_KEY_ENV_NAME = "AUDIT_REPORT_HMAC_KEY_B64"
HMAC_KEY_ID_ENV_NAME = "AUDIT_REPORT_HMAC_KEY_ID"
MINIMUM_HMAC_KEY_BYTES = 32

_KEY_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_MISSING_KEYRING_MESSAGE = "The audit report authentication keyring is missing."
_INVALID_KEYRING_MESSAGE = "The audit report authentication keyring is invalid."
_DUPLICATE_KEY_ID_MESSAGE = "Authentication key IDs must be unique."
_ACTIVE_KEY_NOT_FOUND_MESSAGE = "The active authentication key is not registered."
_INVALID_KEY_MESSAGE = "The audit report authentication key is invalid."
_INVALID_KEY_ID_MESSAGE = "The audit report authentication key ID is invalid."


def is_valid_key_id(value: object) -> bool:
    return isinstance(value, str) and _KEY_ID_PATTERN.fullmatch(value) is not None


@dataclass(frozen=True)
class AuthenticationKey:
    key_id: str
    secret: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not is_valid_key_id(self.key_id):
            raise InvalidAuthenticationKeyIdError(_INVALID_KEY_ID_MESSAGE)
        if not isinstance(self.secret, bytes):
            raise InvalidAuthenticationKeyError(_INVALID_KEY_MESSAGE)
        if len(self.secret) < MINIMUM_HMAC_KEY_BYTES:
            raise InvalidAuthenticationKeyError(_INVALID_KEY_MESSAGE)


@dataclass(frozen=True)
class AuthenticationKeyring:
    active_key_id: str
    keys: tuple[AuthenticationKey, ...]

    def __post_init__(self) -> None:
        if not is_valid_key_id(self.active_key_id):
            raise InvalidAuthenticationKeyIdError(_INVALID_KEY_ID_MESSAGE)
        if not isinstance(self.keys, tuple):
            raise InvalidAuthenticationKeyringError(_INVALID_KEYRING_MESSAGE)
        if not self.keys:
            raise InvalidAuthenticationKeyringError(_INVALID_KEYRING_MESSAGE)

        seen: set[str] = set()
        for key in self.keys:
            if not isinstance(key, AuthenticationKey):
                raise InvalidAuthenticationKeyringError(_INVALID_KEYRING_MESSAGE)
            if key.key_id in seen:
                raise DuplicateAuthenticationKeyIdError(_DUPLICATE_KEY_ID_MESSAGE)
            seen.add(key.key_id)

        if self.active_key_id not in seen:
            raise ActiveAuthenticationKeyNotFoundError(_ACTIVE_KEY_NOT_FOUND_MESSAGE)

    def get_active_key(self) -> AuthenticationKey:
        for key in self.keys:
            if key.key_id == self.active_key_id:
                return key
        raise ActiveAuthenticationKeyNotFoundError(_ACTIVE_KEY_NOT_FOUND_MESSAGE)

    def get_key(self, key_id: str) -> AuthenticationKey:
        if not is_valid_key_id(key_id):
            raise InvalidAuthenticationKeyIdError(_INVALID_KEY_ID_MESSAGE)
        for key in self.keys:
            if key.key_id == key_id:
                return key
        raise UnknownAuthenticationKeyError("The authentication key ID is not available.")


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


def _parse_key_item(value: object) -> AuthenticationKey:
    if not isinstance(value, dict):
        raise InvalidAuthenticationKeyringError(_INVALID_KEYRING_MESSAGE)
    if set(value) != {"key_id", "secret_b64"}:
        raise InvalidAuthenticationKeyringError(_INVALID_KEYRING_MESSAGE)
    key_id = value["key_id"]
    if not is_valid_key_id(key_id):
        raise InvalidAuthenticationKeyIdError(_INVALID_KEY_ID_MESSAGE)
    return AuthenticationKey(
        key_id=key_id,
        secret=_decode_secret_b64(value["secret_b64"]),
    )


def _parse_keyring_json(value: str) -> AuthenticationKeyring:
    if not isinstance(value, str) or not value:
        raise InvalidAuthenticationKeyringError(_INVALID_KEYRING_MESSAGE)
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise InvalidAuthenticationKeyringError(_INVALID_KEYRING_MESSAGE) from error

    if not isinstance(payload, dict):
        raise InvalidAuthenticationKeyringError(_INVALID_KEYRING_MESSAGE)
    if set(payload) != {"active_key_id", "keys"}:
        raise InvalidAuthenticationKeyringError(_INVALID_KEYRING_MESSAGE)

    active_key_id = payload["active_key_id"]
    if not is_valid_key_id(active_key_id):
        raise InvalidAuthenticationKeyIdError(_INVALID_KEY_ID_MESSAGE)
    keys_payload = payload["keys"]
    if not isinstance(keys_payload, list):
        raise InvalidAuthenticationKeyringError(_INVALID_KEYRING_MESSAGE)

    keys = tuple(_parse_key_item(item) for item in keys_payload)
    return AuthenticationKeyring(active_key_id=active_key_id, keys=keys)


def load_authentication_keyring(
    *,
    environ: Mapping[str, str],
) -> AuthenticationKeyring:
    if not isinstance(environ, Mapping):
        raise TypeError("environ must be a Mapping")

    if HMAC_KEYRING_ENV_NAME in environ:
        return _parse_keyring_json(environ[HMAC_KEYRING_ENV_NAME])

    if HMAC_KEY_ENV_NAME not in environ or HMAC_KEY_ID_ENV_NAME not in environ:
        raise MissingAuthenticationKeyringError(_MISSING_KEYRING_MESSAGE)

    encoded_key = environ[HMAC_KEY_ENV_NAME]
    key_id = environ[HMAC_KEY_ID_ENV_NAME]
    if not encoded_key or not key_id:
        raise MissingAuthenticationKeyringError(_MISSING_KEYRING_MESSAGE)
    if not is_valid_key_id(key_id):
        raise InvalidAuthenticationKeyIdError(_INVALID_KEY_ID_MESSAGE)

    key = AuthenticationKey(
        key_id=key_id,
        secret=_decode_secret_b64(encoded_key),
    )
    return AuthenticationKeyring(active_key_id=key.key_id, keys=(key,))
