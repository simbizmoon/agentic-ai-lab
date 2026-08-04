"""Deterministic retry and backoff policy evaluation."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from app.guardrails.retry_decision import (
    RetryDecision,
    RetryDecisionType,
    RetryFailureContext,
    RetryStopReason,
)
from app.guardrails.retry_policy import (
    RetryBackoffStrategy,
    RetryJitterStrategy,
    RetryPolicy,
)
from app.guardrails.retry_policy_evaluator_error import (
    RetryPolicyEvaluatorError,
)


class RetryPolicyEvaluator:
    """Determine whether and when a failed execution should retry."""

    def __init__(
        self,
        *,
        policy: RetryPolicy,
        decision_id_factory: Callable[[], str] | None = None,
        random_fraction_factory: Callable[[], float] | None = None,
    ) -> None:
        self._policy = policy
        self._decision_id_factory = (
            decision_id_factory
            or (lambda: f"retry-decision-{uuid4()}")
        )
        self._random_fraction_factory = (
            random_fraction_factory
            or (lambda: 0.5)
        )

    def evaluate(
        self,
        failure: RetryFailureContext,
    ) -> RetryDecision:
        """Return a deterministic retry or stop decision."""

        stop_reason = self._stop_reason(failure)

        if stop_reason is not RetryStopReason.NONE:
            return self._stop_decision(
                failure=failure,
                stop_reason=stop_reason,
            )

        delay, used_retry_after = self._delay(failure)

        return RetryDecision(
            decision_id=self._new_identifier(),
            policy_id=self._policy.policy_id,
            failure_id=failure.failure_id,
            decision=RetryDecisionType.RETRY,
            current_attempt=failure.attempt_number,
            next_attempt=failure.attempt_number + 1,
            delay_seconds=delay,
            used_retry_after=used_retry_after,
            summary=(
                "Retry allowed for attempt "
                f"{failure.attempt_number + 1} after "
                f"{delay:.4f} seconds."
            ),
            metadata={
                "category": failure.category.value,
                "error_code": failure.error_code,
                "backoff_strategy": (
                    self._policy.backoff_strategy.value
                ),
                "jitter_strategy": (
                    self._policy.jitter_strategy.value
                ),
            },
        )

    def _stop_reason(
        self,
        failure: RetryFailureContext,
    ) -> RetryStopReason:
        """Return the first policy reason that stops retrying."""

        if not failure.retryable:
            return RetryStopReason.FAILURE_NOT_RETRYABLE

        if (
            failure.attempt_number
            >= self._policy.maximum_attempts
        ):
            return RetryStopReason.MAXIMUM_ATTEMPTS_REACHED

        if failure.category in self._policy.denied_categories:
            return RetryStopReason.CATEGORY_DENIED

        if (
            self._policy.allowed_categories
            and failure.category
            not in self._policy.allowed_categories
        ):
            return RetryStopReason.CATEGORY_NOT_ALLOWED

        normalized_code = failure.error_code.strip().casefold()
        denied_codes = {
            code.strip().casefold()
            for code in self._policy.denied_error_codes
        }

        if normalized_code in denied_codes:
            return RetryStopReason.ERROR_CODE_DENIED

        allowed_codes = {
            code.strip().casefold()
            for code in self._policy.allowed_error_codes
        }

        if (
            allowed_codes
            and normalized_code not in allowed_codes
        ):
            return RetryStopReason.ERROR_CODE_NOT_ALLOWED

        return RetryStopReason.NONE

    def _delay(
        self,
        failure: RetryFailureContext,
    ) -> tuple[float, bool]:
        """Compute retry delay and Retry-After usage."""

        if (
            self._policy.respect_retry_after
            and failure.retry_after_seconds is not None
        ):
            delay = failure.retry_after_seconds

            if self._policy.retry_after_max_seconds is not None:
                delay = min(
                    delay,
                    self._policy.retry_after_max_seconds,
                )

            return delay, True

        delay = self._base_backoff_delay(
            attempt_number=failure.attempt_number,
        )
        delay = min(
            delay,
            self._policy.maximum_delay_seconds,
        )

        return self._apply_jitter(delay), False

    def _base_backoff_delay(
        self,
        *,
        attempt_number: int,
    ) -> float:
        """Compute delay before jitter and maximum cap."""

        base = self._policy.base_delay_seconds

        if (
            self._policy.backoff_strategy
            is RetryBackoffStrategy.FIXED
        ):
            return base

        if (
            self._policy.backoff_strategy
            is RetryBackoffStrategy.LINEAR
        ):
            return base * attempt_number

        return (
            base
            * self._policy.multiplier
            ** (attempt_number - 1)
        )

    def _apply_jitter(self, delay: float) -> float:
        """Apply configured deterministic jitter."""

        strategy = self._policy.jitter_strategy

        if strategy is RetryJitterStrategy.NONE:
            return delay

        fraction = self._random_fraction_factory()

        if not 0 <= fraction <= 1:
            raise RetryPolicyEvaluatorError(
                "random_fraction_factory must return "
                "a value between 0 and 1"
            )

        if strategy is RetryJitterStrategy.FULL:
            return delay * fraction

        half = delay / 2

        return half + half * fraction

    def _stop_decision(
        self,
        *,
        failure: RetryFailureContext,
        stop_reason: RetryStopReason,
    ) -> RetryDecision:
        """Build one terminal retry decision."""

        return RetryDecision(
            decision_id=self._new_identifier(),
            policy_id=self._policy.policy_id,
            failure_id=failure.failure_id,
            decision=RetryDecisionType.STOP,
            stop_reason=stop_reason,
            current_attempt=failure.attempt_number,
            summary=(
                "Retry stopped because "
                f"{stop_reason.value}."
            ),
            metadata={
                "category": failure.category.value,
                "error_code": failure.error_code,
            },
        )

    def _new_identifier(self) -> str:
        """Generate one nonblank decision identifier."""

        value = self._decision_id_factory()

        if not value.strip():
            raise RetryPolicyEvaluatorError(
                "decision_id factory returned blank value"
            )

        return value
