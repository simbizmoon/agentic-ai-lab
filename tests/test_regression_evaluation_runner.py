"""Tests for baseline-to-current regression evaluation."""

import pytest

from app.evals.evaluation_expected_outcome import (
    EvaluationDimension,
)
from app.evals.evaluation_result import (
    EvaluationCaseResult,
    EvaluationDimensionScore,
    EvaluationExecutionMetrics,
    EvaluationResultStatus,
    EvaluationViolation,
    EvaluationViolationSeverity,
)
from app.evals.regression_evaluation_runner import (
    RegressionChangeType,
    RegressionEvaluationRunner,
)
from app.evals.regression_evaluation_runner_error import (
    RegressionEvaluationRunnerError,
)


def dimension_score(
    *,
    dimension: EvaluationDimension,
    score: float,
) -> EvaluationDimensionScore:
    """Return one evaluation dimension score."""

    return EvaluationDimensionScore(
        dimension=dimension,
        score=score,
        threshold=0.7,
        required=True,
        passed=score >= 0.7,
        rationale="Deterministic evaluation score.",
        evaluator="test-evaluator",
    )


def blocking_violation(
    *,
    violation_id: str = "violation-001",
    code: str = "BLOCKING_ERROR",
) -> EvaluationViolation:
    """Return one blocking evaluation violation."""

    return EvaluationViolation(
        violation_id=violation_id,
        code=code,
        severity=EvaluationViolationSeverity.ERROR,
        message="A blocking evaluation violation occurred.",
        blocking=True,
    )


def evaluation_result(
    *,
    result_id: str,
    status: EvaluationResultStatus = (
        EvaluationResultStatus.PASSED
    ),
    overall_score: float = 0.9,
    correctness_score: float = 0.9,
    clarity_score: float = 0.9,
    violations: list[EvaluationViolation] | None = None,
    token_count: int = 100,
    tool_call_count: int = 4,
) -> EvaluationCaseResult:
    """Return one deterministic evaluation result."""

    input_tokens = token_count // 2
    output_tokens = token_count - input_tokens

    return EvaluationCaseResult(
        result_id=result_id,
        run_id=f"run-{result_id}",
        dataset_id="dataset-001",
        dataset_version="1.0.0",
        case_id="case-001",
        request_id="research-001",
        workspace_id="workspace-001",
        execution_id=f"execution-{result_id}",
        status=status,
        overall_score=overall_score,
        dimension_scores=[
            dimension_score(
                dimension=EvaluationDimension.CORRECTNESS,
                score=correctness_score,
            ),
            dimension_score(
                dimension=EvaluationDimension.CLARITY,
                score=clarity_score,
            ),
        ],
        violations=violations or [],
        metrics=EvaluationExecutionMetrics(
            tool_call_count=tool_call_count,
            input_token_count=input_tokens,
            output_token_count=output_tokens,
        ),
        summary="Evaluation completed.",
    )


def runner(
    *,
    overall_score_tolerance: float = 0.02,
    dimension_score_tolerance: float = 0.05,
) -> RegressionEvaluationRunner:
    """Return one deterministic regression runner."""

    return RegressionEvaluationRunner(
        overall_score_tolerance=overall_score_tolerance,
        dimension_score_tolerance=(
            dimension_score_tolerance
        ),
        comparison_id_factory=(
            lambda: "comparison-001"
        ),
        change_id_factory=(
            lambda index: f"change-{index:03d}"
        ),
    )


def test_identical_results_have_no_regression() -> None:
    baseline = evaluation_result(
        result_id="baseline"
    )
    current = evaluation_result(
        result_id="current"
    )

    value = runner().compare(
        baseline=baseline,
        current=current,
    )

    assert value.passed is True
    assert value.regression_detected is False
    assert value.regression_count == 0


def test_passed_to_failed_is_regression() -> None:
    baseline = evaluation_result(
        result_id="baseline"
    )
    current = evaluation_result(
        result_id="current",
        status=EvaluationResultStatus.FAILED,
        overall_score=0.6,
        correctness_score=0.6,
        violations=[
            blocking_violation(),
        ],
    )

    value = runner().compare(
        baseline=baseline,
        current=current,
    )

    assert value.regression_detected is True
    assert any(
        change.change_type
        is RegressionChangeType.STATUS_REGRESSION
        for change in value.changes
    )
    assert any(
        change.change_type
        is RegressionChangeType.NEW_BLOCKING_VIOLATION
        for change in value.changes
    )


def test_overall_score_drop_is_regression() -> None:
    value = runner().compare(
        baseline=evaluation_result(
            result_id="baseline",
            overall_score=0.9,
        ),
        current=evaluation_result(
            result_id="current",
            overall_score=0.8,
        ),
    )

    assert any(
        change.change_type
        is RegressionChangeType.OVERALL_SCORE_REGRESSION
        for change in value.changes
    )


def test_small_score_drop_is_tolerated() -> None:
    value = runner(
        overall_score_tolerance=0.05
    ).compare(
        baseline=evaluation_result(
            result_id="baseline",
            overall_score=0.90,
        ),
        current=evaluation_result(
            result_id="current",
            overall_score=0.87,
        ),
    )

    assert not any(
        change.change_type
        is RegressionChangeType.OVERALL_SCORE_REGRESSION
        for change in value.changes
    )


def test_dimension_drop_is_regression() -> None:
    value = runner().compare(
        baseline=evaluation_result(
            result_id="baseline",
            correctness_score=0.9,
        ),
        current=evaluation_result(
            result_id="current",
            correctness_score=0.7,
        ),
    )

    change = next(
        change
        for change in value.changes
        if change.change_type
        is RegressionChangeType.DIMENSION_REGRESSION
    )

    assert change.dimension is (
        EvaluationDimension.CORRECTNESS
    )


def test_resolved_violation_is_improvement() -> None:
    baseline = evaluation_result(
        result_id="baseline",
        status=EvaluationResultStatus.FAILED,
        overall_score=0.6,
        correctness_score=0.6,
        violations=[
            blocking_violation(
                code="UNSUPPORTED_CLAIM"
            )
        ],
    )
    current = evaluation_result(
        result_id="current",
    )

    value = runner().compare(
        baseline=baseline,
        current=current,
    )

    assert value.improvement_count >= 1
    assert any(
        change.change_type
        is RegressionChangeType
        .RESOLVED_BLOCKING_VIOLATION
        for change in value.changes
    )


def test_token_increase_is_recorded_but_not_quality_regression() -> None:
    value = runner().compare(
        baseline=evaluation_result(
            result_id="baseline",
            token_count=100,
        ),
        current=evaluation_result(
            result_id="current",
            token_count=150,
        ),
    )

    change = next(
        change
        for change in value.changes
        if change.change_type
        is RegressionChangeType.TOKEN_USAGE_INCREASE
    )

    assert change.regression is False
    assert value.regression_detected is False


def test_tool_call_decrease_is_improvement() -> None:
    value = runner().compare(
        baseline=evaluation_result(
            result_id="baseline",
            tool_call_count=8,
        ),
        current=evaluation_result(
            result_id="current",
            tool_call_count=4,
        ),
    )

    assert any(
        change.change_type
        is RegressionChangeType.TOOL_CALL_DECREASE
        for change in value.changes
    )


def test_runner_requires_same_case() -> None:
    baseline = evaluation_result(
        result_id="baseline"
    )
    current_values = evaluation_result(
        result_id="current"
    ).model_dump(mode="python")
    current_values["case_id"] = "case-other"
    current = EvaluationCaseResult.model_validate(
        current_values
    )

    with pytest.raises(
        RegressionEvaluationRunnerError,
        match=(
            "baseline and current results must share case_id"
        ),
    ):
        runner().compare(
            baseline=baseline,
            current=current,
        )


def test_runner_rejects_negative_tolerance() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "overall_score_tolerance must be nonnegative"
        ),
    ):
        RegressionEvaluationRunner(
            overall_score_tolerance=-0.1
        )


def test_runner_rejects_blank_comparison_id() -> None:
    value = RegressionEvaluationRunner(
        comparison_id_factory=lambda: " ",
    )

    with pytest.raises(
        RegressionEvaluationRunnerError,
        match=(
            "comparison_id factory returned blank value"
        ),
    ):
        value.compare(
            baseline=evaluation_result(
                result_id="baseline"
            ),
            current=evaluation_result(
                result_id="current"
            ),
        )
