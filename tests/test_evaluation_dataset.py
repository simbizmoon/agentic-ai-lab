"""Tests for research evaluation dataset schemas."""

import pytest
from pydantic import ValidationError

from app.evals.evaluation_dataset import (
    EvaluationCase,
    EvaluationCaseStatus,
    EvaluationDataset,
    EvaluationDifficulty,
    ExpectedClaim,
    ExpectedEvidence,
    ExpectedSource,
)


def expected_source(
    *,
    source_id: str = "source-001",
    required: bool = True,
) -> ExpectedSource:
    """Return one expected source."""

    return ExpectedSource(
        source_id=source_id,
        title="Authoritative research source",
        canonical_url="https://example.com/source",
        publisher="Example Publisher",
        required=required,
    )


def expected_evidence(
    *,
    evidence_id: str = "evidence-001",
    source_id: str = "source-001",
    required: bool = True,
) -> ExpectedEvidence:
    """Return one expected evidence item."""

    return ExpectedEvidence(
        evidence_id=evidence_id,
        source_id=source_id,
        expected_text="The source supports the finding.",
        location_hint="Section 2",
        required=required,
    )


def expected_claim(
    *,
    claim_id: str = "claim-001",
    evidence_ids: list[str] | None = None,
    required: bool = True,
) -> ExpectedClaim:
    """Return one expected claim."""

    return ExpectedClaim(
        claim_id=claim_id,
        expected_text="The finding is supported.",
        supporting_evidence_ids=(
            evidence_ids or ["evidence-001"]
        ),
        required=required,
        minimum_support_count=1,
    )


def evaluation_case(
    *,
    case_id: str = "case-001",
    status: EvaluationCaseStatus = (
        EvaluationCaseStatus.ACTIVE
    ),
) -> EvaluationCase:
    """Return one complete evaluation case."""

    return EvaluationCase(
        case_id=case_id,
        name="Basic grounding case",
        description=(
            "Evaluate source, evidence, and claim grounding."
        ),
        research_question=(
            "What finding does the source support?"
        ),
        status=status,
        difficulty=EvaluationDifficulty.MEDIUM,
        input_context=[
            "Use authoritative sources.",
        ],
        expected_sources=[
            expected_source(),
        ],
        expected_evidence=[
            expected_evidence(),
        ],
        expected_claims=[
            expected_claim(),
        ],
        required_report_elements=[
            "Supported finding",
            "Source citation",
        ],
        forbidden_report_elements=[
            "Unsupported numerical estimate",
        ],
        tags=[
            "grounding",
            "citation",
        ],
        minimum_overall_score=0.8,
    )


def test_evaluation_case_tracks_required_counts() -> None:
    value = EvaluationCase(
        case_id="case-counts",
        name="Count expected artifacts",
        description="Count required expected artifacts.",
        research_question="What is supported?",
        difficulty=EvaluationDifficulty.EASY,
        expected_sources=[
            expected_source(
                source_id="source-required",
                required=True,
            ),
            expected_source(
                source_id="source-optional",
                required=False,
            ),
        ],
        expected_evidence=[
            expected_evidence(
                evidence_id="evidence-required",
                source_id="source-required",
                required=True,
            ),
            expected_evidence(
                evidence_id="evidence-optional",
                source_id="source-optional",
                required=False,
            ),
        ],
        expected_claims=[
            expected_claim(
                claim_id="claim-required",
                evidence_ids=["evidence-required"],
                required=True,
            ),
            expected_claim(
                claim_id="claim-optional",
                evidence_ids=["evidence-optional"],
                required=False,
            ),
        ],
    )

    assert value.required_source_count == 1
    assert value.required_evidence_count == 1
    assert value.required_claim_count == 1


def test_case_rejects_unknown_source_reference() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "expected evidence must reference "
            "an expected source"
        ),
    ):
        EvaluationCase(
            case_id="case-invalid-source",
            name="Invalid source reference",
            description="Evidence references missing source.",
            research_question="What is supported?",
            difficulty=EvaluationDifficulty.MEDIUM,
            expected_sources=[
                expected_source(),
            ],
            expected_evidence=[
                expected_evidence(
                    source_id="source-missing"
                ),
            ],
        )


def test_case_rejects_unknown_evidence_reference() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "expected claim must reference "
            "expected evidence"
        ),
    ):
        EvaluationCase(
            case_id="case-invalid-evidence",
            name="Invalid evidence reference",
            description="Claim references missing evidence.",
            research_question="What is supported?",
            difficulty=EvaluationDifficulty.MEDIUM,
            expected_sources=[
                expected_source(),
            ],
            expected_evidence=[
                expected_evidence(),
            ],
            expected_claims=[
                expected_claim(
                    evidence_ids=["evidence-missing"]
                ),
            ],
        )


def test_case_rejects_duplicate_source_ids() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "expected source IDs must not "
            "contain duplicates"
        ),
    ):
        EvaluationCase(
            case_id="case-duplicate-source",
            name="Duplicate source IDs",
            description="Duplicate source IDs are invalid.",
            research_question="What is supported?",
            difficulty=EvaluationDifficulty.EASY,
            expected_sources=[
                expected_source(source_id="SOURCE-001"),
                expected_source(source_id="source-001"),
            ],
        )


def test_case_rejects_conflicting_report_elements() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "report elements must not be both "
            "required and forbidden"
        ),
    ):
        EvaluationCase(
            case_id="case-conflict",
            name="Conflicting report requirements",
            description="One element appears in both lists.",
            research_question="What is supported?",
            difficulty=EvaluationDifficulty.EASY,
            required_report_elements=[
                "Source citation",
            ],
            forbidden_report_elements=[
                "source citation",
            ],
        )


def test_claim_rejects_excessive_minimum_support() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "minimum_support_count must not exceed "
            "supporting evidence count"
        ),
    ):
        ExpectedClaim(
            claim_id="claim-invalid",
            expected_text="A supported claim.",
            supporting_evidence_ids=[
                "evidence-001",
            ],
            minimum_support_count=2,
        )


def test_dataset_returns_active_cases() -> None:
    dataset = EvaluationDataset(
        dataset_id="dataset-001",
        name="AIRA evaluation dataset",
        description="Baseline research evaluation cases.",
        version="1.0.0",
        cases=[
            evaluation_case(case_id="case-active"),
            evaluation_case(
                case_id="case-retired",
                status=EvaluationCaseStatus.RETIRED,
            ),
        ],
        tags=[
            "aira",
            "baseline",
        ],
    )

    assert [
        case.case_id
        for case in dataset.active_cases
    ] == ["case-active"]


def test_dataset_finds_case_case_insensitively() -> None:
    dataset = EvaluationDataset(
        dataset_id="dataset-001",
        name="AIRA evaluation dataset",
        description="Baseline research evaluation cases.",
        version="1.0.0",
        cases=[
            evaluation_case(case_id="Case-001"),
        ],
    )

    value = dataset.case_by_id("case-001")

    assert value is not None
    assert value.case_id == "Case-001"
    assert dataset.case_by_id("missing") is None


def test_dataset_rejects_duplicate_case_ids() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "dataset cases must have unique case IDs"
        ),
    ):
        EvaluationDataset(
            dataset_id="dataset-duplicate",
            name="Duplicate dataset",
            description="Contains duplicate case IDs.",
            version="1.0.0",
            cases=[
                evaluation_case(case_id="CASE-001"),
                evaluation_case(case_id="case-001"),
            ],
        )


def test_dataset_requires_at_least_one_case() -> None:
    with pytest.raises(ValidationError):
        EvaluationDataset(
            dataset_id="dataset-empty",
            name="Empty dataset",
            description="No cases.",
            version="1.0.0",
            cases=[],
        )


def test_strict_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ExpectedSource.model_validate(
            {
                "source_id": "source-001",
                "title": "Source",
                "unknown_field": "not allowed",
            }
        )
