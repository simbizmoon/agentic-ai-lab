"""Tests for research evaluation result schemas."""

import pytest
from pydantic import ValidationError

from app.evals.evaluation_expected_outcome import (
    EvaluationDimension,
)
from app.evals.evaluation_result import (
    EvaluationArtifactFinding,
    EvaluationArtifactType,
    EvaluationCaseResult,
    EvaluationDimensionScore,
    EvaluationError,
    EvaluationExecutionMetrics,
    EvaluationFindingStatus,
    EvaluationResultStatus,
    EvaluationViolation,
    EvaluationViolationSeverity,
)


def dimension_score(
    *,
    dimension: EvaluationDimension = (
        EvaluationDimension.CORRECTNESS
    ),
    score: float = 0.9,
    threshold: float = 0.8,
    required: bool = True,
) -> EvaluationDimensionScore:
    """Return one dimension score."""

    return EvaluationDimensionScore(
        dimension=dimension,
        score=score,
        threshold=threshold,
        required=required,
        passed=score >= threshold,
        rationale="The output satisfies the rubric.",
        evaluator="deterministic-evaluator",
    )


def matched_finding() -> EvaluationArtifactFinding:
    """Return one matched artifact finding."""

    return EvaluationArtifactFinding(
        finding_id="finding-001",
        artifact_type=EvaluationArtifactType.CLAIM,
        expected_artifact_id="claim-expected-001",
        actual_artifact_id="claim-actual-001",
        status=EvaluationFindingStatus.MATCHED,
        score=1.0,
        explanation="The expected claim was found.",
        evidence=[
            "Equivalent normalized claim text.",
        ],
    )


def blocking_violation() -> EvaluationViolation:
    """Return one blocking violation."""

    return EvaluationViolation(
        violation_id="violation-001",
        code="UNSUPPORTED_CLAIM",
        severity=EvaluationViolationSeverity.ERROR,
        message="A required claim is unsupported.",
        blocking=True,
        dimension=EvaluationDimension.CLAIM_SUPPORT,
        artifact_type=EvaluationArtifactType.CLAIM,
        artifact_id="claim-actual-001",
        remediation="Add supporting evidence.",
    )


def passed_result() -> EvaluationCaseResult:
    """Return one passing evaluation result."""

    return EvaluationCaseResult(
        result_id="evaluation-result-001",
        run_id="evaluation-run-001",
        dataset_id="dataset-001",
        dataset_version="1.0.0",
        case_id="case-001",
        request_id="research-001",
        workspace_id="workspace-001",
        execution_id="execution-001",
        status=EvaluationResultStatus.PASSED,
        overall_score=0.9,
        dimension_scores=[
            dimension_score(),
            dimension_score(
                dimension=EvaluationDimension.CLARITY,
                score=0.85,
                threshold=0.7,
            ),
        ],
        findings=[
            matched_finding(),
        ],
        metrics=EvaluationExecutionMetrics(
            duration_ms=120,
            evaluator_call_count=2,
            tool_call_count=3,
            input_token_count=100,
            output_token_count=50,
            source_count=4,
            evidence_count=6,
            claim_count=3,
            citation_count=3,
        ),
        summary="The evaluation passed.",
    )


def test_dimension_score_requires_threshold_consistency() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "passed must match score threshold result"
        ),
    ):
        EvaluationDimensionScore(
            dimension=EvaluationDimension.CORRECTNESS,
            score=0.5,
            threshold=0.8,
            required=True,
            passed=True,
            rationale="Incorrect pass state.",
            evaluator="test-evaluator",
        )


def test_matched_finding_requires_actual_artifact() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "matched finding must include "
            "actual_artifact_id"
        ),
    ):
        EvaluationArtifactFinding(
            finding_id="finding-invalid",
            artifact_type=EvaluationArtifactType.CLAIM,
            expected_artifact_id="claim-expected-001",
            status=EvaluationFindingStatus.MATCHED,
            explanation="Claim matched.",
        )


def test_missing_finding_requires_expected_artifact() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "missing finding must include "
            "expected_artifact_id"
        ),
    ):
        EvaluationArtifactFinding(
            finding_id="finding-invalid",
            artifact_type=EvaluationArtifactType.EVIDENCE,
            status=EvaluationFindingStatus.MISSING,
            explanation="Evidence is missing.",
        )


def test_passed_result_exposes_properties() -> None:
    value = passed_result()

    assert value.passed is True
    assert value.blocking_violations == []
    assert value.failed_required_dimensions == []
    assert value.metrics.total_token_count == 150


def test_passed_result_rejects_blocking_violation() -> None:
    values = passed_result().model_dump(mode="python")
    values["violations"] = [
        blocking_violation(),
    ]

    with pytest.raises(
        ValidationError,
        match=(
            "passed result must not contain "
            "blocking violations"
        ),
    ):
        EvaluationCaseResult.model_validate(values)


def test_passed_result_rejects_failed_required_score() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "passed result must not contain failed "
            "required dimension scores"
        ),
    ):
        EvaluationCaseResult(
            result_id="evaluation-result-invalid",
            run_id="evaluation-run-001",
            dataset_id="dataset-001",
            dataset_version="1.0.0",
            case_id="case-001",
            request_id="research-001",
            workspace_id="workspace-001",
            execution_id="execution-001",
            status=EvaluationResultStatus.PASSED,
            overall_score=0.7,
            dimension_scores=[
                dimension_score(
                    score=0.5,
                    threshold=0.8,
                    required=True,
                )
            ],
            summary="Invalid passing result.",
        )


def test_failed_result_accepts_blocking_violation() -> None:
    value = EvaluationCaseResult(
        result_id="evaluation-result-failed",
        run_id="evaluation-run-001",
        dataset_id="dataset-001",
        dataset_version="1.0.0",
        case_id="case-001",
        request_id="research-001",
        workspace_id="workspace-001",
        execution_id="execution-001",
        status=EvaluationResultStatus.FAILED,
        overall_score=0.4,
        dimension_scores=[
            dimension_score(
                score=0.4,
                threshold=0.8,
            )
        ],
        violations=[
            blocking_violation(),
        ],
        summary="The evaluation failed.",
    )

    assert value.passed is False
    assert len(value.blocking_violations) == 1
    assert len(value.failed_required_dimensions) == 1


def test_scored_result_requires_overall_score() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "scored result must include overall_score"
        ),
    ):
        EvaluationCaseResult(
            result_id="evaluation-result-invalid",
            run_id="evaluation-run-001",
            dataset_id="dataset-001",
            dataset_version="1.0.0",
            case_id="case-001",
            request_id="research-001",
            workspace_id="workspace-001",
            execution_id="execution-001",
            status=EvaluationResultStatus.PARTIAL,
            summary="Partial evaluation result.",
        )


def test_error_result_requires_structured_error() -> None:
    with pytest.raises(
        ValidationError,
        match="error result must include error",
    ):
        EvaluationCaseResult(
            result_id="evaluation-result-error",
            run_id="evaluation-run-001",
            dataset_id="dataset-001",
            dataset_version="1.0.0",
            case_id="case-001",
            request_id="research-001",
            workspace_id="workspace-001",
            execution_id="execution-001",
            status=EvaluationResultStatus.ERROR,
            summary="Evaluation failed unexpectedly.",
        )


def test_error_result_accepts_structured_error() -> None:
    value = EvaluationCaseResult(
        result_id="evaluation-result-error",
        run_id="evaluation-run-001",
        dataset_id="dataset-001",
        dataset_version="1.0.0",
        case_id="case-001",
        request_id="research-001",
        workspace_id="workspace-001",
        execution_id="execution-001",
        status=EvaluationResultStatus.ERROR,
        summary="Evaluation failed unexpectedly.",
        error=EvaluationError(
            code="EVALUATOR_TIMEOUT",
            message="The evaluator timed out.",
            retryable=True,
            stage="claim_support",
        ),
    )

    assert value.error is not None
    assert value.error.retryable is True


def test_skipped_result_rejects_score() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "skipped result must not include "
            "overall_score"
        ),
    ):
        EvaluationCaseResult(
            result_id="evaluation-result-skipped",
            run_id="evaluation-run-001",
            dataset_id="dataset-001",
            dataset_version="1.0.0",
            case_id="case-001",
            request_id="research-001",
            workspace_id="workspace-001",
            execution_id="execution-001",
            status=EvaluationResultStatus.SKIPPED,
            overall_score=1.0,
            summary="Evaluation was skipped.",
        )


def test_result_rejects_duplicate_dimensions() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "dimension score dimensions must not "
            "contain duplicates"
        ),
    ):
        EvaluationCaseResult(
            result_id="evaluation-result-duplicate",
            run_id="evaluation-run-001",
            dataset_id="dataset-001",
            dataset_version="1.0.0",
            case_id="case-001",
            request_id="research-001",
            workspace_id="workspace-001",
            execution_id="execution-001",
            status=EvaluationResultStatus.FAILED,
            overall_score=0.5,
            dimension_scores=[
                dimension_score(),
                dimension_score(),
            ],
            summary="Duplicate dimensions.",
        )


def test_result_rejects_duplicate_violation_ids() -> None:
    violation = blocking_violation()

    with pytest.raises(
        ValidationError,
        match=(
            "violation IDs must not contain duplicates"
        ),
    ):
        EvaluationCaseResult(
            result_id="evaluation-result-duplicate",
            run_id="evaluation-run-001",
            dataset_id="dataset-001",
            dataset_version="1.0.0",
            case_id="case-001",
            request_id="research-001",
            workspace_id="workspace-001",
            execution_id="execution-001",
            status=EvaluationResultStatus.FAILED,
            overall_score=0.4,
            violations=[
                violation,
                violation,
            ],
            summary="Duplicate violations.",
        )
