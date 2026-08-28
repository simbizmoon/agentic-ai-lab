"""Offline tests for locked Stage 9 experiment contracts."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.evals.evaluation_case_definition import (
    EvaluationCaseDefinition,
    EvaluationInput,
)
from app.evals.evaluation_dataset import EvaluationDifficulty
from app.evals.evaluation_expected_outcome import EvaluationExpectedOutcome
from app.schemas.monetary_cost_budget import MonetaryCostBudget
from app.schemas.stage9_evaluation_manifest import (
    HumanReviewDimension,
    Stage9DatasetPartition,
    Stage9EvaluationCase,
    Stage9EvaluationDomain,
    Stage9ExperimentManifest,
    Stage9HumanReviewCriterion,
    Stage9HumanReviewRubric,
)


def _rubric() -> Stage9HumanReviewRubric:
    return Stage9HumanReviewRubric(
        rubric_id="stage9-human-review-v1",
        version="1.0.0",
        criteria=tuple(
            Stage9HumanReviewCriterion(
                criterion_id=dimension.value,
                dimension=dimension,
                question=f"Review {dimension.value} on a five-point scale.",
                minimum_score=4,
                blocking=dimension is HumanReviewDimension.CORRECTNESS,
            )
            for dimension in HumanReviewDimension
        ),
    )


def _case(index: int) -> Stage9EvaluationCase:
    domains = tuple(Stage9EvaluationDomain)
    definition = EvaluationCaseDefinition(
        case_id=f"stage9-case-{index:02d}",
        name=f"Stage 9 case {index}",
        description="A bounded real-research evaluation case.",
        difficulty=EvaluationDifficulty.MEDIUM,
        evaluation_input=EvaluationInput(research_question=f"Question {index}?"),
        expected_outcome=EvaluationExpectedOutcome(
            outcome_id=f"outcome-{index:02d}",
            name=f"Expected outcome {index}",
            description="Expected grounded research boundary.",
        ),
    )
    return Stage9EvaluationCase(
        definition=definition,
        domain=domains[(index - 1) % len(domains)],
        partition=(
            Stage9DatasetPartition.DEVELOPMENT
            if index <= 5
            else Stage9DatasetPartition.LOCKED
        ),
        prohibited_claims=("Do not invent unsupported conclusions.",),
        expected_uncertainties=("State when available evidence is insufficient.",),
    )


def _manifest(**updates: object) -> Stage9ExperimentManifest:
    cases = tuple(_case(index) for index in range(1, 11))
    values: dict[str, object] = {
        "manifest_id": "stage9-single-agent-baseline-v1",
        "manifest_version": "1.0.0",
        "dataset_id": "aira-real-research-golden-v1",
        "dataset_version": "1.0.0",
        "dataset_sha256": "a" * 64,
        "system_profile_id": "bounded-single-agent-profile-v1",
        "architecture": "bounded_single_agent",
        "provider_name": "OpenAI",
        "model_name": "fixture-model",
        "price_registry_version": "price-registry-v1",
        "cases": cases,
        "case_order": tuple(item.definition.case_id for item in cases),
        "repetitions_per_case": 1,
        "execution_budget": MonetaryCostBudget(
            currency="USD", maximum_execution_cost=Decimal("1.00")
        ),
        "human_review_rubric": _rubric(),
    }
    values.update(updates)
    return Stage9ExperimentManifest.model_validate(values)


def test_accepts_complete_frozen_stage9_manifest() -> None:
    manifest = _manifest()
    assert len(manifest.cases) == 10
    assert {case.domain for case in manifest.cases} == set(Stage9EvaluationDomain)
    assert manifest.architecture == "bounded_single_agent"


def test_rejects_fewer_than_ten_cases() -> None:
    cases = tuple(_case(index) for index in range(1, 10))
    with pytest.raises(ValidationError):
        _manifest(cases=cases, case_order=tuple(x.definition.case_id for x in cases))


def test_rejects_changed_case_order() -> None:
    with pytest.raises(ValidationError, match="case_order"):
        _manifest(case_order=tuple(reversed(_manifest().case_order)))


def test_rejects_missing_domain() -> None:
    cases = tuple(
        case.model_copy(update={"domain": Stage9EvaluationDomain.ACADEMIC})
        for case in _manifest().cases
    )
    with pytest.raises(ValidationError, match="domain"):
        _manifest(cases=cases)


def test_rejects_dataset_without_locked_partition() -> None:
    cases = tuple(
        case.model_copy(update={"partition": Stage9DatasetPartition.DEVELOPMENT})
        for case in _manifest().cases
    )
    with pytest.raises(ValidationError, match="locked"):
        _manifest(cases=cases)


def test_rejects_incomplete_human_review_rubric() -> None:
    incomplete = Stage9HumanReviewRubric.model_construct(
        rubric_id="unsafe", version="1", criteria=_rubric().criteria[:3]
    )
    with pytest.raises(ValidationError, match="dimension"):
        _manifest(human_review_rubric=incomplete)
