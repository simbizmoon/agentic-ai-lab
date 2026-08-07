"""Tests for semantic citation evaluation schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.semantic_citation_evaluation import (
    SemanticCitationConfusionEntry,
    SemanticCitationEvaluationCase,
    SemanticCitationEvaluationCaseResult,
    SemanticCitationEvaluationDataset,
    SemanticCitationEvaluationRun,
)
from app.schemas.semantic_citation_judgment import (
    SemanticCitationSupportLevel,
)


def case(
    *,
    case_id: str = "case-001",
    expected: SemanticCitationSupportLevel = (
        SemanticCitationSupportLevel.FULLY_SUPPORTED
    ),
) -> SemanticCitationEvaluationCase:
    """Return one valid semantic citation evaluation case."""

    return SemanticCitationEvaluationCase(
        case_id=case_id,
        claim="The SDK supports function tools.",
        evidence="The SDK supports function tools.",
        expected_support_level=expected,
        description="Direct support case.",
    )


def test_case_accepts_valid_values() -> None:
    value = case()

    assert value.case_id == "case-001"
    assert value.expected_support_level is (
        SemanticCitationSupportLevel.FULLY_SUPPORTED
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("case_id", " "),
        ("claim", ""),
        ("evidence", "   "),
        ("description", "\t"),
    ],
)
def test_case_rejects_blank_required_text(
    field_name: str,
    value: str,
) -> None:
    values = {
        "case_id": "case-001",
        "claim": "Claim.",
        "evidence": "Evidence.",
        "expected_support_level": (
            SemanticCitationSupportLevel.FULLY_SUPPORTED
        ),
        "description": "Description.",
    }
    values[field_name] = value

    with pytest.raises(
        ValidationError,
        match=f"{field_name} must not be blank",
    ):
        SemanticCitationEvaluationCase.model_validate(
            values
        )


def test_dataset_accepts_unique_cases() -> None:
    dataset = SemanticCitationEvaluationDataset(
        dataset_id="semantic-citation-golden-v1",
        version="1.0.0",
        cases=[
            case(case_id="case-001"),
            case(
                case_id="case-002",
                expected=(
                    SemanticCitationSupportLevel
                    .PARTIALLY_SUPPORTED
                ),
            ),
        ],
    )

    assert len(dataset.cases) == 2


def test_dataset_rejects_duplicate_case_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="dataset cases must have unique case IDs",
    ):
        SemanticCitationEvaluationDataset(
            dataset_id="semantic-citation-golden-v1",
            version="1.0.0",
            cases=[
                case(case_id="Case-001"),
                case(case_id=" case-001 "),
            ],
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("dataset_id", " "),
        ("version", ""),
    ],
)
def test_dataset_rejects_blank_identity(
    field_name: str,
    value: str,
) -> None:
    values = {
        "dataset_id": "semantic-citation-golden-v1",
        "version": "1.0.0",
        "cases": [case()],
    }
    values[field_name] = value

    with pytest.raises(ValidationError):
        SemanticCitationEvaluationDataset.model_validate(
            values
        )


def test_case_result_accepts_semantic_prediction() -> None:
    result = SemanticCitationEvaluationCaseResult(
        case_id="case-001",
        expected_support_level=(
            SemanticCitationSupportLevel.PARTIALLY_SUPPORTED
        ),
        actual_support_level=(
            SemanticCitationSupportLevel.UNSUPPORTED
        ),
        entailment_score=0.3,
        correct=False,
        rationale="Support was insufficient.",
        issues=["Qualifier was unsupported."],
    )

    assert result.correct is False
    assert result.entailment_score == pytest.approx(0.3)


def test_confusion_entry_records_expected_actual_pair() -> None:
    entry = SemanticCitationConfusionEntry(
        expected=(
            SemanticCitationSupportLevel.CONTRADICTED
        ),
        actual=(
            SemanticCitationSupportLevel.UNSUPPORTED
        ),
        count=2,
    )

    assert entry.count == 2


def test_run_accepts_aggregate_result() -> None:
    result = SemanticCitationEvaluationCaseResult(
        case_id="case-001",
        expected_support_level=(
            SemanticCitationSupportLevel.FULLY_SUPPORTED
        ),
        actual_support_level=(
            SemanticCitationSupportLevel.FULLY_SUPPORTED
        ),
        entailment_score=1.0,
        correct=True,
        rationale="Fully supported.",
        issues=[],
    )

    run = SemanticCitationEvaluationRun(
        dataset_id="semantic-citation-golden-v1",
        dataset_version="1.0.0",
        model="test-model",
        case_count=1,
        correct_count=1,
        accuracy=1.0,
        false_fully_supported_count=0,
        false_rejected_count=0,
        results=[result],
        confusion=[
            SemanticCitationConfusionEntry(
                expected=(
                    SemanticCitationSupportLevel
                    .FULLY_SUPPORTED
                ),
                actual=(
                    SemanticCitationSupportLevel
                    .FULLY_SUPPORTED
                ),
                count=1,
            )
        ],
    )

    assert run.accuracy == pytest.approx(1.0)
    assert run.case_count == 1


def test_run_rejects_inconsistent_accuracy() -> None:
    result = SemanticCitationEvaluationCaseResult(
        case_id="case-001",
        expected_support_level=(
            SemanticCitationSupportLevel.FULLY_SUPPORTED
        ),
        actual_support_level=(
            SemanticCitationSupportLevel.FULLY_SUPPORTED
        ),
        entailment_score=1.0,
        correct=True,
        rationale="Fully supported.",
        issues=[],
    )

    with pytest.raises(
        ValidationError,
        match="accuracy must match evaluation results",
    ):
        SemanticCitationEvaluationRun(
            dataset_id="semantic-citation-golden-v1",
            dataset_version="1.0.0",
            model="test-model",
            case_count=1,
            correct_count=1,
            accuracy=0.5,
            false_fully_supported_count=0,
            false_rejected_count=0,
            results=[result],
            confusion=[
                SemanticCitationConfusionEntry(
                    expected=(
                        SemanticCitationSupportLevel
                        .FULLY_SUPPORTED
                    ),
                    actual=(
                        SemanticCitationSupportLevel
                        .FULLY_SUPPORTED
                    ),
                    count=1,
                )
            ],
        )
