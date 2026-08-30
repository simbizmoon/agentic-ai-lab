"""Offline tests for Stage 9 runtime-to-adapter preflight binding."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.research.stage9_baseline_runtime_preflight import (
    CITATION_EVALUATOR_OPERATION,
    GENERATOR_OPERATION,
    PLANNER_OPERATION,
    Stage9BaselineRuntimePreflight,
)
from app.schemas.provider_cost import ModelPriceEntry, PriceRate, UsageUnit
from app.schemas.stage9_baseline_runtime_stack import (
    Stage9BaselineRuntimeStack,
    Stage9RuntimeComponentLock,
    Stage9RuntimeComponentRole,
)

PRICING_DATE = date(2026, 8, 30)


class Responses:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, Any]] = []
        self.parse_calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> object:
        self.create_calls.append(kwargs)
        return SimpleNamespace()

    def parse(self, **kwargs: Any) -> object:
        self.parse_calls.append(kwargs)
        return SimpleNamespace()


class Client:
    def __init__(self) -> None:
        self.responses = Responses()


def _component(
    role: Stage9RuntimeComponentRole,
    *,
    operation: str,
    model: str,
    reasoning_effort: str | None,
    provider: str = "OpenAI",
) -> Stage9RuntimeComponentLock:
    price = ModelPriceEntry(
        price_entry_id=f"{role.value}-price",
        registry_version="stage9-preflight-test-registry-v1",
        provider_name=provider,
        model_name=model,
        operation=operation,
        effective_from=PRICING_DATE,
        effective_through=PRICING_DATE,
        source_reference="offline fixture; not current provider pricing",
        rates=(
            PriceRate(
                usage_unit=UsageUnit.TOTAL_TOKEN,
                unit_size=Decimal(1_000_000),
                rate_amount=Decimal("1.00"),
                currency="USD",
            ),
        ),
    )
    return Stage9RuntimeComponentLock(
        role=role,
        provider_name=provider,
        model_name=model,
        operation=operation,
        reasoning_effort=reasoning_effort,
        pricing_date=PRICING_DATE,
        price_entry=price,
    )


def _stack(**replacements: Stage9RuntimeComponentLock) -> Stage9BaselineRuntimeStack:
    values = {
        "planner": _component(
            Stage9RuntimeComponentRole.PLANNER,
            operation=PLANNER_OPERATION,
            model="planner-model",
            reasoning_effort="low",
        ),
        "generator": _component(
            Stage9RuntimeComponentRole.GROUNDED_ANSWER_GENERATOR,
            operation=GENERATOR_OPERATION,
            model="generator-model",
            reasoning_effort=None,
        ),
        "evaluator": _component(
            Stage9RuntimeComponentRole.CITATION_EVALUATOR,
            operation=CITATION_EVALUATOR_OPERATION,
            model="evaluator-model",
            reasoning_effort=None,
        ),
    }
    values.update(replacements)
    return Stage9BaselineRuntimeStack(
        stack_id="stage9-preflight-test-stack-v1",
        stack_version="1.0.0",
        components=tuple(values.values()),
    )


def test_prepares_exact_models_without_provider_calls() -> None:
    generation = Client()
    citation = Client()
    prepared = Stage9BaselineRuntimePreflight().prepare(
        runtime_stack=_stack(),
        generation_client=generation,
        citation_client=citation,
    )
    assert prepared.planner_config.model == "planner-model"
    assert prepared.planner_config.reasoning_effort == "low"
    assert prepared.planner_config.store is False
    assert prepared.generator_model == "generator-model"
    assert prepared.citation_evaluator_model == "evaluator-model"
    assert prepared.grounded_answer_orchestrator is not None
    assert generation.responses.create_calls == []
    assert citation.responses.parse_calls == []


def test_rejects_non_openai_provider_before_calls() -> None:
    generation = Client()
    citation = Client()
    planner = _component(
        Stage9RuntimeComponentRole.PLANNER,
        operation=PLANNER_OPERATION,
        model="planner-model",
        reasoning_effort="low",
        provider="Different Provider",
    )
    with pytest.raises(ValueError, match="require the OpenAI provider"):
        Stage9BaselineRuntimePreflight().prepare(
            runtime_stack=_stack(planner=planner),
            generation_client=generation,
            citation_client=citation,
        )
    assert generation.responses.create_calls == []
    assert citation.responses.parse_calls == []


def test_rejects_wrong_operation_before_calls() -> None:
    generation = Client()
    citation = Client()
    evaluator = _component(
        Stage9RuntimeComponentRole.CITATION_EVALUATOR,
        operation="responses.create",
        model="evaluator-model",
        reasoning_effort=None,
    )
    with pytest.raises(ValueError, match="operation"):
        Stage9BaselineRuntimePreflight().prepare(
            runtime_stack=_stack(evaluator=evaluator),
            generation_client=generation,
            citation_client=citation,
        )
    assert generation.responses.create_calls == []
    assert citation.responses.parse_calls == []


@pytest.mark.parametrize(
    "role,key,operation",
    [
        (
            Stage9RuntimeComponentRole.GROUNDED_ANSWER_GENERATOR,
            "generator",
            GENERATOR_OPERATION,
        ),
        (
            Stage9RuntimeComponentRole.CITATION_EVALUATOR,
            "evaluator",
            CITATION_EVALUATOR_OPERATION,
        ),
    ],
)
def test_rejects_unimplemented_reasoning_effort_before_calls(
    role: Stage9RuntimeComponentRole, key: str, operation: str
) -> None:
    generation = Client()
    citation = Client()
    component = _component(
        role,
        operation=operation,
        model=f"{key}-model",
        reasoning_effort="low",
    )
    with pytest.raises(ValueError, match="do not expose reasoning effort"):
        Stage9BaselineRuntimePreflight().prepare(
            runtime_stack=_stack(**{key: component}),
            generation_client=generation,
            citation_client=citation,
        )
    assert generation.responses.create_calls == []
    assert citation.responses.parse_calls == []
