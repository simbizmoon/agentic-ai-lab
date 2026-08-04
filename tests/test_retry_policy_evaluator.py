"""Tests for deterministic retry and backoff policies."""

import pytest
from pydantic import ValidationError

from app.guardrails.retry_decision import (
    RetryDecision,
    RetryDecisionType,
    RetryFailureContext,
    RetryStopReason,
)
from app.guardrails.retry_policy import (
    RetryBackoffStrategy,
    RetryFailureCategory,
    RetryJitterStrategy,
    RetryPolicy,
    default_retry_policy,
)
from app.guardrails.retry_policy_evaluator import (
    RetryPolicyEvaluator,
)
from app.guardrails.retry_policy_evaluator_error import (
    RetryPolicyEvaluatorError,
)


def policy(
    *,
    maximum_attempts: int = 3,
    base_delay_seconds: float = 1.0,
    maximum_delay_seconds: float = 30.0,
    backoff_strategy: RetryBackoffStrategy = (
        RetryBackoffStrategy.EXPONENTIAL
    ),
    multiplier: float = 2.0,
    jitter_strategy: RetryJitterStrategy = (
        RetryJitterStrategy.NONE
    ),
    respect_retry_after: bool = True,
) -> RetryPolicy:
    """Return one test retry policy."""

    return RetryPolicy(
        policy_id="retry-policy-001",
        name="Test retry policy",
        description="Retry temporary failures.",
        version="1.0.0",
        maximum_attempts=maximum_attempts,
        base_delay_seconds=base_delay_seconds,
        maximum_delay_seconds=maximum_delay_seconds,
        backoff_strategy=backoff_strategy,
        multiplier=multiplier,
        jitter_strategy=jitter_strategy,
        allowed_categories=[
            RetryFailureCategory.TIMEOUT,
            RetryFailureCategory.RATE_LIMIT,
            RetryFailureCategory.NETWORK,
        ],
        denied_categories=[
            RetryFailureCategory.VALIDATION,
            RetryFailureCategory.PERMISSION,
        ],
        respect_retry_after=respect_retry_after,
        retry_after_max_seconds=(
            120.0
            if respect_retry_after
            else None
        ),
    )


def failure(
    *,
    category: RetryFailureCategory = (
        RetryFailureCategory.TIMEOUT
    ),
    error_code: str = "TIMEOUT",
    retryable: bool = True,
    attempt_number: int = 1,
    retry_after_seconds: float | None = None,
) -> RetryFailureContext:
    """Return one normalized failure context."""

    return RetryFailureContext(
        failure_id="failure-001",
        category=category,
        error_code=error_code,
        message="The operation failed.",
        retryable=retryable,
        attempt_number=attempt_number,
        retry_after_seconds=retry_after_seconds,
    )


def evaluator(
    retry_policy: RetryPolicy | None = None,
    *,
    random_fraction: float = 0.5,
) -> RetryPolicyEvaluator:
    """Return one deterministic retry evaluator."""

    return RetryPolicyEvaluator(
        policy=retry_policy or policy(),
        decision_id_factory=(
            lambda: "retry-decision-001"
        ),
        random_fraction_factory=(
            lambda: random_fraction
        ),
    )


def test_retryable_failure_is_retried() -> None:
    value = evaluator().evaluate(failure())

    assert value.decision is RetryDecisionType.RETRY
    assert value.stop_reason is RetryStopReason.NONE
    assert value.current_attempt == 1
    assert value.next_attempt == 2
    assert value.delay_seconds == pytest.approx(1.0)
    assert value.used_retry_after is False


def test_nonretryable_failure_stops() -> None:
    value = evaluator().evaluate(
        failure(retryable=False)
    )

    assert value.decision is RetryDecisionType.STOP
    assert value.stop_reason is (
        RetryStopReason.FAILURE_NOT_RETRYABLE
    )


def test_maximum_attempts_stop_retry() -> None:
    value = evaluator().evaluate(
        failure(attempt_number=3)
    )

    assert value.stop_reason is (
        RetryStopReason.MAXIMUM_ATTEMPTS_REACHED
    )


def test_denied_category_stops_retry() -> None:
    value = evaluator().evaluate(
        failure(
            category=RetryFailureCategory.VALIDATION
        )
    )

    assert value.stop_reason is (
        RetryStopReason.CATEGORY_DENIED
    )


def test_unlisted_category_stops_retry() -> None:
    value = evaluator().evaluate(
        failure(
            category=RetryFailureCategory.INTERNAL
        )
    )

    assert value.stop_reason is (
        RetryStopReason.CATEGORY_NOT_ALLOWED
    )


def test_exponential_backoff() -> None:
    value = evaluator().evaluate(
        failure(attempt_number=2)
    )

    assert value.delay_seconds == pytest.approx(2.0)
    assert value.next_attempt == 3


def test_fixed_backoff() -> None:
    value = evaluator(
        policy(
            backoff_strategy=RetryBackoffStrategy.FIXED,
            multiplier=2.0,
        )
    ).evaluate(
        failure(attempt_number=2)
    )

    assert value.delay_seconds == pytest.approx(1.0)


def test_linear_backoff() -> None:
    value = evaluator(
        policy(
            backoff_strategy=RetryBackoffStrategy.LINEAR,
            multiplier=2.0,
        )
    ).evaluate(
        failure(attempt_number=2)
    )

    assert value.delay_seconds == pytest.approx(2.0)


def test_backoff_is_capped() -> None:
    retry_policy = policy(
        maximum_attempts=6,
        base_delay_seconds=10.0,
        maximum_delay_seconds=25.0,
    )

    value = evaluator(retry_policy).evaluate(
        failure(attempt_number=4)
    )

    assert value.delay_seconds == pytest.approx(25.0)


def test_retry_after_is_preferred() -> None:
    value = evaluator().evaluate(
        failure(retry_after_seconds=15.0)
    )

    assert value.delay_seconds == pytest.approx(15.0)
    assert value.used_retry_after is True


def test_retry_after_is_capped_separately() -> None:
    value = evaluator().evaluate(
        failure(retry_after_seconds=300.0)
    )

    assert value.delay_seconds == pytest.approx(120.0)


def test_retry_after_can_be_ignored() -> None:
    retry_policy = policy(
        respect_retry_after=False
    )

    value = evaluator(retry_policy).evaluate(
        failure(retry_after_seconds=15.0)
    )

    assert value.delay_seconds == pytest.approx(1.0)
    assert value.used_retry_after is False


def test_full_jitter() -> None:
    retry_policy = policy(
        jitter_strategy=RetryJitterStrategy.FULL
    )

    value = evaluator(
        retry_policy,
        random_fraction=0.25,
    ).evaluate(failure())

    assert value.delay_seconds == pytest.approx(0.25)


def test_equal_jitter() -> None:
    retry_policy = policy(
        jitter_strategy=RetryJitterStrategy.EQUAL
    )

    value = evaluator(
        retry_policy,
        random_fraction=0.5,
    ).evaluate(failure())

    assert value.delay_seconds == pytest.approx(0.75)


def test_invalid_jitter_fraction_fails() -> None:
    retry_policy = policy(
        jitter_strategy=RetryJitterStrategy.FULL
    )

    with pytest.raises(
        RetryPolicyEvaluatorError,
        match=(
            "random_fraction_factory must return "
            "a value between 0 and 1"
        ),
    ):
        evaluator(
            retry_policy,
            random_fraction=1.5,
        ).evaluate(failure())


def test_denied_error_code_stops_retry() -> None:
    retry_policy = policy().model_copy(
        update={
            "denied_error_codes": ["TIMEOUT"],
        }
    )

    value = evaluator(retry_policy).evaluate(
        failure(error_code="timeout")
    )

    assert value.stop_reason is (
        RetryStopReason.ERROR_CODE_DENIED
    )


def test_allowed_error_code_filter_stops_unknown_code() -> None:
    retry_policy = policy().model_copy(
        update={
            "allowed_error_codes": [
                "TEMPORARY_TIMEOUT",
            ],
        }
    )

    value = evaluator(retry_policy).evaluate(
        failure(error_code="OTHER_TIMEOUT")
    )

    assert value.stop_reason is (
        RetryStopReason.ERROR_CODE_NOT_ALLOWED
    )


def test_default_policy_allows_temporary_categories() -> None:
    value = default_retry_policy()

    assert RetryFailureCategory.TIMEOUT in (
        value.allowed_categories
    )
    assert RetryFailureCategory.PERMISSION in (
        value.denied_categories
    )


def test_policy_rejects_invalid_delay_range() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "maximum_delay_seconds must be greater than "
            "or equal to base_delay_seconds"
        ),
    ):
        policy(
            base_delay_seconds=10.0,
            maximum_delay_seconds=5.0,
        )


def test_policy_rejects_overlapping_categories() -> None:
    values = policy().model_dump(mode="python")
    values["denied_categories"].append(
        RetryFailureCategory.TIMEOUT
    )

    with pytest.raises(
        ValidationError,
        match=(
            "allowed_categories and denied_categories "
            "must not overlap"
        ),
    ):
        RetryPolicy.model_validate(values)


def test_retry_decision_requires_next_attempt() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "retry decision must include next_attempt"
        ),
    ):
        RetryDecision(
            decision_id="decision-invalid",
            policy_id="policy-001",
            failure_id="failure-001",
            decision=RetryDecisionType.RETRY,
            current_attempt=1,
            delay_seconds=1.0,
            summary="Invalid retry decision.",
        )


def test_evaluator_rejects_blank_decision_id() -> None:
    value = RetryPolicyEvaluator(
        policy=policy(),
        decision_id_factory=lambda: " ",
    )

    with pytest.raises(
        RetryPolicyEvaluatorError,
        match=(
            "decision_id factory returned blank value"
        ),
    ):
        value.evaluate(failure())
