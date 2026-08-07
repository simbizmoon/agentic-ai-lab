"""Tests for bounded research search usage schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.research_search_budget import (
    ResearchSearchBudget,
    ResearchSearchUsage,
)


def test_search_budget_accepts_valid_limits() -> None:
    budget = ResearchSearchBudget(
        maximum_provider_calls=2,
        maximum_credits=2.0,
        maximum_latency_ms=10_000,
    )

    assert budget.maximum_provider_calls == 2
    assert budget.maximum_credits == 2.0
    assert budget.maximum_latency_ms == 10_000
    assert budget.default_credit_per_call == 1.0


def test_search_budget_rejects_zero_provider_calls() -> None:
    with pytest.raises(ValidationError):
        ResearchSearchBudget(
            maximum_provider_calls=0,
            maximum_credits=2.0,
            maximum_latency_ms=10_000,
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("maximum_credits", -0.1),
        ("maximum_latency_ms", -1),
        ("default_credit_per_call", -0.1),
    ],
)
def test_search_budget_rejects_negative_limits(
    field_name: str,
    value: float,
) -> None:
    values: dict[str, object] = {
        "maximum_provider_calls": 2,
        "maximum_credits": 2.0,
        "maximum_latency_ms": 10_000,
    }
    values[field_name] = value

    with pytest.raises(ValidationError):
        ResearchSearchBudget(**values)


def test_search_usage_defaults_to_zero() -> None:
    usage = ResearchSearchUsage()

    assert usage.provider_call_count == 0
    assert usage.credit_used == 0.0
    assert usage.latency_used_ms == 0
    assert usage.unreported_credit_call_count == 0
    assert usage.blocked_query_count == 0


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("provider_call_count", -1),
        ("credit_used", -0.1),
        ("latency_used_ms", -1),
        ("unreported_credit_call_count", -1),
        ("blocked_query_count", -1),
    ],
)
def test_search_usage_rejects_negative_values(
    field_name: str,
    value: float,
) -> None:
    with pytest.raises(ValidationError):
        ResearchSearchUsage(**{field_name: value})


def test_search_budget_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ResearchSearchBudget(
            maximum_provider_calls=2,
            maximum_credits=2.0,
            maximum_latency_ms=10_000,
            unknown_limit=1,
        )


def test_search_usage_forbids_mutation() -> None:
    usage = ResearchSearchUsage()

    with pytest.raises(ValidationError):
        usage.provider_call_count = 1
