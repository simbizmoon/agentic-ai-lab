"""Deterministic reliability metrics calculation."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Sequence
from uuid import uuid4

from app.guardrails.reliability_metrics import (
    ReliabilityExecutionRecord,
    ReliabilityExecutionStatus,
    ReliabilityMetrics,
    ReliabilityRecoveryStatus,
)
from app.guardrails.reliability_metrics_calculator_error import (
    ReliabilityMetricsCalculatorError,
)


class ReliabilityMetricsCalculator:
    """Aggregate normalized execution reliability records."""

    def __init__(
        self,
        *,
        metrics_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._metrics_id_factory = (
            metrics_id_factory
            or (lambda: f"reliability-metrics-{uuid4()}")
        )

    def calculate(
        self,
        records: Sequence[ReliabilityExecutionRecord],
    ) -> ReliabilityMetrics:
        """Calculate reliability metrics from execution records."""

        self._validate_records(records)

        total = len(records)
        successful = self._status_count(
            records,
            ReliabilityExecutionStatus.SUCCEEDED,
        )
        failed = self._status_count(
            records,
            ReliabilityExecutionStatus.FAILED,
        )
        cancelled = self._status_count(
            records,
            ReliabilityExecutionStatus.CANCELLED,
        )
        timed_out = self._status_count(
            records,
            ReliabilityExecutionStatus.TIMED_OUT,
        )

        retried = sum(record.retried for record in records)
        retry_successes = sum(
            record.retried
            and record.status
            is ReliabilityExecutionStatus.SUCCEEDED
            for record in records
        )

        recovery_attempts = sum(
            record.recovery_attempted
            for record in records
        )
        recovery_successes = sum(
            record.recovery_status
            is ReliabilityRecoveryStatus.SUCCEEDED
            for record in records
        )
        manual_reviews = sum(
            record.recovery_status
            is ReliabilityRecoveryStatus.MANUAL_REVIEW
            for record in records
        )

        guardrail_evaluations = sum(
            record.guardrail_evaluated
            for record in records
        )
        guardrail_blocks = sum(
            record.guardrail_blocked
            for record in records
        )

        durations = sorted(
            record.duration_seconds
            for record in records
        )

        category_counts = Counter(
            record.failure_category
            for record in records
            if record.failure_category is not None
        )

        return ReliabilityMetrics(
            metrics_id=self._new_identifier(),
            total_executions=total,
            successful_executions=successful,
            failed_executions=failed,
            cancelled_executions=cancelled,
            timed_out_executions=timed_out,
            retried_executions=retried,
            retry_successes=retry_successes,
            recovery_attempts=recovery_attempts,
            recovery_successes=recovery_successes,
            manual_review_recoveries=manual_reviews,
            guardrail_evaluations=guardrail_evaluations,
            guardrail_blocks=guardrail_blocks,
            success_rate=self._rate(successful, total),
            failure_rate=self._rate(failed, total),
            cancellation_rate=self._rate(cancelled, total),
            timeout_rate=self._rate(timed_out, total),
            retry_rate=self._rate(retried, total),
            retry_success_rate=self._rate(
                retry_successes,
                retried,
            ),
            recovery_attempt_rate=self._rate(
                recovery_attempts,
                total,
            ),
            recovery_success_rate=self._rate(
                recovery_successes,
                recovery_attempts,
            ),
            guardrail_block_rate=self._rate(
                guardrail_blocks,
                guardrail_evaluations,
            ),
            mean_duration_seconds=self._mean(durations),
            p50_duration_seconds=self._percentile(
                durations,
                percentile=0.50,
            ),
            p95_duration_seconds=self._percentile(
                durations,
                percentile=0.95,
            ),
            maximum_duration_seconds=(
                max(durations)
                if durations
                else 0.0
            ),
            failure_category_counts=dict(category_counts),
            summary=(
                "Reliability metrics calculated for "
                f"{total} executions with "
                f"{successful} successes, "
                f"{failed} failures, "
                f"{cancelled} cancellations, and "
                f"{timed_out} timeouts."
            ),
        )

    @staticmethod
    def _validate_records(
        records: Sequence[ReliabilityExecutionRecord],
    ) -> None:
        """Validate execution-record uniqueness."""

        execution_ids = [
            record.execution_id.strip().casefold()
            for record in records
        ]

        if len(set(execution_ids)) != len(execution_ids):
            raise ReliabilityMetricsCalculatorError(
                "records must have unique execution IDs"
            )

    @staticmethod
    def _status_count(
        records: Sequence[ReliabilityExecutionRecord],
        status: ReliabilityExecutionStatus,
    ) -> int:
        """Count records with one status."""

        return sum(
            record.status is status
            for record in records
        )

    @staticmethod
    def _rate(
        numerator: int,
        denominator: int,
    ) -> float:
        """Return a safe ratio."""

        if denominator == 0:
            return 0.0

        return numerator / denominator

    @staticmethod
    def _mean(values: Sequence[float]) -> float:
        """Return arithmetic mean or zero."""

        if not values:
            return 0.0

        return sum(values) / len(values)

    @staticmethod
    def _percentile(
        values: Sequence[float],
        *,
        percentile: float,
    ) -> float:
        """Return nearest-rank percentile."""

        if not values:
            return 0.0

        rank = max(
            1,
            math.ceil(percentile * len(values)),
        )

        return values[rank - 1]

    def _new_identifier(self) -> str:
        """Generate one nonblank metrics identifier."""

        value = self._metrics_id_factory()

        if not value.strip():
            raise ReliabilityMetricsCalculatorError(
                "metrics_id factory returned blank value"
            )

        return value
