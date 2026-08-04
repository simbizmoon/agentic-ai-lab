"""Tests for deterministic reliability metrics calculation."""

import pytest
from pydantic import ValidationError

from app.guardrails.reliability_metrics import (
    ReliabilityExecutionRecord,
    ReliabilityExecutionStatus,
    ReliabilityMetrics,
    ReliabilityRecoveryStatus,
)
from app.guardrails.reliability_metrics_calculator import (
    ReliabilityMetricsCalculator,
)
from app.guardrails.reliability_metrics_calculator_error import (
    ReliabilityMetricsCalculatorError,
)
from app.guardrails.retry_policy import RetryFailureCategory


def record(
    *,
    execution_id: str,
    status: ReliabilityExecutionStatus,
    duration_seconds: float,
    attempt_count: int = 1,
    guardrail_evaluated: bool = False,
    guardrail_blocked: bool = False,
    recovery_status: ReliabilityRecoveryStatus = (
        ReliabilityRecoveryStatus.NOT_ATTEMPTED
    ),
    failure_category: RetryFailureCategory | None = None,
) -> ReliabilityExecutionRecord:
    """Return one reliability execution record."""

    return ReliabilityExecutionRecord(
        execution_id=execution_id,
        status=status,
        duration_seconds=duration_seconds,
        attempt_count=attempt_count,
        guardrail_evaluated=guardrail_evaluated,
        guardrail_blocked=guardrail_blocked,
        recovery_status=recovery_status,
        failure_category=failure_category,
    )


def calculator() -> ReliabilityMetricsCalculator:
    """Return one deterministic calculator."""

    return ReliabilityMetricsCalculator(
        metrics_id_factory=(
            lambda: "reliability-metrics-001"
        )
    )


def sample_records() -> list[ReliabilityExecutionRecord]:
    """Return representative reliability records."""

    return [
        record(
            execution_id="execution-001",
            status=ReliabilityExecutionStatus.SUCCEEDED,
            duration_seconds=1.0,
            guardrail_evaluated=True,
        ),
        record(
            execution_id="execution-002",
            status=ReliabilityExecutionStatus.SUCCEEDED,
            duration_seconds=2.0,
            attempt_count=2,
            guardrail_evaluated=True,
            recovery_status=(
                ReliabilityRecoveryStatus.SUCCEEDED
            ),
        ),
        record(
            execution_id="execution-003",
            status=ReliabilityExecutionStatus.FAILED,
            duration_seconds=3.0,
            attempt_count=3,
            guardrail_evaluated=True,
            guardrail_blocked=True,
            recovery_status=(
                ReliabilityRecoveryStatus.FAILED
            ),
            failure_category=(
                RetryFailureCategory.TOOL_TEMPORARY
            ),
        ),
        record(
            execution_id="execution-004",
            status=ReliabilityExecutionStatus.TIMED_OUT,
            duration_seconds=10.0,
            attempt_count=2,
            recovery_status=(
                ReliabilityRecoveryStatus.MANUAL_REVIEW
            ),
            failure_category=RetryFailureCategory.TIMEOUT,
        ),
        record(
            execution_id="execution-005",
            status=ReliabilityExecutionStatus.CANCELLED,
            duration_seconds=4.0,
        ),
    ]


def test_calculates_execution_status_metrics() -> None:
    value = calculator().calculate(sample_records())

    assert value.total_executions == 5
    assert value.successful_executions == 2
    assert value.failed_executions == 1
    assert value.cancelled_executions == 1
    assert value.timed_out_executions == 1

    assert value.success_rate == pytest.approx(0.4)
    assert value.failure_rate == pytest.approx(0.2)
    assert value.cancellation_rate == pytest.approx(0.2)
    assert value.timeout_rate == pytest.approx(0.2)


def test_calculates_retry_metrics() -> None:
    value = calculator().calculate(sample_records())

    assert value.retried_executions == 3
    assert value.retry_successes == 1
    assert value.retry_rate == pytest.approx(0.6)
    assert value.retry_success_rate == pytest.approx(
        1 / 3
    )


def test_calculates_recovery_metrics() -> None:
    value = calculator().calculate(sample_records())

    assert value.recovery_attempts == 3
    assert value.recovery_successes == 1
    assert value.manual_review_recoveries == 1
    assert value.recovery_attempt_rate == pytest.approx(0.6)
    assert value.recovery_success_rate == pytest.approx(
        1 / 3
    )


def test_calculates_guardrail_metrics() -> None:
    value = calculator().calculate(sample_records())

    assert value.guardrail_evaluations == 3
    assert value.guardrail_blocks == 1
    assert value.guardrail_block_rate == pytest.approx(
        1 / 3
    )


def test_calculates_duration_metrics() -> None:
    value = calculator().calculate(sample_records())

    assert value.mean_duration_seconds == pytest.approx(4.0)
    assert value.p50_duration_seconds == pytest.approx(3.0)
    assert value.p95_duration_seconds == pytest.approx(10.0)
    assert value.maximum_duration_seconds == pytest.approx(
        10.0
    )


def test_calculates_failure_category_distribution() -> None:
    value = calculator().calculate(sample_records())

    assert value.failure_category_counts == {
        RetryFailureCategory.TOOL_TEMPORARY: 1,
        RetryFailureCategory.TIMEOUT: 1,
    }


def test_empty_records_return_zero_metrics() -> None:
    value = calculator().calculate([])

    assert value.total_executions == 0
    assert value.success_rate == 0.0
    assert value.retry_success_rate == 0.0
    assert value.recovery_success_rate == 0.0
    assert value.guardrail_block_rate == 0.0
    assert value.mean_duration_seconds == 0.0
    assert value.p50_duration_seconds == 0.0
    assert value.p95_duration_seconds == 0.0
    assert value.maximum_duration_seconds == 0.0


def test_duplicate_execution_ids_are_rejected() -> None:
    duplicate = record(
        execution_id="execution-001",
        status=ReliabilityExecutionStatus.SUCCEEDED,
        duration_seconds=1.0,
    )

    with pytest.raises(
        ReliabilityMetricsCalculatorError,
        match="records must have unique execution IDs",
    ):
        calculator().calculate(
            [
                duplicate,
                duplicate,
            ]
        )


def test_guardrail_block_requires_evaluation() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "guardrail_blocked requires "
            "guardrail_evaluated"
        ),
    ):
        record(
            execution_id="execution-invalid",
            status=ReliabilityExecutionStatus.CANCELLED,
            duration_seconds=1.0,
            guardrail_blocked=True,
        )


def test_success_rejects_failure_category() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "successful execution must not include "
            "failure_category"
        ),
    ):
        record(
            execution_id="execution-invalid",
            status=ReliabilityExecutionStatus.SUCCEEDED,
            duration_seconds=1.0,
            failure_category=RetryFailureCategory.INTERNAL,
        )


@pytest.mark.parametrize(
    "status",
    [
        ReliabilityExecutionStatus.FAILED,
        ReliabilityExecutionStatus.TIMED_OUT,
    ],
)
def test_failure_status_requires_category(
    status: ReliabilityExecutionStatus,
) -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "failed or timed-out execution requires "
            "failure_category"
        ),
    ):
        record(
            execution_id="execution-invalid",
            status=status,
            duration_seconds=1.0,
        )


def test_successful_recovery_requires_success_status() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "successful recovery requires successful "
            "execution status"
        ),
    ):
        record(
            execution_id="execution-invalid",
            status=ReliabilityExecutionStatus.FAILED,
            duration_seconds=1.0,
            recovery_status=(
                ReliabilityRecoveryStatus.SUCCEEDED
            ),
            failure_category=RetryFailureCategory.INTERNAL,
        )


def test_metrics_reject_inconsistent_status_counts() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "execution status counts must equal "
            "total_executions"
        ),
    ):
        ReliabilityMetrics(
            metrics_id="metrics-invalid",
            total_executions=2,
            successful_executions=1,
            failed_executions=0,
            cancelled_executions=0,
            timed_out_executions=0,
            retried_executions=0,
            retry_successes=0,
            recovery_attempts=0,
            recovery_successes=0,
            manual_review_recoveries=0,
            guardrail_evaluations=0,
            guardrail_blocks=0,
            success_rate=0.5,
            failure_rate=0.0,
            cancellation_rate=0.0,
            timeout_rate=0.0,
            retry_rate=0.0,
            retry_success_rate=0.0,
            recovery_attempt_rate=0.0,
            recovery_success_rate=0.0,
            guardrail_block_rate=0.0,
            mean_duration_seconds=0.0,
            p50_duration_seconds=0.0,
            p95_duration_seconds=0.0,
            maximum_duration_seconds=0.0,
            summary="Invalid metrics.",
        )


def test_blank_metrics_id_is_rejected() -> None:
    value = ReliabilityMetricsCalculator(
        metrics_id_factory=lambda: " ",
    )

    with pytest.raises(
        ReliabilityMetricsCalculatorError,
        match="metrics_id factory returned blank value",
    ):
        value.calculate([])
