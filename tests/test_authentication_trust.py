from __future__ import annotations

import base64
import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.authentication_keyring import HMAC_KEY_ENV_NAME, HMAC_KEY_ID_ENV_NAME
from app.authentication_trust import (
    AUTHENTICATION_TRUST_STORE_ENV_NAME,
    SINGLE_KEY_VALID_FROM_ENV_NAME,
    AuthenticationKeyStatus,
    AuthenticationTrustStore,
    RevokedKeyPolicy,
    TrustedAuthenticationKey,
    ensure_key_trusted_for_verification,
    load_authentication_trust_store,
    parse_aware_datetime,
    select_signing_key,
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

SECRET = b"s" * 32
OLD_SECRET = b"o" * 32
NEW_SECRET = b"n" * 32
PRIVATE_SECRET = "PRIVATE-TRUST-SECRET"
BASE_TIME = datetime(2026, 8, 2, 0, 0, tzinfo=UTC)
PAST_TIME = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)
FUTURE_TIME = datetime(2026, 8, 3, 0, 0, tzinfo=UTC)
REVOKED_TIME = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


def encoded(secret: bytes = SECRET) -> str:
    return base64.b64encode(secret).decode("ascii")


def trusted_key(
    *,
    key_id: str = "key-1",
    secret: bytes = SECRET,
    status: AuthenticationKeyStatus = AuthenticationKeyStatus.ACTIVE,
    valid_from: datetime = PAST_TIME,
    valid_until: datetime | None = None,
    revoked_at: datetime | None = None,
) -> TrustedAuthenticationKey:
    return TrustedAuthenticationKey(
        key_id=key_id,
        secret=secret,
        status=status,
        valid_from=valid_from,
        valid_until=valid_until,
        revoked_at=revoked_at,
    )


def trust_store_json(keys: list[dict[str, object]] | None = None) -> str:
    return json.dumps(
        {
            "keys": keys
            if keys is not None
            else [
                {
                    "key_id": "old-key",
                    "secret_b64": encoded(OLD_SECRET),
                    "status": "verify_only",
                    "valid_from": PAST_TIME.isoformat(),
                    "valid_until": None,
                    "revoked_at": None,
                },
                {
                    "key_id": "new-key",
                    "secret_b64": encoded(NEW_SECRET),
                    "status": "active",
                    "valid_from": PAST_TIME.isoformat(),
                    "valid_until": None,
                    "revoked_at": None,
                },
                {
                    "key_id": "revoked-key",
                    "secret_b64": encoded(b"r" * 32),
                    "status": "revoked",
                    "valid_from": PAST_TIME.isoformat(),
                    "valid_until": None,
                    "revoked_at": REVOKED_TIME.isoformat(),
                },
            ]
        }
    )


def test_key_status_values() -> None:
    assert AuthenticationKeyStatus.ACTIVE.value == "active"
    assert AuthenticationKeyStatus.VERIFY_ONLY.value == "verify_only"
    assert AuthenticationKeyStatus.REVOKED.value == "revoked"


def test_revoked_policy_values() -> None:
    assert RevokedKeyPolicy.REJECT.value == "reject"
    assert RevokedKeyPolicy.ALLOW_PRE_REVOCATION.value == "allow_pre_revocation"


@pytest.mark.parametrize("status", list(AuthenticationKeyStatus))
def test_trusted_key_accepts_statuses(status: AuthenticationKeyStatus) -> None:
    revoked_at = REVOKED_TIME if status is AuthenticationKeyStatus.REVOKED else None

    assert trusted_key(status=status, revoked_at=revoked_at).status is status


def test_trusted_key_repr_hides_secret() -> None:
    key = trusted_key(secret=(PRIVATE_SECRET + "x" * 32).encode())

    assert PRIVATE_SECRET not in repr(key)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"key_id": "bad key"},
        {"secret": "secret"},
        {"secret": b"s" * 31},
        {"valid_from": datetime.fromisoformat("2026-08-02T00:00:00")},
        {"valid_until": datetime.fromisoformat("2026-08-03T00:00:00")},
        {"revoked_at": datetime.fromisoformat("2026-08-02T00:00:00")},
        {"valid_until": PAST_TIME},
        {"revoked_at": datetime(2026, 7, 31, tzinfo=UTC), "status": AuthenticationKeyStatus.REVOKED},
        {"revoked_at": BASE_TIME},
        {"status": AuthenticationKeyStatus.VERIFY_ONLY, "revoked_at": BASE_TIME},
        {"status": AuthenticationKeyStatus.REVOKED},
    ],
)
def test_trusted_key_rejects_invalid_values(kwargs: dict[str, object]) -> None:
    with pytest.raises(
        (
            InvalidAuthenticationKeyError,
            InvalidAuthenticationKeyIdError,
            InvalidAuthenticationTrustStoreError,
        )
    ):
        trusted_key(**kwargs)  # type: ignore[arg-type]


def test_trusted_key_normalizes_to_utc() -> None:
    key = trusted_key(valid_from=datetime(2026, 8, 2, 9, 0, tzinfo=timezone(timedelta(hours=9))))

    assert key.valid_from == BASE_TIME


def test_trusted_key_is_frozen() -> None:
    key = trusted_key()

    with pytest.raises(FrozenInstanceError):
        key.key_id = "other"


def test_trust_store_accepts_empty_store() -> None:
    assert AuthenticationTrustStore(keys=()).keys == ()


def test_trust_store_rejects_duplicate_key_id() -> None:
    with pytest.raises(DuplicateAuthenticationKeyIdError):
        AuthenticationTrustStore(keys=(trusted_key(), trusted_key()))


def test_trust_store_get_key_success() -> None:
    store = AuthenticationTrustStore(keys=(trusted_key(),))

    assert store.get_key("key-1").key_id == "key-1"


def test_trust_store_get_key_unknown() -> None:
    store = AuthenticationTrustStore(keys=(trusted_key(),))

    with pytest.raises(UnknownAuthenticationKeyError):
        store.get_key("missing")


def test_parse_aware_datetime_accepts_and_normalizes() -> None:
    assert parse_aware_datetime("2026-08-02T09:00:00+09:00") == BASE_TIME


@pytest.mark.parametrize("value", ["", "not-a-date", "2026-08-02T00:00:00", 123])
def test_parse_aware_datetime_rejects_invalid_values(value: object) -> None:
    with pytest.raises(InvalidAuthenticationTrustStoreError):
        parse_aware_datetime(value)


def test_load_trust_store_accepts_json() -> None:
    store = load_authentication_trust_store(environ={AUTHENTICATION_TRUST_STORE_ENV_NAME: trust_store_json()})

    assert len(store.keys) == 3
    assert store.get_key("new-key").status is AuthenticationKeyStatus.ACTIVE
    assert store.get_key("old-key").status is AuthenticationKeyStatus.VERIFY_ONLY
    assert store.get_key("revoked-key").status is AuthenticationKeyStatus.REVOKED


@pytest.mark.parametrize(
    "value",
    [
        "",
        "{",
        "[]",
        json.dumps({}),
        json.dumps({"keys": [], "extra": True}),
        json.dumps({"keys": {}}),
        json.dumps({"keys": [None]}),
        json.dumps({"keys": [{"key_id": "key-1"}]}),
        json.dumps({
            "keys": [{
                "key_id": "key-1",
                "secret_b64": encoded(),
                "status": "active",
                "valid_from": PAST_TIME.isoformat(),
                "valid_until": None,
                "revoked_at": None,
                "extra": True,
            }]
        }),
        json.dumps({"keys": [{"key_id": "key-1", "secret_b64": "not-base64!", "status": "active", "valid_from": PAST_TIME.isoformat(), "valid_until": None, "revoked_at": None}]}),
        json.dumps({"keys": [{"key_id": "key-1", "secret_b64": encoded(), "status": "unknown", "valid_from": PAST_TIME.isoformat(), "valid_until": None, "revoked_at": None}]}),
        json.dumps({"keys": [{"key_id": "key-1", "secret_b64": encoded(), "status": "active", "valid_from": "not-a-date", "valid_until": None, "revoked_at": None}]}),
    ],
)
def test_load_trust_store_rejects_invalid_json(value: str) -> None:
    with pytest.raises((InvalidAuthenticationTrustStoreError, InvalidAuthenticationKeyError)):
        load_authentication_trust_store(environ={AUTHENTICATION_TRUST_STORE_ENV_NAME: value})


def test_trust_store_errors_omit_json_and_secret() -> None:
    payload = json.dumps({"keys": [{"key_id": "key-1", "secret_b64": PRIVATE_SECRET}]})

    with pytest.raises(InvalidAuthenticationTrustStoreError) as exc_info:
        load_authentication_trust_store(environ={AUTHENTICATION_TRUST_STORE_ENV_NAME: payload})

    assert PRIVATE_SECRET not in str(exc_info.value)
    assert payload not in str(exc_info.value)


def test_single_key_compatibility_loader() -> None:
    store = load_authentication_trust_store(
        environ={
            HMAC_KEY_ENV_NAME: encoded(),
            HMAC_KEY_ID_ENV_NAME: "key-1",
            SINGLE_KEY_VALID_FROM_ENV_NAME: PAST_TIME.isoformat(),
        }
    )

    assert store.get_key("key-1").status is AuthenticationKeyStatus.ACTIVE


def test_single_key_compatibility_requires_valid_from() -> None:
    with pytest.raises(InvalidAuthenticationTrustStoreError):
        load_authentication_trust_store(
            environ={HMAC_KEY_ENV_NAME: encoded(), HMAC_KEY_ID_ENV_NAME: "key-1"}
        )


def test_loader_does_not_mutate_environ() -> None:
    environ = {AUTHENTICATION_TRUST_STORE_ENV_NAME: trust_store_json()}
    before = dict(environ)

    load_authentication_trust_store(environ=environ)

    assert environ == before


def test_select_signing_key_returns_one_active_key() -> None:
    store = AuthenticationTrustStore(keys=(trusted_key(), trusted_key(key_id="old", status=AuthenticationKeyStatus.VERIFY_ONLY)))

    assert select_signing_key(trust_store=store, authenticated_at=BASE_TIME).key_id == "key-1"


def test_select_signing_key_excludes_verify_only_and_revoked() -> None:
    store = AuthenticationTrustStore(keys=(
        trusted_key(key_id="verify", status=AuthenticationKeyStatus.VERIFY_ONLY),
        trusted_key(key_id="revoked", status=AuthenticationKeyStatus.REVOKED, revoked_at=REVOKED_TIME),
    ))

    with pytest.raises(NoActiveAuthenticationKeyError):
        select_signing_key(trust_store=store, authenticated_at=BASE_TIME)


def test_select_signing_key_validity_boundaries() -> None:
    store = AuthenticationTrustStore(keys=(trusted_key(valid_from=BASE_TIME, valid_until=FUTURE_TIME),))

    assert select_signing_key(trust_store=store, authenticated_at=BASE_TIME).key_id == "key-1"
    with pytest.raises(NoActiveAuthenticationKeyError):
        select_signing_key(trust_store=store, authenticated_at=FUTURE_TIME)


def test_select_signing_key_multiple_active_keys() -> None:
    store = AuthenticationTrustStore(keys=(trusted_key(key_id="one"), trusted_key(key_id="two")))

    with pytest.raises(MultipleActiveAuthenticationKeysError):
        select_signing_key(trust_store=store, authenticated_at=BASE_TIME)


def test_select_signing_key_rejects_naive_time() -> None:
    with pytest.raises(InvalidAuthenticationTrustStoreError):
        select_signing_key(trust_store=AuthenticationTrustStore(keys=(trusted_key(),)), authenticated_at=datetime.fromisoformat("2026-08-02T00:00:00"))


def test_verification_trust_allows_active_and_verify_only() -> None:
    for status in (AuthenticationKeyStatus.ACTIVE, AuthenticationKeyStatus.VERIFY_ONLY):
        ensure_key_trusted_for_verification(
            key=trusted_key(status=status),
            authenticated_at=BASE_TIME,
            verification_time=BASE_TIME,
            revoked_key_policy=RevokedKeyPolicy.REJECT,
            maximum_clock_skew=timedelta(minutes=5),
        )


def test_verification_trust_rejects_revoked_by_default() -> None:
    with pytest.raises(RejectedAuthenticationKeyError):
        ensure_key_trusted_for_verification(
            key=trusted_key(status=AuthenticationKeyStatus.REVOKED, revoked_at=REVOKED_TIME),
            authenticated_at=BASE_TIME,
            verification_time=BASE_TIME,
            revoked_key_policy=RevokedKeyPolicy.REJECT,
            maximum_clock_skew=timedelta(minutes=5),
        )


def test_verification_trust_allows_pre_revocation_policy_before_revocation() -> None:
    ensure_key_trusted_for_verification(
        key=trusted_key(status=AuthenticationKeyStatus.REVOKED, revoked_at=REVOKED_TIME),
        authenticated_at=BASE_TIME,
        verification_time=BASE_TIME,
        revoked_key_policy=RevokedKeyPolicy.ALLOW_PRE_REVOCATION,
        maximum_clock_skew=timedelta(minutes=5),
    )


@pytest.mark.parametrize("authenticated_at", [REVOKED_TIME, REVOKED_TIME + timedelta(seconds=1)])
def test_verification_trust_rejects_revoked_at_boundary(authenticated_at: datetime) -> None:
    with pytest.raises(RejectedAuthenticationKeyError):
        ensure_key_trusted_for_verification(
            key=trusted_key(status=AuthenticationKeyStatus.REVOKED, revoked_at=REVOKED_TIME),
            authenticated_at=authenticated_at,
            verification_time=authenticated_at,
            revoked_key_policy=RevokedKeyPolicy.ALLOW_PRE_REVOCATION,
            maximum_clock_skew=timedelta(minutes=5),
        )


@pytest.mark.parametrize("authenticated_at", [PAST_TIME - timedelta(seconds=1), FUTURE_TIME])
def test_verification_trust_rejects_outside_validity(authenticated_at: datetime) -> None:
    with pytest.raises(AuthenticationKeyNotValidAtSigningTimeError):
        ensure_key_trusted_for_verification(
            key=trusted_key(valid_from=PAST_TIME, valid_until=FUTURE_TIME),
            authenticated_at=authenticated_at,
            verification_time=authenticated_at,
            revoked_key_policy=RevokedKeyPolicy.REJECT,
            maximum_clock_skew=timedelta(minutes=5),
        )


def test_verification_trust_future_skew_boundary() -> None:
    ensure_key_trusted_for_verification(
        key=trusted_key(),
        authenticated_at=BASE_TIME + timedelta(minutes=5),
        verification_time=BASE_TIME,
        revoked_key_policy=RevokedKeyPolicy.REJECT,
        maximum_clock_skew=timedelta(minutes=5),
    )

    with pytest.raises(AuthenticationFromFutureError):
        ensure_key_trusted_for_verification(
            key=trusted_key(),
            authenticated_at=BASE_TIME + timedelta(minutes=5, seconds=1),
            verification_time=BASE_TIME,
            revoked_key_policy=RevokedKeyPolicy.REJECT,
            maximum_clock_skew=timedelta(minutes=5),
        )


def test_verification_trust_rejects_negative_clock_skew() -> None:
    with pytest.raises(ValueError):
        ensure_key_trusted_for_verification(
            key=trusted_key(),
            authenticated_at=BASE_TIME,
            verification_time=BASE_TIME,
            revoked_key_policy=RevokedKeyPolicy.REJECT,
            maximum_clock_skew=timedelta(seconds=-1),
        )
