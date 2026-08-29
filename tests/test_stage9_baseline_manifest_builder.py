"""Offline tests for exact Stage 9 baseline manifest construction."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.evals.stage9_baseline_manifest_builder import (
    CANONICAL_DATASET_SHA256,
    Stage9BaselineManifestBuilder,
    Stage9BaselineManifestSettings,
)
from app.schemas.monetary_cost_budget import (
    CostBudgetBasis,
    MonetaryCostBudget,
)
from app.schemas.provider_cost import ModelPriceEntry, PriceRate, UsageUnit
from app.schemas.stage9_baseline_experiment_protocol import (
    Stage9ExecutionProtocol,
    Stage9OperationalBudget,
)
from app.schemas.stage9_evaluation_manifest import (
    HumanReviewDimension,
    Stage9HumanReviewCriterion,
    Stage9HumanReviewRubric,
)

DATASET = Path("evals/datasets/stage9/stage9-locked-golden-dataset-v1.json")


def _price(**updates: object) -> ModelPriceEntry:
    values: dict[str, object] = {
        "price_entry_id": "explicit-offline-test-price",
        "registry_version": "explicit-offline-test-registry-v1",
        "provider_name": "Explicit Test Provider",
        "model_name": "explicit-test-model",
        "operation": "grounded_answer",
        "effective_from": date(2026, 8, 1),
        "effective_through": date(2026, 8, 31),
        "source_reference": "offline test fixture; not a current provider price",
        "rates": (
            PriceRate(
                usage_unit=UsageUnit.INPUT_TOKEN,
                unit_size=Decimal(1_000_000),
                rate_amount=Decimal("1.00"),
                currency="USD",
            ),
            PriceRate(
                usage_unit=UsageUnit.OUTPUT_TOKEN,
                unit_size=Decimal(1_000_000),
                rate_amount=Decimal("2.00"),
                currency="USD",
            ),
        ),
    }
    values.update(updates)
    return ModelPriceEntry.model_validate(values)


def _rubric() -> Stage9HumanReviewRubric:
    return Stage9HumanReviewRubric(
        rubric_id="stage9-baseline-human-review-v1",
        version="1.0.0",
        criteria=tuple(
            Stage9HumanReviewCriterion(
                criterion_id=dimension.value,
                dimension=dimension,
                question=f"Score {dimension.value} from one to five.",
                minimum_score=4,
                blocking=dimension is HumanReviewDimension.CORRECTNESS,
            )
            for dimension in HumanReviewDimension
        ),
    )


def _settings(**updates: object) -> Stage9BaselineManifestSettings:
    values: dict[str, object] = {
        "manifest_id": "stage9-single-agent-baseline-test-v1",
        "manifest_version": "1.0.0",
        "system_profile_id": "bounded-single-agent-test-profile-v1",
        "price_entry": _price(),
        "pricing_date": date(2026, 8, 30),
        "repetitions_per_case": 1,
        "monetary_budget": MonetaryCostBudget(
            basis=CostBudgetBasis.ESTIMATED,
            currency="USD",
            maximum_execution_cost=Decimal("1.00"),
        ),
        "operational_budget": Stage9OperationalBudget(
            maximum_provider_requests=10,
            maximum_external_requests=10,
            maximum_recorded_tokens=100_000,
            maximum_elapsed_seconds=3_600.0,
        ),
        "protocol": Stage9ExecutionProtocol(
            protocol_id="stage9-development-then-holdout-v1",
            protocol_version="1.0.0",
        ),
        "human_review_rubric": _rubric(),
    }
    values.update(updates)
    return Stage9BaselineManifestSettings.model_validate(values)


def test_builds_plan_from_canonical_repository_dataset() -> None:
    plan = Stage9BaselineManifestBuilder().build(
        dataset_path=DATASET, settings=_settings()
    )
    assert plan.manifest.dataset_sha256 == CANONICAL_DATASET_SHA256
    assert plan.manifest.provider_name == "Explicit Test Provider"
    assert plan.development_case_ids == (
        "tech-01",
        "academic-01",
        "patent-01",
        "cross-01",
    )
    assert len(plan.blind_holdout_case_ids) == 6
    assert plan.planned_case_executions == 10


def test_repetitions_change_planned_execution_count() -> None:
    settings = _settings(
        repetitions_per_case=2,
        operational_budget=Stage9OperationalBudget(
            maximum_provider_requests=20,
            maximum_external_requests=20,
            maximum_recorded_tokens=200_000,
            maximum_elapsed_seconds=7_200.0,
        ),
    )
    plan = Stage9BaselineManifestBuilder().build(
        dataset_path=DATASET, settings=settings
    )
    assert plan.planned_case_executions == 20


def test_rejects_price_outside_locked_effective_period() -> None:
    with pytest.raises(ValidationError, match="not effective"):
        _settings(pricing_date=date(2026, 9, 1))


def test_rejects_price_without_exact_model() -> None:
    with pytest.raises(ValidationError, match="exact model"):
        _settings(price_entry=_price(model_name=None))


def test_rejects_price_and_budget_currency_mismatch() -> None:
    budget = MonetaryCostBudget(
        basis=CostBudgetBasis.ESTIMATED,
        currency="KRW",
        maximum_execution_cost=Decimal(1_000),
    )
    with pytest.raises(ValidationError, match="currencies must match"):
        _settings(monetary_budget=budget)


def test_rejects_nonestimated_budget_for_registry_price() -> None:
    budget = MonetaryCostBudget(
        basis=CostBudgetBasis.BILLED,
        currency="USD",
        maximum_execution_cost=Decimal("1.00"),
    )
    with pytest.raises(ValidationError, match="estimated-cost"):
        _settings(monetary_budget=budget)


def test_tampered_dataset_is_rejected_before_plan_creation(tmp_path: Path) -> None:
    target = tmp_path / DATASET.name
    target.write_bytes(DATASET.read_bytes() + b"\n")
    Path(str(target) + ".sha256").write_bytes(
        Path(str(DATASET) + ".sha256").read_bytes()
    )
    with pytest.raises(ValueError, match="checksum"):
        Stage9BaselineManifestBuilder().build(dataset_path=target, settings=_settings())
