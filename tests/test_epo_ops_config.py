"""Tests for EPO OPS transport configuration and token contracts."""

import pytest
from pydantic import SecretStr, ValidationError

from app.schemas.epo_ops_config import EpoOpsAccessToken, EpoOpsConfig


def config(**overrides: object) -> EpoOpsConfig:
    values: dict[str, object] = {
        "consumer_key": SecretStr("consumer-key"),
        "consumer_secret": SecretStr("consumer-secret"),
    }
    values.update(overrides)
    return EpoOpsConfig.model_validate(values)


def test_config_defaults_are_bounded_and_private() -> None:
    value = config()

    assert value.timeout_seconds == 15.0
    assert value.maximum_response_bytes == 1_000_000
    rendered = repr(value) + str(value.model_dump())
    assert "consumer-key" not in rendered
    assert "consumer-secret" not in rendered


@pytest.mark.parametrize("field", ["consumer_key", "consumer_secret"])
def test_config_rejects_blank_credentials(field: str) -> None:
    with pytest.raises(ValidationError, match="must not be blank"):
        config(**{field: SecretStr("  ")})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("timeout_seconds", 0.0),
        ("timeout_seconds", 121.0),
        ("maximum_response_bytes", 1_023),
        ("maximum_response_bytes", 10_000_001),
    ],
)
def test_config_rejects_out_of_bounds(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        config(**{field: value})


def test_config_is_strict_and_frozen() -> None:
    value = config()

    with pytest.raises(ValidationError):
        config(timeout_seconds="15")
    with pytest.raises(ValidationError):
        value.timeout_seconds = 20


def test_token_accepts_documented_numeric_string_and_is_secret_safe() -> None:
    value = EpoOpsAccessToken.model_validate(
        {
            "access_token": SecretStr("bearer-secret"),
            "token_type": "Bearer",
            "expires_in": "1199",
            "documented_extra": "ignored",
        }
    )

    assert value.expires_in == 1199
    assert "bearer-secret" not in repr(value)
    assert "bearer-secret" not in str(value.model_dump())


def test_token_is_strict_frozen_and_validated() -> None:
    with pytest.raises(ValidationError):
        EpoOpsAccessToken(
            access_token=SecretStr("token"), token_type="mac", expires_in=60
        )
    value = EpoOpsAccessToken(
        access_token=SecretStr("token"), token_type="Bearer", expires_in=60
    )
    with pytest.raises(ValidationError):
        value.expires_in = 120
