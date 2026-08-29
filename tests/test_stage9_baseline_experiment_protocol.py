"""Offline tests for the locked Stage 9 baseline execution protocol."""

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
from app.schemas.stage9_baseline_experiment_protocol import (
    Stage9BaselineExperimentPlan,
    Stage9ExecutionPhase,
    Stage9ExecutionProtocol,
    Stage9OperationalBudget,
)
from app.schemas.stage9_evaluation_manifest import (
    HumanReviewDimension,
    Stage9DatasetPartition,
    Stage9EvaluationCase,
    Stage9EvaluationDomain,
    Stage9ExperimentManifest,
    Stage9HumanReviewCriterion,
    Stage9HumanReviewRubric,
)


def _case(index: int) -> Stage9EvaluationCase:
    domains = tuple(Stage9EvaluationDomain)
    return Stage9EvaluationCase(
        definition=EvaluationCaseDefinition(
            case_id=f"case-{index:02d}",
            name=f"Case {index}",
            description="Human-locked Stage 9 case.",
            difficulty=EvaluationDifficulty.MEDIUM,
            evaluation_input=EvaluationInput(research_question=f"Question {index}?"),
            expected_outcome=EvaluationExpectedOutcome(
                outcome_id=f"outcome-{index:02d}",
                name=f"Outcome {index}",
                description="Expected grounded boundary.",
            ),
        ),
        domain=domains[(index - 1) % len(domains)],
        partition=(
            Stage9DatasetPartition.DEVELOPMENT
            if index in {1, 3, 5, 8}
            else Stage9DatasetPartition.LOCKED
        ),
        prohibited_claims=("Do not invent unsupported conclusions.",),
        expected_uncertainties=("Disclose insufficient evidence.",),
    )


def _manifest(repetitions: int = 1) -> Stage9ExperimentManifest:
    cases = tuple(_case(index) for index in range(1, 11))
    rubric = Stage9HumanReviewRubric(
        rubric_id="stage9-review-v1",
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
    return Stage9ExperimentManifest(
        manifest_id="stage9-single-agent-baseline-v1",
        manifest_version="1.0.0",
        dataset_id="aira-stage9-golden-v1",
        dataset_version="1.0.0",
        dataset_sha256="a" * 64,
        system_profile_id="bounded-single-agent-v1",
        architecture="bounded_single_agent",
        provider_name="provider-fixed-before-live-run",
        model_name="model-fixed-before-live-run",
        price_registry_version="price-registry-fixed-before-live-run",
        cases=cases,
        case_order=tuple(case.definition.case_id for case in cases),
        repetitions_per_case=repetitions,
        execution_budget=MonetaryCostBudget(
            currency="USD", maximum_execution_cost=Decimal("1.00")
        ),
        human_review_rubric=rubric,
    )


def _plan(**updates: object) -> Stage9BaselineExperimentPlan:
    manifest = updates.pop("manifest", _manifest())
    values: dict[str, object] = {
        "manifest": manifest,
        "operational_budget": Stage9OperationalBudget(
            maximum_provider_requests=10,
            maximum_external_requests=10,
            maximum_recorded_tokens=100_000,
            maximum_elapsed_seconds=3_600.0,
        ),
        "protocol": Stage9ExecutionProtocol(
            protocol_id="stage9-dev-then-holdout-v1",
            protocol_version="1.0.0",
        ),
        "development_case_ids": ("case-01", "case-03", "case-05", "case-08"),
        "blind_holdout_case_ids": (
            "case-02",
            "case-04",
            "case-06",
            "case-07",
            "case-09",
            "case-10",
        ),
        "planned_case_executions": 10,
    }
    values.update(updates)
    return Stage9BaselineExperimentPlan.model_validate(values)


def test_accepts_complete_locked_baseline_plan() -> None:
    plan = _plan()
    assert plan.planned_case_executions == 10
    assert plan.protocol.phase_order[-1] is Stage9ExecutionPhase.BLIND_HOLDOUT


def test_rejects_holdout_before_development() -> None:
    with pytest.raises(ValidationError, match="development must run"):
        Stage9ExecutionProtocol(
            protocol_id="unsafe",
            protocol_version="1",
            phase_order=(
                Stage9ExecutionPhase.BLIND_HOLDOUT,
                Stage9ExecutionPhase.DEVELOPMENT,
            ),
        )


@pytest.mark.parametrize(
    "field,value",
    [("allow_holdout_adjustment", True), ("reveal_holdout_before_manifest_lock", True)],
)
def test_rejects_holdout_tuning(field: str, value: bool) -> None:
    with pytest.raises(ValidationError, match="blind holdout"):
        Stage9ExecutionProtocol.model_validate(
            {
                "protocol_id": "unsafe",
                "protocol_version": "1",
                field: value,
            }
        )


def test_rejects_development_adjustment_without_new_manifest() -> None:
    with pytest.raises(ValidationError, match="new locked manifest"):
        Stage9ExecutionProtocol(
            protocol_id="unsafe",
            protocol_version="1",
            allow_development_adjustment=True,
            require_new_manifest_after_development_adjustment=False,
        )


def test_rejects_external_request_ceiling_below_provider_ceiling() -> None:
    with pytest.raises(ValidationError, match="external-request ceiling"):
        Stage9OperationalBudget(
            maximum_provider_requests=10,
            maximum_external_requests=9,
            maximum_recorded_tokens=1,
            maximum_elapsed_seconds=1.0,
        )


def test_rejects_partition_identity_drift() -> None:
    with pytest.raises(ValidationError, match="development IDs"):
        _plan(development_case_ids=("case-01",))


def test_rejects_incorrect_planned_execution_count() -> None:
    with pytest.raises(ValidationError, match="cases times repetitions"):
        _plan(planned_case_executions=9)


def test_rejects_request_budget_below_planned_runs() -> None:
    budget = Stage9OperationalBudget(
        maximum_provider_requests=10,
        maximum_external_requests=10,
        maximum_recorded_tokens=100_000,
        maximum_elapsed_seconds=3_600.0,
    )
    with pytest.raises(ValidationError, match="one request per planned run"):
        _plan(
            manifest=_manifest(repetitions=2),
            operational_budget=budget,
            planned_case_executions=20,
        )
