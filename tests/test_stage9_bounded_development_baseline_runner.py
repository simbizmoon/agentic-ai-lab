"""Offline tests for the bounded Stage 9 development runner."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.evals.stage9_bounded_development_baseline_runner import (
    BoundedStage9DevelopmentBaselineRunner,
    Stage9DevelopmentBaselineRunnerError,
    Stage9DevelopmentCaseExecutionError,
)
from app.schemas.provider_cost import CostKind
from app.schemas.stage9_development_baseline_run import (
    STAGE9_DEVELOPMENT_CASE_IDS,
    Stage9DevelopmentCaseRecord,
    Stage9DevelopmentCaseStatus,
    Stage9DevelopmentCaseUsage,
    Stage9DevelopmentRunBudget,
    Stage9DevelopmentRunRequest,
    Stage9DevelopmentRunStatus,
)

DIRECTORY = Path("evals/manifests/stage9/stage9-single-agent-baseline-live-v1")
MANIFEST = DIRECTORY / "approved-live-baseline.json"
REVIEW = DIRECTORY / "runtime-budget-review.md"
MANIFEST_SHA = "60179543f5290136d434d4f4c72598af8f74eb569a1d06b43c7490320d81e191"
REVIEW_SHA = "f36c0b7bee7cc9548f2f3a36946e4b49293883b69349b4499f2c80d27190cae7"


def _request(**updates: object) -> Stage9DevelopmentRunRequest:
    values: dict[str, object] = {
        "run_id": "stage9-development-offline-run-001",
        "manifest_sha256": MANIFEST_SHA,
        "review_sha256": REVIEW_SHA,
        "case_ids": STAGE9_DEVELOPMENT_CASE_IDS,
        "repetitions_per_case": 1,
        "budget": Stage9DevelopmentRunBudget(
            maximum_provider_requests=16,
            maximum_external_requests=24,
            maximum_recorded_tokens=120_000,
            maximum_elapsed_seconds=2_880.0,
            maximum_estimated_cost=Decimal("1.50"),
            currency="USD",
        ),
        "allow_blind_holdout": False,
    }
    values.update(updates)
    return Stage9DevelopmentRunRequest.model_validate(values)


class ControlledExecutor:
    def __init__(
        self,
        *,
        statuses: dict[str, Stage9DevelopmentCaseStatus] | None = None,
        per_case_cost: Decimal = Decimal("0.10"),
        fail_on: str | None = None,
        wrong_case: bool = False,
    ) -> None:
        self.statuses = statuses or {}
        self.per_case_cost = per_case_cost
        self.fail_on = fail_on
        self.wrong_case = wrong_case
        self.calls: list[str] = []

    def execute(self, *, case_id: str, request) -> Stage9DevelopmentCaseRecord:
        del request
        self.calls.append(case_id)
        if case_id == self.fail_on:
            raise Stage9DevelopmentCaseExecutionError("controlled executor failure")
        returned_id = "academic-01" if self.wrong_case else case_id
        marker = STAGE9_DEVELOPMENT_CASE_IDS.index(case_id) + 1
        return Stage9DevelopmentCaseRecord(
            case_id=returned_id,
            execution_id=f"{case_id}-execution-001",
            status=self.statuses.get(
                case_id, Stage9DevelopmentCaseStatus.ANSWER_AVAILABLE
            ),
            workflow_artifact_path=f"cases/{case_id}/workflow.json",
            workflow_artifact_sha256=f"{marker:x}" * 64,
            response_model_ids=("gpt-5.6-terra",),
            usage=Stage9DevelopmentCaseUsage(
                provider_requests=3,
                external_requests=3,
                recorded_tokens=1_000,
                elapsed_seconds=2.0,
                estimated_cost=self.per_case_cost,
                currency="USD",
                cost_kind=CostKind.ESTIMATED,
            ),
        )


def _runner(executor: ControlledExecutor):
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    return BoundedStage9DevelopmentBaselineRunner(
        experiment=experiment,
        executor=executor,
    )


def test_runs_exact_four_development_cases_in_locked_order() -> None:
    executor = ControlledExecutor()
    result = _runner(executor).run(_request())
    assert result.status is Stage9DevelopmentRunStatus.COMPLETED
    assert tuple(executor.calls) == STAGE9_DEVELOPMENT_CASE_IDS
    assert result.usage.provider_requests == 12
    assert result.usage.estimated_cost == Decimal("0.40")


def test_abstention_is_a_completed_case_and_does_not_force_retry() -> None:
    executor = ControlledExecutor(
        statuses={"tech-01": Stage9DevelopmentCaseStatus.ABSTAINED}
    )
    result = _runner(executor).run(_request())
    assert result.status is Stage9DevelopmentRunStatus.COMPLETED
    assert len(executor.calls) == 4


def test_incomplete_case_stops_before_next_case() -> None:
    executor = ControlledExecutor(
        statuses={"academic-01": Stage9DevelopmentCaseStatus.INCOMPLETE}
    )
    result = _runner(executor).run(_request())
    assert result.status is Stage9DevelopmentRunStatus.INCOMPLETE
    assert executor.calls == ["tech-01", "academic-01"]


def test_failed_case_stops_before_next_case() -> None:
    executor = ControlledExecutor(
        statuses={"academic-01": Stage9DevelopmentCaseStatus.FAILED}
    )
    result = _runner(executor).run(_request())
    assert result.status is Stage9DevelopmentRunStatus.FAILED
    assert executor.calls == ["tech-01", "academic-01"]


def test_executor_exception_preserves_prior_records_and_stops() -> None:
    executor = ControlledExecutor(fail_on="academic-01")
    result = _runner(executor).run(_request())
    assert result.status is Stage9DevelopmentRunStatus.FAILED
    assert tuple(item.case_id for item in result.case_records) == ("tech-01",)
    assert executor.calls == ["tech-01", "academic-01"]


def test_cost_overrun_stops_after_persisted_case() -> None:
    executor = ControlledExecutor(per_case_cost=Decimal("0.80"))
    result = _runner(executor).run(_request())
    assert result.status is Stage9DevelopmentRunStatus.STOPPED
    assert result.budget_exhausted is True
    assert executor.calls == ["tech-01", "academic-01"]
    assert len(result.case_records) == 2


def test_exact_ceiling_prevents_starting_another_case() -> None:
    executor = ControlledExecutor(per_case_cost=Decimal("0.75"))
    result = _runner(executor).run(_request())
    assert result.status is Stage9DevelopmentRunStatus.STOPPED
    assert result.budget_exhausted is False
    assert executor.calls == ["tech-01", "academic-01"]
    assert "reached before next case" in result.stop_reason


def test_wrong_case_record_is_rejected() -> None:
    executor = ControlledExecutor(wrong_case=True)
    with pytest.raises(Stage9DevelopmentBaselineRunnerError, match="wrong case"):
        _runner(executor).run(_request())


def test_wrong_manifest_hash_is_rejected_before_executor_call() -> None:
    executor = ControlledExecutor()
    request = _request(manifest_sha256="0" * 64)
    with pytest.raises(Stage9DevelopmentBaselineRunnerError, match="approved manifest"):
        _runner(executor).run(request)
    assert executor.calls == []
