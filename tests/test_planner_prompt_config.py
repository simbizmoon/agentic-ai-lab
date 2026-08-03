"""Tests for planner prompt configuration."""

import pytest
from pydantic import ValidationError

from app.schemas.planner_prompt_config import (
    PlannerPromptConfig,
)


def test_config_has_safe_defaults() -> None:
    config = PlannerPromptConfig()

    assert config.include_metadata is False
    assert config.include_previous_outputs is True
    assert config.maximum_output_characters == 2_000


def test_config_rejects_tiny_output_limit() -> None:
    with pytest.raises(ValidationError):
        PlannerPromptConfig(
            maximum_output_characters=99
        )


def test_config_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        PlannerPromptConfig(
            unknown_value=True
        )
