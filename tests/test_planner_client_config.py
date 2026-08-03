"""Tests for structured planner client configuration."""

import pytest
from pydantic import ValidationError

from app.schemas.planner_client_config import (
    PlannerClientConfig,
)


def test_config_has_safe_defaults() -> None:
    config = PlannerClientConfig()

    assert config.model == "gpt-5-mini"
    assert config.max_output_tokens == 4_000
    assert config.reasoning_effort == "low"
    assert config.store is False


def test_config_rejects_blank_model() -> None:
    with pytest.raises(
        ValidationError,
        match="model must not be blank",
    ):
        PlannerClientConfig(model=" ")


def test_config_can_disable_reasoning_argument() -> None:
    config = PlannerClientConfig(
        reasoning_effort=None
    )

    assert config.reasoning_effort is None


def test_config_rejects_blank_reasoning_effort() -> None:
    with pytest.raises(
        ValidationError,
        match="reasoning_effort must not be blank",
    ):
        PlannerClientConfig(
            reasoning_effort=" "
        )


def test_config_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        PlannerClientConfig(
            unknown_value=True
        )
