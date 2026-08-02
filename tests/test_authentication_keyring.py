from __future__ import annotations

import base64
import json
from dataclasses import FrozenInstanceError

import pytest

from app.authentication_keyring import (
    HMAC_KEY_ENV_NAME,
    HMAC_KEY_ID_ENV_NAME,
    HMAC_KEYRING_ENV_NAME,
    AuthenticationKey,
    AuthenticationKeyring,
    _decode_secret_b64,
    _parse_key_item,
    _parse_keyring_json,
    is_valid_key_id,
    load_authentication_keyring,
)
from app.exceptions import (
    ActiveAuthenticationKeyNotFoundError,
    DuplicateAuthenticationKeyIdError,
    InvalidAuthenticationKeyError,
    InvalidAuthenticationKeyIdError,
    InvalidAuthenticationKeyringError,
    MissingAuthenticationKeyringError,
    UnknownAuthenticationKeyError,
)

SECRET = b"s" * 32
OLD_SECRET = b"o" * 32
NEW_SECRET = b"n" * 32
PRIVATE_SECRET = "PRIVATE-KEYRING-SECRET"


def encoded(secret: bytes = SECRET) -> str:
    return base64.b64encode(secret).decode("ascii")


def key(key_id: str = "key-1", secret: bytes = SECRET) -> AuthenticationKey:
    return AuthenticationKey(key_id=key_id, secret=secret)


def keyring_json(
    *,
    active_key_id: str = "new-key",
    keys: list[dict[str, object]] | None = None,
) -> str:
    return json.dumps(
        {
            "active_key_id": active_key_id,
            "keys": keys
            if keys is not None
            else [
                {"key_id": "old-key", "secret_b64": encoded(OLD_SECRET)},
                {"key_id": "new-key", "secret_b64": encoded(NEW_SECRET)},
            ],
        }
    )


def test_authentication_key_accepts_valid_key() -> None:
    assert key().key_id == "key-1"


def test_authentication_key_accepts_32_bytes() -> None:
    assert len(key(secret=b"x" * 32).secret) == 32


def test_authentication_key_rejects_31_bytes() -> None:
    with pytest.raises(InvalidAuthenticationKeyError):
        key(secret=b"x" * 31)


@pytest.mark.parametrize("secret", ["secret", bytearray(b"x" * 32)])
def test_authentication_key_rejects_non_bytes(secret: object) -> None:
    with pytest.raises(InvalidAuthenticationKeyError):
        AuthenticationKey(key_id="key-1", secret=secret)  # type: ignore[arg-type]


def test_authentication_key_rejects_bad_key_id() -> None:
    with pytest.raises(InvalidAuthenticationKeyIdError):
        key(key_id="bad key")


def test_authentication_key_repr_hides_secret() -> None:
    assert PRIVATE_SECRET not in repr(AuthenticationKey("key-1", (PRIVATE_SECRET + "x" * 32).encode()))


def test_authentication_key_is_frozen() -> None:
    item = key()

    with pytest.raises(FrozenInstanceError):
        item.key_id = "other"


def test_keyring_accepts_single_key() -> None:
    ring = AuthenticationKeyring(active_key_id="key-1", keys=(key(),))

    assert ring.get_active_key().key_id == "key-1"


def test_keyring_accepts_multiple_keys() -> None:
    ring = AuthenticationKeyring(active_key_id="new-key", keys=(key("old-key"), key("new-key")))

    assert len(ring.keys) == 2


def test_keyring_get_active_key() -> None:
    ring = AuthenticationKeyring(active_key_id="new-key", keys=(key("old-key"), key("new-key")))

    assert ring.get_active_key().key_id == "new-key"


def test_keyring_get_key_returns_old_key() -> None:
    ring = AuthenticationKeyring(active_key_id="new-key", keys=(key("old-key"), key("new-key")))

    assert ring.get_key("old-key").key_id == "old-key"


def test_keyring_rejects_empty_keys() -> None:
    with pytest.raises(InvalidAuthenticationKeyringError):
        AuthenticationKeyring(active_key_id="key-1", keys=())


def test_keyring_rejects_keys_list() -> None:
    with pytest.raises(InvalidAuthenticationKeyringError):
        AuthenticationKeyring(active_key_id="key-1", keys=[key()])  # type: ignore[arg-type]


def test_keyring_rejects_wrong_item_type() -> None:
    with pytest.raises(InvalidAuthenticationKeyringError):
        AuthenticationKeyring(active_key_id="key-1", keys=(object(),))  # type: ignore[arg-type]


def test_keyring_rejects_duplicate_key_id() -> None:
    with pytest.raises(DuplicateAuthenticationKeyIdError):
        AuthenticationKeyring(active_key_id="key-1", keys=(key(), key()))


def test_keyring_rejects_unregistered_active_key() -> None:
    with pytest.raises(ActiveAuthenticationKeyNotFoundError):
        AuthenticationKeyring(active_key_id="missing", keys=(key(),))


def test_keyring_get_key_rejects_unknown_key_id() -> None:
    ring = AuthenticationKeyring(active_key_id="key-1", keys=(key(),))

    with pytest.raises(UnknownAuthenticationKeyError):
        ring.get_key("missing")


def test_keyring_repr_hides_all_secrets() -> None:
    ring = AuthenticationKeyring(
        active_key_id="new-key",
        keys=(AuthenticationKey("old-key", b"o" * 32), AuthenticationKey("new-key", b"n" * 32)),
    )

    assert "oooooooo" not in repr(ring)
    assert "nnnnnnnn" not in repr(ring)


def test_keyring_is_frozen() -> None:
    ring = AuthenticationKeyring(active_key_id="key-1", keys=(key(),))

    with pytest.raises(FrozenInstanceError):
        ring.active_key_id = "other"


def test_keyring_keeps_original_tuple_unchanged() -> None:
    keys = (key(),)
    before = keys

    AuthenticationKeyring(active_key_id="key-1", keys=keys)

    assert keys == before


def test_decode_secret_accepts_valid_base64() -> None:
    assert _decode_secret_b64(encoded()) == SECRET


@pytest.mark.parametrize("value", ["", "not-base64!", "한글", encoded(b"x" * 31), 123])
def test_decode_secret_rejects_invalid_values(value: object) -> None:
    with pytest.raises(InvalidAuthenticationKeyError):
        _decode_secret_b64(value)


def test_parse_key_item_accepts_valid_item() -> None:
    item = _parse_key_item({"key_id": "key-1", "secret_b64": encoded()})

    assert item.key_id == "key-1"


@pytest.mark.parametrize(
    "item",
    [
        None,
        {"secret_b64": encoded()},
        {"key_id": "key-1"},
        {"key_id": "key-1", "secret_b64": encoded(), "extra": "x"},
    ],
)
def test_parse_key_item_rejects_invalid_structure(item: object) -> None:
    with pytest.raises(InvalidAuthenticationKeyringError):
        _parse_key_item(item)


def test_load_keyring_accepts_json() -> None:
    ring = load_authentication_keyring(environ={HMAC_KEYRING_ENV_NAME: keyring_json()})

    assert ring.active_key_id == "new-key"


def test_load_keyring_active_key_is_correct() -> None:
    ring = load_authentication_keyring(environ={HMAC_KEYRING_ENV_NAME: keyring_json()})

    assert ring.get_active_key().secret == NEW_SECRET


def test_load_keyring_can_lookup_past_key() -> None:
    ring = load_authentication_keyring(environ={HMAC_KEYRING_ENV_NAME: keyring_json()})

    assert ring.get_key("old-key").secret == OLD_SECRET


def test_load_keyring_rejects_missing_environment() -> None:
    with pytest.raises(MissingAuthenticationKeyringError):
        load_authentication_keyring(environ={})


@pytest.mark.parametrize(
    "value",
    [
        "",
        "{",
        "[]",
        json.dumps({"keys": []}),
        json.dumps({"active_key_id": "key-1", "keys": [], "extra": True}),
        json.dumps({"active_key_id": 123, "keys": []}),
        json.dumps({"active_key_id": "key-1", "keys": {}}),
        json.dumps({"active_key_id": "key-1", "keys": [None]}),
    ],
)
def test_parse_keyring_json_rejects_invalid_structure(value: str) -> None:
    with pytest.raises((InvalidAuthenticationKeyringError, InvalidAuthenticationKeyIdError)):
        _parse_keyring_json(value)


def test_load_keyring_rejects_bad_key_base64() -> None:
    with pytest.raises(InvalidAuthenticationKeyError):
        load_authentication_keyring(
            environ={
                HMAC_KEYRING_ENV_NAME: keyring_json(
                    active_key_id="key-1",
                    keys=[{"key_id": "key-1", "secret_b64": "not-base64!"}],
                )
            }
        )


def test_load_keyring_rejects_non_ascii_base64() -> None:
    with pytest.raises(InvalidAuthenticationKeyError):
        load_authentication_keyring(
            environ={
                HMAC_KEYRING_ENV_NAME: keyring_json(
                    active_key_id="key-1",
                    keys=[{"key_id": "key-1", "secret_b64": "한글"}],
                )
            }
        )


def test_load_keyring_rejects_short_secret() -> None:
    with pytest.raises(InvalidAuthenticationKeyError):
        load_authentication_keyring(
            environ={
                HMAC_KEYRING_ENV_NAME: keyring_json(
                    active_key_id="key-1",
                    keys=[{"key_id": "key-1", "secret_b64": encoded(b"x" * 31)}],
                )
            }
        )


def test_load_keyring_rejects_duplicate_key_id() -> None:
    with pytest.raises(DuplicateAuthenticationKeyIdError):
        load_authentication_keyring(
            environ={
                HMAC_KEYRING_ENV_NAME: keyring_json(
                    active_key_id="key-1",
                    keys=[
                        {"key_id": "key-1", "secret_b64": encoded(SECRET)},
                        {"key_id": "key-1", "secret_b64": encoded(OLD_SECRET)},
                    ],
                )
            }
        )


def test_load_keyring_rejects_missing_active_key() -> None:
    with pytest.raises(ActiveAuthenticationKeyNotFoundError):
        load_authentication_keyring(
            environ={
                HMAC_KEYRING_ENV_NAME: keyring_json(
                    active_key_id="missing",
                    keys=[{"key_id": "key-1", "secret_b64": encoded()}],
                )
            }
        )


def test_keyring_error_omits_json_and_secret() -> None:
    payload = json.dumps(
        {
            "active_key_id": "key-1",
            "keys": [{"key_id": "key-1", "secret_b64": PRIVATE_SECRET}],
        }
    )

    with pytest.raises(InvalidAuthenticationKeyError) as exc_info:
        load_authentication_keyring(environ={HMAC_KEYRING_ENV_NAME: payload})

    assert PRIVATE_SECRET not in str(exc_info.value)
    assert payload not in str(exc_info.value)


def test_load_keyring_does_not_mutate_environ() -> None:
    environ = {HMAC_KEYRING_ENV_NAME: keyring_json()}
    before = dict(environ)

    load_authentication_keyring(environ=environ)

    assert environ == before


def test_load_keyring_falls_back_to_single_key() -> None:
    ring = load_authentication_keyring(
        environ={HMAC_KEY_ENV_NAME: encoded(), HMAC_KEY_ID_ENV_NAME: "single-key"}
    )

    assert ring.active_key_id == "single-key"
    assert len(ring.keys) == 1


def test_single_key_fallback_key_is_active() -> None:
    ring = load_authentication_keyring(
        environ={HMAC_KEY_ENV_NAME: encoded(), HMAC_KEY_ID_ENV_NAME: "single-key"}
    )

    assert ring.get_active_key().key_id == "single-key"


@pytest.mark.parametrize(
    "environ",
    [
        {HMAC_KEY_ID_ENV_NAME: "single-key"},
        {HMAC_KEY_ENV_NAME: encoded()},
    ],
)
def test_single_key_fallback_requires_both_values(environ: dict[str, str]) -> None:
    with pytest.raises(MissingAuthenticationKeyringError):
        load_authentication_keyring(environ=environ)


def test_keyring_json_takes_precedence_over_single_key() -> None:
    ring = load_authentication_keyring(
        environ={
            HMAC_KEYRING_ENV_NAME: keyring_json(),
            HMAC_KEY_ENV_NAME: encoded(),
            HMAC_KEY_ID_ENV_NAME: "single-key",
        }
    )

    assert ring.active_key_id == "new-key"


def test_bad_keyring_json_does_not_fallback_to_single_key() -> None:
    with pytest.raises(InvalidAuthenticationKeyringError):
        load_authentication_keyring(
            environ={
                HMAC_KEYRING_ENV_NAME: "{",
                HMAC_KEY_ENV_NAME: encoded(),
                HMAC_KEY_ID_ENV_NAME: "single-key",
            }
        )


def test_is_valid_key_id_policy() -> None:
    assert is_valid_key_id("key.1_2-3") is True
    assert is_valid_key_id("bad key") is False
