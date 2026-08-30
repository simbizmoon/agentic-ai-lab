"""Offline tests for component-specific Stage 9 runtime locking."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.provider_cost import ModelPriceEntry, PriceRate, UsageUnit
from app.schemas.stage9_baseline_runtime_stack import (
    Stage9BaselineRuntimeStack,
    Stage9RuntimeComponentLock,
    Stage9RuntimeComponentRole,
)

PRICING_DATE = date(2026, 8, 30)


def _price(role: Stage9RuntimeComponentRole, **updates: object) -> ModelPriceEntry:
    values: dict[str, object] = {
        "price_entry_id": f"offline-{role.value}-price",
        "registry_version": "offline-stage9-runtime-test-v1",
        "provider_name": "Offline Test Provider",
        "model_name": f"offline-{role.value}-model",
        "operation": role.value,
        "effective_from": PRICING_DATE,
        "effective_through": PRICING_DATE,
        "source_reference": "offline fixture; not current provider pricing",
        "rates": (
            PriceRate(
                usage_unit=UsageUnit.TOTAL_TOKEN,
                unit_size=Decimal(1_000_000),
                rate_amount=Decimal("1.00"),
                currency="USD",
            ),
        ),
    }
    values.update(updates)
    return ModelPriceEntry.model_validate(values)


def _component(
    role: Stage9RuntimeComponentRole, **updates: object
) -> Stage9RuntimeComponentLock:
    values: dict[str, object] = {
        "role": role,
        "provider_name": "Offline Test Provider",
        "model_name": f"offline-{role.value}-model",
        "operation": role.value,
        "reasoning_effort": "low",
        "pricing_date": PRICING_DATE,
        "price_entry": _price(role),
    }
    values.update(updates)
    return Stage9RuntimeComponentLock.model_validate(values)


def _stack(**updates: object) -> Stage9BaselineRuntimeStack:
    values: dict[str, object] = {
        "stack_id": "stage9-offline-runtime-stack-v1",
        "stack_version": "1.0.0",
        "components": tuple(_component(role) for role in Stage9RuntimeComponentRole),
    }
    values.update(updates)
    return Stage9BaselineRuntimeStack.model_validate(values)


def test_accepts_exact_three_component_runtime_stack() -> None:
    stack = _stack()
    assert {item.role for item in stack.components} == set(Stage9RuntimeComponentRole)
    assert (
        stack.component(Stage9RuntimeComponentRole.PLANNER).model_name
        == "offline-planner-model"
    )


def test_rejects_component_price_model_mismatch() -> None:
    with pytest.raises(ValidationError, match="identity must match"):
        _component(
            Stage9RuntimeComponentRole.PLANNER,
            price_entry=_price(
                Stage9RuntimeComponentRole.PLANNER, model_name="different-model"
            ),
        )


def test_rejects_price_outside_locked_date() -> None:
    with pytest.raises(ValidationError, match="not effective"):
        _component(
            Stage9RuntimeComponentRole.PLANNER,
            pricing_date=date(2026, 8, 31),
        )


def test_rejects_missing_component_role() -> None:
    components = tuple(
        _component(role)
        for role in (
            Stage9RuntimeComponentRole.PLANNER,
            Stage9RuntimeComponentRole.GROUNDED_ANSWER_GENERATOR,
        )
    )
    with pytest.raises(ValidationError):
        _stack(components=components)


def test_rejects_duplicate_component_role() -> None:
    components = (
        _component(Stage9RuntimeComponentRole.PLANNER),
        _component(Stage9RuntimeComponentRole.PLANNER),
        _component(Stage9RuntimeComponentRole.CITATION_EVALUATOR),
    )
    with pytest.raises(ValidationError, match="each required role"):
        _stack(components=components)


def test_rejects_mixed_registry_versions() -> None:
    components = list(_stack().components)
    role = Stage9RuntimeComponentRole.CITATION_EVALUATOR
    components[-1] = _component(
        role,
        price_entry=_price(role, registry_version="different-registry"),
    )
    with pytest.raises(ValidationError, match="one price registry"):
        _stack(components=tuple(components))


def test_rejects_mixed_pricing_dates() -> None:
    components = list(_stack().components)
    role = Stage9RuntimeComponentRole.CITATION_EVALUATOR
    other_date = date(2026, 8, 29)
    components[-1] = _component(
        role,
        pricing_date=other_date,
        price_entry=_price(
            role, effective_from=other_date, effective_through=other_date
        ),
    )
    with pytest.raises(ValidationError, match="one locked pricing date"):
        _stack(components=tuple(components))
