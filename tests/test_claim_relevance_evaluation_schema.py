"""Tests for claim relevance evaluation schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.claim_relevance_evaluation import (
    ClaimRelevanceConfusionEntry,
    ClaimRelevanceEvaluationCase,
    ClaimRelevanceEvaluationCaseResult,
    ClaimRelevanceEvaluationDataset,
    ClaimRelevanceEvaluationRun,
)
from app.schemas.claim_relevance_judgment import ClaimRelevanceLevel


def case() -> ClaimRelevanceEvaluationCase:
    return ClaimRelevanceEvaluationCase(
        case_id="case-001",
        question="How are tool calls bounded?",
        objective="Explain bounded execution controls.",
        claim="The runner limits provider calls.",
        expected_relevance_level=ClaimRelevanceLevel.DIRECTLY_RELEVANT,
        description="Direct mechanism.",
    )


def test_dataset_accepts_unique_cases() -> None:
    dataset = ClaimRelevanceEvaluationDataset(
        dataset_id="claim-relevance-golden-v1",
        version="1.0.0",
        cases=[case()],
    )
    assert dataset.cases[0].case_id == "case-001"


def test_dataset_rejects_duplicate_case_ids() -> None:
    with pytest.raises(ValidationError):
        ClaimRelevanceEvaluationDataset(
            dataset_id="claim-relevance-golden-v1",
            version="1.0.0",
            cases=[
                case(),
                case().model_copy(update={"case_id": " CASE-001 "}),
            ],
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("case_id", " "),
        ("question", ""),
        ("objective", " "),
        ("claim", ""),
        ("description", " "),
    ],
)
def test_case_rejects_blank_required_text(
    field: str,
    value: str,
) -> None:
    payload = case().model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        ClaimRelevanceEvaluationCase.model_validate(payload)


def test_run_validates_aggregate_metrics() -> None:
    result = ClaimRelevanceEvaluationCaseResult(
        case_id="case-001",
        expected_relevance_level=ClaimRelevanceLevel.DIRECTLY_RELEVANT,
        actual_relevance_level=ClaimRelevanceLevel.DIRECTLY_RELEVANT,
        relevance_score=0.9,
        correct=True,
        rationale="Direct answer.",
        issues=[],
    )
    run = ClaimRelevanceEvaluationRun(
        dataset_id="claim-relevance-golden-v1",
        dataset_version="1.0.0",
        model="gpt-5",
        case_count=1,
        correct_count=1,
        accuracy=1.0,
        false_directly_relevant_count=0,
        false_irrelevant_count=0,
        results=[result],
        confusion=[
            ClaimRelevanceConfusionEntry(
                expected=ClaimRelevanceLevel.DIRECTLY_RELEVANT,
                actual=ClaimRelevanceLevel.DIRECTLY_RELEVANT,
                count=1,
            )
        ],
    )
    assert run.accuracy == 1.0


def test_run_rejects_incorrect_accuracy() -> None:
    result = ClaimRelevanceEvaluationCaseResult(
        case_id="case-001",
        expected_relevance_level=ClaimRelevanceLevel.DIRECTLY_RELEVANT,
        actual_relevance_level=ClaimRelevanceLevel.DIRECTLY_RELEVANT,
        relevance_score=0.9,
        correct=True,
        rationale="Direct answer.",
        issues=[],
    )
    with pytest.raises(ValidationError):
        ClaimRelevanceEvaluationRun(
            dataset_id="claim-relevance-golden-v1",
            dataset_version="1.0.0",
            model="gpt-5",
            case_count=1,
            correct_count=1,
            accuracy=0.5,
            false_directly_relevant_count=0,
            false_irrelevant_count=0,
            results=[result],
            confusion=[
                ClaimRelevanceConfusionEntry(
                    expected=ClaimRelevanceLevel.DIRECTLY_RELEVANT,
                    actual=ClaimRelevanceLevel.DIRECTLY_RELEVANT,
                    count=1,
                )
            ],
        )
