"""Tests for evaluation expected outcome schemas."""

import pytest
from pydantic import ValidationError

from app.evals.evaluation_case_definition import (
    EvaluationCaseDefinition,
    EvaluationInput,
)
from app.evals.evaluation_dataset import (
    EvaluationDifficulty,
    ExpectedClaim,
    ExpectedEvidence,
    ExpectedSource,
)
from app.evals.evaluation_expected_outcome import (
    AcceptableOutcomeVariation,
    EvaluationDimension,
    EvaluationExpectedOutcome,
    EvaluationScoreThreshold,
    ExpectedFailureCondition,
    ExpectedFailureConditionType,
)


def source() -> ExpectedSource:
    """Return one expected source."""

    return ExpectedSource(
        source_id="source-001",
        title="Authoritative source",
        canonical_url="https://example.com/source",
    )


def evidence() -> ExpectedEvidence:
    """Return one expected evidence item."""

    return ExpectedEvidence(
        evidence_id="evidence-001",
        source_id="source-001",
        expected_text="The source supports the claim.",
    )


def claim() -> ExpectedClaim:
    """Return one expected claim."""

    return ExpectedClaim(
        claim_id="claim-001",
        expected_text="The claim is supported.",
        supporting_evidence_ids=["evidence-001"],
    )


def expected_outcome() -> EvaluationExpectedOutcome:
    """Return one complete expected outcome."""

    return EvaluationExpectedOutcome(
        outcome_id="outcome-001",
        name="Grounded research outcome",
        description=(
            "Expect grounded sources, evidence, and claims."
        ),
        expected_sources=[source()],
        expected_evidence=[evidence()],
        expected_claims=[claim()],
        required_report_elements=[
            "Supported conclusion",
            "Source citation",
        ],
        forbidden_report_elements=[
            "Unsupported numerical estimate",
        ],
        acceptable_variations=[
            AcceptableOutcomeVariation(
                variation_id="variation-001",
                target_type="claim",
                target_id="claim-001",
                description=(
                    "Equivalent wording is acceptable."
                ),
                accepted_texts=[
                    "The finding is supported.",
                    "Evidence supports the finding.",
                ],
            )
        ],
        score_thresholds=[
            EvaluationScoreThreshold(
                dimension=(
                    EvaluationDimension
                    .EVIDENCE_GROUNDING
                ),
                minimum_score=0.8,
                required=True,
            ),
            EvaluationScoreThreshold(
                dimension=(
                    EvaluationDimension.CLARITY
                ),
                minimum_score=0.7,
                required=False,
            ),
        ],
        failure_conditions=[
            ExpectedFailureCondition(
                condition_id="failure-001",
                condition_type=(
                    ExpectedFailureConditionType
                    .MISSING_REQUIRED_CLAIM
                ),
                description=(
                    "Required claim must be present."
                ),
                target_id="claim-001",
                blocking=True,
            )
        ],
        minimum_overall_score=0.75,
    )


def test_expected_outcome_returns_required_items() -> None:
    value = expected_outcome()

    assert len(value.required_thresholds) == 1
    assert (
        value.required_thresholds[0].dimension
        is EvaluationDimension.EVIDENCE_GROUNDING
    )
    assert len(value.blocking_failure_conditions) == 1


def test_expected_outcome_rejects_unknown_evidence_source() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "expected evidence must reference "
            "an expected source"
        ),
    ):
        EvaluationExpectedOutcome(
            outcome_id="outcome-invalid-source",
            name="Invalid source",
            description="Evidence references missing source.",
            expected_sources=[source()],
            expected_evidence=[
                ExpectedEvidence(
                    evidence_id="evidence-001",
                    source_id="source-missing",
                    expected_text="Evidence.",
                )
            ],
        )


def test_expected_outcome_rejects_unknown_claim_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "expected claim must reference "
            "expected evidence"
        ),
    ):
        EvaluationExpectedOutcome(
            outcome_id="outcome-invalid-evidence",
            name="Invalid evidence",
            description="Claim references missing evidence.",
            expected_sources=[source()],
            expected_evidence=[evidence()],
            expected_claims=[
                ExpectedClaim(
                    claim_id="claim-001",
                    expected_text="Claim.",
                    supporting_evidence_ids=[
                        "evidence-missing"
                    ],
                )
            ],
        )


def test_variation_rejects_unknown_artifact_target() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "acceptable variation must reference "
            "an expected artifact"
        ),
    ):
        EvaluationExpectedOutcome(
            outcome_id="outcome-invalid-variation",
            name="Invalid variation",
            description="Variation target is missing.",
            expected_sources=[source()],
            acceptable_variations=[
                AcceptableOutcomeVariation(
                    variation_id="variation-001",
                    target_type="source",
                    target_id="source-missing",
                    description="Alternative source title.",
                )
            ],
        )


def test_failure_condition_requires_artifact_target() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "artifact-related failure condition "
            "must include target_id"
        ),
    ):
        ExpectedFailureCondition(
            condition_id="failure-invalid",
            condition_type=(
                ExpectedFailureConditionType
                .MISSING_REQUIRED_SOURCE
            ),
            description="Required source is missing.",
        )


def test_outcome_rejects_unknown_failure_target() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "failure condition must reference "
            "an expected artifact"
        ),
    ):
        EvaluationExpectedOutcome(
            outcome_id="outcome-invalid-failure",
            name="Invalid failure target",
            description="Failure target is missing.",
            expected_sources=[source()],
            failure_conditions=[
                ExpectedFailureCondition(
                    condition_id="failure-001",
                    condition_type=(
                        ExpectedFailureConditionType
                        .MISSING_REQUIRED_SOURCE
                    ),
                    description="Required source is absent.",
                    target_id="source-missing",
                )
            ],
        )


def test_outcome_rejects_duplicate_dimensions() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "score thresholds must have unique dimensions"
        ),
    ):
        EvaluationExpectedOutcome(
            outcome_id="outcome-duplicate-scores",
            name="Duplicate score dimensions",
            description="Score dimensions must be unique.",
            score_thresholds=[
                EvaluationScoreThreshold(
                    dimension=EvaluationDimension.CLARITY,
                    minimum_score=0.7,
                ),
                EvaluationScoreThreshold(
                    dimension=EvaluationDimension.CLARITY,
                    minimum_score=0.8,
                ),
            ],
        )


def test_case_definition_connects_input_and_outcome() -> None:
    value = EvaluationCaseDefinition(
        case_id="case-001",
        name="Grounding evaluation case",
        description="Evaluate grounded research output.",
        difficulty=EvaluationDifficulty.MEDIUM,
        evaluation_input=EvaluationInput(
            research_question=(
                "What finding does the source support?"
            ),
            context=[
                "Use authoritative sources.",
            ],
            constraints=[
                "Do not invent numerical estimates.",
            ],
        ),
        expected_outcome=expected_outcome(),
        tags=[
            "grounding",
            "baseline",
        ],
    )

    assert value.case_id == "case-001"
    assert (
        value.expected_outcome.outcome_id
        == "outcome-001"
    )
    assert value.evaluation_input.constraints == [
        "Do not invent numerical estimates."
    ]


def test_evaluation_input_rejects_duplicate_context() -> None:
    with pytest.raises(
        ValidationError,
        match="context must not contain duplicates",
    ):
        EvaluationInput(
            research_question="What is supported?",
            context=[
                "Use authoritative sources.",
                "use authoritative sources.",
            ],
        )


def test_case_definition_rejects_duplicate_tags() -> None:
    with pytest.raises(
        ValidationError,
        match="tags must not contain duplicates",
    ):
        EvaluationCaseDefinition(
            case_id="case-duplicate-tags",
            name="Duplicate tags",
            description="Tags must be unique.",
            difficulty=EvaluationDifficulty.EASY,
            evaluation_input=EvaluationInput(
                research_question="What is supported?"
            ),
            expected_outcome=expected_outcome(),
            tags=[
                "Grounding",
                "grounding",
            ],
        )
