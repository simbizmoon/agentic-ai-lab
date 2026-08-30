"""Offline tests for the Stage 9 development-only baseline contract."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.provider_cost import CostKind
from app.schemas.stage9_development_baseline_run import (
    STAGE9_DEVELOPMENT_CASE_IDS,
    Stage9DevelopmentCaseRecord,
    Stage9DevelopmentCaseStatus,
    Stage9DevelopmentCaseUsage,
    Stage9DevelopmentRunBudget,
    Stage9DevelopmentRunRequest,
    Stage9DevelopmentRunResult,
    Stage9DevelopmentRunStatus,
    Stage9DevelopmentRunUsage,
)

MANIFEST_SHA = "6" * 64
REVIEW_SHA = "f" * 64


def _budget(**updates: object) -> Stage9DevelopmentRunBudget:
    values: dict[str, object] = {
        "maximum_provider_requests": 16,
        "maximum_external_requests": 24,
        "maximum_recorded_tokens": 120_000,
        "maximum_elapsed_seconds": 2_880.0,
        "maximum_estimated_cost": Decimal("1.50"),
        "currency": "USD",
    }
    values.update(updates)
    return Stage9DevelopmentRunBudget.model_validate(values)


def _request(**updates: object) -> Stage9DevelopmentRunRequest:
    values: dict[str, object] = {
        "run_id": "stage9-development-baseline-v1-run-001",
        "manifest_sha256": MANIFEST_SHA,
        "review_sha256": REVIEW_SHA,
        "case_ids": STAGE9_DEVELOPMENT_CASE_IDS,
        "repetitions_per_case": 1,
        "budget": _budget(),
        "allow_blind_holdout": False,
    }
    values.update(updates)
    return Stage9DevelopmentRunRequest.model_validate(values)


def _case(index: int, *, cost: str = "0.10") -> Stage9DevelopmentCaseRecord:
    case_id = STAGE9_DEVELOPMENT_CASE_IDS[index]
    return Stage9DevelopmentCaseRecord(
        case_id=case_id,
        execution_id=f"{case_id}-execution-001",
        status=Stage9DevelopmentCaseStatus.ANSWER_AVAILABLE,
        workflow_artifact_path=f"cases/{case_id}/workflow.json",
        workflow_artifact_sha256=f"{index + 1:x}" * 64,
        response_model_ids=("gpt-5.6-terra",),
        usage=Stage9DevelopmentCaseUsage(
            provider_requests=3,
            external_requests=3,
            recorded_tokens=1_000,
            elapsed_seconds=2.0,
            estimated_cost=Decimal(cost),
            currency="USD",
            cost_kind=CostKind.ESTIMATED,
        ),
    )


def _usage(records: tuple[Stage9DevelopmentCaseRecord, ...]):
    return Stage9DevelopmentRunUsage(
        provider_requests=sum(item.usage.provider_requests for item in records),
        external_requests=sum(item.usage.external_requests for item in records),
        recorded_tokens=sum(item.usage.recorded_tokens for item in records),
        elapsed_seconds=sum(item.usage.elapsed_seconds for item in records),
        estimated_cost=sum((item.usage.estimated_cost for item in records), Decimal(0)),
        currency="USD",
        cost_kind=CostKind.ESTIMATED,
    )


def test_accepts_exact_four_case_completed_development_run() -> None:
    records = tuple(_case(index) for index in range(4))
    result = Stage9DevelopmentRunResult(
        request=_request(),
        status=Stage9DevelopmentRunStatus.COMPLETED,
        case_records=records,
        usage=_usage(records),
        budget_exhausted=False,
    )
    assert tuple(item.case_id for item in result.case_records) == (
        STAGE9_DEVELOPMENT_CASE_IDS
    )
    assert result.usage.estimated_cost == Decimal("0.40")


def test_rejects_any_blind_holdout_case_in_request() -> None:
    with pytest.raises(ValidationError, match="development order"):
        _request(case_ids=("tech-01", "academic-01", "patent-01", "cross-02"))


def test_rejects_explicit_holdout_permission() -> None:
    with pytest.raises(ValidationError, match="forbidden"):
        _request(allow_blind_holdout=True)


def test_rejects_repetition_above_one() -> None:
    with pytest.raises(ValidationError):
        _request(repetitions_per_case=2)


def test_rejects_phase_budget_above_human_approved_ceiling() -> None:
    with pytest.raises(ValidationError):
        _budget(maximum_estimated_cost=Decimal("1.51"))


def test_rejects_billed_cost_authority_for_estimated_ledger() -> None:
    with pytest.raises(ValidationError, match="estimated cost authority"):
        Stage9DevelopmentCaseUsage(
            provider_requests=1,
            external_requests=1,
            recorded_tokens=10,
            elapsed_seconds=1.0,
            estimated_cost=Decimal("0.01"),
            currency="USD",
            cost_kind=CostKind.BILLED,
        )


def test_rejects_non_prefix_case_result_order() -> None:
    records = (_case(1),)
    with pytest.raises(ValidationError, match="development-order prefix"):
        Stage9DevelopmentRunResult(
            request=_request(),
            status=Stage9DevelopmentRunStatus.INCOMPLETE,
            case_records=records,
            usage=_usage(records),
            budget_exhausted=False,
            stop_reason="first case was not preserved",
        )


def test_rejects_incorrect_aggregate_usage() -> None:
    records = (_case(0),)
    wrong = Stage9DevelopmentRunUsage(
        provider_requests=2,
        external_requests=3,
        recorded_tokens=1_000,
        elapsed_seconds=2.0,
        estimated_cost=Decimal("0.10"),
        currency="USD",
        cost_kind=CostKind.ESTIMATED,
    )
    with pytest.raises(ValidationError, match="exact case-record totals"):
        Stage9DevelopmentRunResult(
            request=_request(),
            status=Stage9DevelopmentRunStatus.INCOMPLETE,
            case_records=records,
            usage=wrong,
            budget_exhausted=False,
            stop_reason="controlled stop",
        )


def test_budget_exhaustion_matches_exact_cost() -> None:
    records = tuple(_case(index, cost="0.40") for index in range(4))
    result = Stage9DevelopmentRunResult(
        request=_request(),
        status=Stage9DevelopmentRunStatus.STOPPED,
        case_records=records,
        usage=_usage(records),
        budget_exhausted=True,
        stop_reason="estimated monetary ceiling exceeded",
    )
    assert result.usage.estimated_cost == Decimal("1.60")


def test_rejects_completed_run_with_missing_case() -> None:
    records = tuple(_case(index) for index in range(3))
    with pytest.raises(ValidationError, match="all four cases"):
        Stage9DevelopmentRunResult(
            request=_request(),
            status=Stage9DevelopmentRunStatus.COMPLETED,
            case_records=records,
            usage=_usage(records),
            budget_exhausted=False,
        )
