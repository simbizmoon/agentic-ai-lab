"""Tests for the deterministic evaluation runner."""

import pytest

from app.evals.deterministic_evaluation_runner import (
    DeterministicEvaluationRunner,
)
from app.evals.deterministic_evaluation_runner_error import (
    DeterministicEvaluationRunnerError,
)
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
from app.evals.evaluation_execution_snapshot import (
    ActualClaimArtifact,
    ActualEvidenceArtifact,
    ActualSourceArtifact,
    EvaluationExecutionSnapshot,
)
from app.evals.evaluation_expected_outcome import (
    EvaluationDimension,
    EvaluationExpectedOutcome,
    EvaluationScoreThreshold,
)
from app.evals.evaluation_result import (
    EvaluationFindingStatus,
    EvaluationResultStatus,
)


def case_definition(
    *,
    allow_partial_result: bool = False,
) -> EvaluationCaseDefinition:
    """Return one deterministic evaluation case."""

    return EvaluationCaseDefinition(
        case_id="case-001",
        name="Grounded report evaluation",
        description="Evaluate exact research artifacts.",
        difficulty=EvaluationDifficulty.MEDIUM,
        evaluation_input=EvaluationInput(
            research_question="What does the source support?"
        ),
        expected_outcome=EvaluationExpectedOutcome(
            outcome_id="outcome-001",
            name="Grounded report",
            description="Require grounded artifacts.",
            expected_sources=[
                ExpectedSource(
                    source_id="source-001",
                    title="Expected source",
                )
            ],
            expected_evidence=[
                ExpectedEvidence(
                    evidence_id="evidence-001",
                    source_id="source-001",
                    expected_text="Supporting evidence.",
                )
            ],
            expected_claims=[
                ExpectedClaim(
                    claim_id="claim-001",
                    expected_text="Supported claim.",
                    supporting_evidence_ids=[
                        "evidence-001"
                    ],
                )
            ],
            required_report_elements=[
                "supported conclusion",
            ],
            forbidden_report_elements=[
                "unsupported estimate",
            ],
            score_thresholds=[
                EvaluationScoreThreshold(
                    dimension=(
                        EvaluationDimension
                        .EVIDENCE_GROUNDING
                    ),
                    minimum_score=1.0,
                    required=True,
                )
            ],
            minimum_overall_score=0.75,
            allow_partial_result=allow_partial_result,
        ),
    )


def complete_snapshot() -> EvaluationExecutionSnapshot:
    """Return one complete research execution snapshot."""

    return EvaluationExecutionSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        sources=[
            ActualSourceArtifact(
                source_id="source-001",
                title="Expected source",
            )
        ],
        evidence=[
            ActualEvidenceArtifact(
                evidence_id="evidence-001",
                source_id="source-001",
                text="Supporting evidence.",
            )
        ],
        claims=[
            ActualClaimArtifact(
                claim_id="claim-001",
                text="Supported claim.",
                supporting_evidence_ids=[
                    "evidence-001"
                ],
                citation_ids=["citation-001"],
            )
        ],
        report_text=(
            "The report contains a supported conclusion."
        ),
        tool_call_count=4,
        input_token_count=100,
        output_token_count=50,
        revision_round_count=1,
    )


def runner() -> DeterministicEvaluationRunner:
    """Return one deterministic runner."""

    return DeterministicEvaluationRunner(
        result_id_factory=(
            lambda: "evaluation-result-001"
        ),
        finding_id_factory=(
            lambda index: f"finding-{index:03d}"
        ),
        violation_id_factory=(
            lambda index: f"violation-{index:03d}"
        ),
    )


def evaluate(
    snapshot: EvaluationExecutionSnapshot,
    *,
    case: EvaluationCaseDefinition | None = None,
):
    """Evaluate one snapshot using standard identifiers."""

    return runner().evaluate(
        run_id="run-001",
        dataset_id="dataset-001",
        dataset_version="1.0.0",
        case=case or case_definition(),
        snapshot=snapshot,
    )


def test_runner_passes_complete_execution() -> None:
    value = evaluate(complete_snapshot())

    assert value.status is EvaluationResultStatus.PASSED
    assert value.overall_score == pytest.approx(1.0)
    assert value.violations == []
    assert len(value.findings) == 4
    assert all(
        finding.status
        is EvaluationFindingStatus.MATCHED
        for finding in value.findings
    )
    assert value.metrics.source_count == 1
    assert value.metrics.evidence_count == 1
    assert value.metrics.claim_count == 1
    assert value.metrics.citation_count == 1
    assert value.metrics.total_token_count == 150


def test_runner_fails_missing_required_source() -> None:
    snapshot = complete_snapshot().model_dump(mode="python")
    snapshot["sources"] = []
    snapshot["evidence"] = []
    snapshot["claims"] = []

    value = evaluate(
        EvaluationExecutionSnapshot.model_validate(snapshot)
    )

    assert value.status is EvaluationResultStatus.FAILED
    assert value.blocking_violations
    assert any(
        violation.code == "MISSING_REQUIRED_SOURCE"
        for violation in value.violations
    )


def test_runner_fails_missing_required_evidence() -> None:
    snapshot = EvaluationExecutionSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        sources=[
            ActualSourceArtifact(
                source_id="source-001",
                title="Expected source",
            )
        ],
        report_text="Supported conclusion.",
    )

    value = evaluate(snapshot)

    assert value.status is EvaluationResultStatus.FAILED
    assert any(
        violation.code
        == "MISSING_REQUIRED_EVIDENCE"
        for violation in value.violations
    )


def test_runner_detects_forbidden_report_content() -> None:
    snapshot = complete_snapshot().model_dump(mode="python")
    snapshot["report_text"] = (
        "Supported conclusion with unsupported estimate."
    )

    value = evaluate(
        EvaluationExecutionSnapshot.model_validate(snapshot)
    )

    assert value.status is EvaluationResultStatus.FAILED
    assert any(
        violation.code == "FORBIDDEN_REPORT_ELEMENT"
        for violation in value.violations
    )
    assert any(
        finding.status
        is EvaluationFindingStatus.UNEXPECTED
        for finding in value.findings
    )


def test_runner_fails_missing_required_report_element() -> None:
    snapshot = complete_snapshot().model_dump(mode="python")
    snapshot["report_text"] = "A report without the phrase."

    value = evaluate(
        EvaluationExecutionSnapshot.model_validate(snapshot)
    )

    assert value.status is EvaluationResultStatus.FAILED
    assert any(
        violation.code
        == "MISSING_REQUIRED_REPORT_ELEMENT"
        for violation in value.violations
    )


def test_runner_supports_partial_result() -> None:
    case = case_definition(allow_partial_result=True)
    case_values = case.model_dump(mode="python")
    outcome = case_values["expected_outcome"]
    outcome["expected_sources"][0]["required"] = False
    outcome["expected_evidence"][0]["required"] = False
    outcome["expected_claims"][0]["required"] = False
    outcome["score_thresholds"] = []
    case = EvaluationCaseDefinition.model_validate(case_values)

    snapshot = EvaluationExecutionSnapshot(
        execution_id="execution-001",
        request_id="research-001",
        workspace_id="workspace-001",
        report_text="Supported conclusion.",
    )

    value = evaluate(snapshot, case=case)

    assert value.status is EvaluationResultStatus.PARTIAL
    assert value.blocking_violations == []
    assert value.overall_score is not None
    assert value.overall_score < 0.75


def test_runner_ignores_absent_dimensions() -> None:
    case = EvaluationCaseDefinition(
        case_id="case-report-only",
        name="Report-only evaluation",
        description="Evaluate only report requirements.",
        difficulty=EvaluationDifficulty.EASY,
        evaluation_input=EvaluationInput(
            research_question="Is the report complete?"
        ),
        expected_outcome=EvaluationExpectedOutcome(
            outcome_id="outcome-report-only",
            name="Report-only outcome",
            description="Require one report element.",
            required_report_elements=[
                "required phrase",
            ],
            minimum_overall_score=1.0,
        ),
    )
    snapshot = EvaluationExecutionSnapshot(
        execution_id="execution-report-only",
        request_id="research-001",
        workspace_id="workspace-001",
        report_text="This contains the required phrase.",
    )

    value = evaluate(snapshot, case=case)

    assert value.status is EvaluationResultStatus.PASSED
    assert len(value.dimension_scores) == 1
    assert (
        value.dimension_scores[0].dimension
        is EvaluationDimension.COMPLETENESS
    )


def test_runner_rejects_blank_run_id() -> None:
    with pytest.raises(
        DeterministicEvaluationRunnerError,
        match="run_id must not be blank",
    ):
        runner().evaluate(
            run_id=" ",
            dataset_id="dataset-001",
            dataset_version="1.0.0",
            case=case_definition(),
            snapshot=complete_snapshot(),
        )


def test_runner_rejects_blank_result_id() -> None:
    value = DeterministicEvaluationRunner(
        result_id_factory=lambda: " ",
    )

    with pytest.raises(
        DeterministicEvaluationRunnerError,
        match="result_id factory returned blank value",
    ):
        value.evaluate(
            run_id="run-001",
            dataset_id="dataset-001",
            dataset_version="1.0.0",
            case=case_definition(),
            snapshot=complete_snapshot(),
        )


def test_snapshot_rejects_unknown_evidence_source() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "actual evidence must reference "
            "an actual source"
        ),
    ):
        EvaluationExecutionSnapshot(
            execution_id="execution-invalid",
            request_id="research-001",
            workspace_id="workspace-001",
            evidence=[
                ActualEvidenceArtifact(
                    evidence_id="evidence-001",
                    source_id="source-missing",
                    text="Evidence.",
                )
            ],
        )
