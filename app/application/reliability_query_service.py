"""Read-only application reliability aggregation service."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from app.application.evaluation_record import (
    ApplicationEvaluationStatus,
)
from app.application.evaluation_repository import (
    ApplicationEvaluationRepository,
)
from app.application.evaluation_repository_query import (
    ApplicationEvaluationQuery,
)
from app.application.execution_record import (
    ApplicationExecutionStatus,
)
from app.application.execution_repository import (
    ApplicationExecutionRepository,
)
from app.application.execution_repository_query import (
    ApplicationExecutionQuery,
)
from app.application.guardrail_record import (
    ApplicationGuardrailDecision,
)
from app.application.guardrail_repository import (
    ApplicationGuardrailRepository,
)
from app.application.guardrail_repository_query import (
    ApplicationGuardrailQuery,
)
from app.application.job_record import (
    ApplicationJobStatus,
)
from app.application.job_repository import (
    ApplicationJobRepository,
)
from app.application.job_repository_query import (
    ApplicationJobQuery,
)
from app.application.reliability_query import (
    ApplicationReliabilityQuery,
)
from app.application.reliability_query_service_error import (
    ApplicationReliabilityQueryServiceError,
)
from app.application.reliability_snapshot import (
    ApplicationEvaluationReliabilityMetrics,
    ApplicationExecutionReliabilityMetrics,
    ApplicationGuardrailReliabilityMetrics,
    ApplicationJobReliabilityMetrics,
    ApplicationReliabilitySnapshot,
)


class ApplicationReliabilityQueryService:
    """Aggregate application reliability from repositories."""

    def __init__(
        self,
        *,
        execution_repository: ApplicationExecutionRepository,
        evaluation_repository: ApplicationEvaluationRepository,
        guardrail_repository: ApplicationGuardrailRepository,
        job_repository: ApplicationJobRepository,
        clock: Callable[[], datetime],
        snapshot_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._execution_repository = execution_repository
        self._evaluation_repository = evaluation_repository
        self._guardrail_repository = guardrail_repository
        self._job_repository = job_repository
        self._clock = clock
        self._snapshot_id_factory = (
            snapshot_id_factory
            or (lambda: f"reliability-snapshot-{uuid4()}")
        )

    def query(
        self,
        query: ApplicationReliabilityQuery,
    ) -> ApplicationReliabilitySnapshot:
        """Return a read-only application reliability snapshot."""

        return ApplicationReliabilitySnapshot(
            snapshot_id=self._new_snapshot_id(),
            generated_at=self._now(),
            request_id=query.request_id,
            workspace_id=query.workspace_id,
            executions=self._execution_metrics(query),
            evaluations=self._evaluation_metrics(query),
            guardrails=self._guardrail_metrics(query),
            jobs=self._job_metrics(query),
        )

    def _execution_metrics(
        self,
        query: ApplicationReliabilityQuery,
    ) -> ApplicationExecutionReliabilityMetrics:
        """Aggregate execution repository metrics."""

        records = self._execution_repository.list(
            ApplicationExecutionQuery(
                request_id=query.request_id,
                workspace_id=query.workspace_id,
                page_size=200,
            )
        ).items

        counts = Counter(record.status for record in records)
        total = len(records)

        succeeded = counts[
            ApplicationExecutionStatus.SUCCEEDED
        ]
        failed = counts[ApplicationExecutionStatus.FAILED]
        cancelled = counts[
            ApplicationExecutionStatus.CANCELLED
        ]
        timed_out = counts[
            ApplicationExecutionStatus.TIMED_OUT
        ]
        retry_attempts = sum(
            record.attempt_number > 1
            for record in records
        )

        return ApplicationExecutionReliabilityMetrics(
            total=total,
            pending=counts[
                ApplicationExecutionStatus.PENDING
            ],
            queued=counts[
                ApplicationExecutionStatus.QUEUED
            ],
            running=counts[
                ApplicationExecutionStatus.RUNNING
            ],
            succeeded=succeeded,
            failed=failed,
            cancellation_requested=counts[
                ApplicationExecutionStatus
                .CANCELLATION_REQUESTED
            ],
            cancelled=cancelled,
            timed_out=timed_out,
            retry_attempts=retry_attempts,
            success_rate=self._rate(succeeded, total),
            failure_rate=self._rate(failed, total),
            cancellation_rate=self._rate(
                cancelled,
                total,
            ),
            timeout_rate=self._rate(timed_out, total),
            retry_rate=self._rate(retry_attempts, total),
        )

    def _evaluation_metrics(
        self,
        query: ApplicationReliabilityQuery,
    ) -> ApplicationEvaluationReliabilityMetrics:
        """Aggregate evaluation repository metrics."""

        records = self._evaluation_repository.list(
            ApplicationEvaluationQuery(
                request_id=query.request_id,
                workspace_id=query.workspace_id,
                page_size=200,
            )
        ).items

        counts = Counter(record.status for record in records)
        total = len(records)

        passed = counts[
            ApplicationEvaluationStatus.PASSED
        ]
        error = counts[
            ApplicationEvaluationStatus.ERROR
        ]
        blocking_results = sum(
            bool(record.blocking_violations)
            for record in records
        )

        scores = [
            record.overall_score
            for record in records
            if record.overall_score is not None
        ]

        average_score = (
            sum(scores) / len(scores)
            if scores
            else None
        )

        return ApplicationEvaluationReliabilityMetrics(
            total=total,
            passed=passed,
            failed=counts[
                ApplicationEvaluationStatus.FAILED
            ],
            error=error,
            skipped=counts[
                ApplicationEvaluationStatus.SKIPPED
            ],
            blocking_results=blocking_results,
            pass_rate=self._rate(passed, total),
            error_rate=self._rate(error, total),
            blocking_rate=self._rate(
                blocking_results,
                total,
            ),
            average_score=average_score,
        )

    def _guardrail_metrics(
        self,
        query: ApplicationReliabilityQuery,
    ) -> ApplicationGuardrailReliabilityMetrics:
        """Aggregate guardrail repository metrics."""

        records = self._guardrail_repository.list(
            ApplicationGuardrailQuery(
                request_id=query.request_id,
                workspace_id=query.workspace_id,
                page_size=200,
            )
        ).items

        counts = Counter(
            record.decision
            for record in records
        )
        total = len(records)

        allowed = counts[
            ApplicationGuardrailDecision.ALLOWED
        ]
        warned = counts[
            ApplicationGuardrailDecision.WARNED
        ]
        blocked = counts[
            ApplicationGuardrailDecision.BLOCKED
        ]

        total_violations = sum(
            record.total_violation_count
            for record in records
        )
        blocking_violations = sum(
            record.blocking_violation_count
            for record in records
        )
        warning_violations = sum(
            record.warning_violation_count
            for record in records
        )

        return ApplicationGuardrailReliabilityMetrics(
            total=total,
            allowed=allowed,
            warned=warned,
            blocked=blocked,
            total_violations=total_violations,
            blocking_violations=blocking_violations,
            warning_violations=warning_violations,
            allow_rate=self._rate(allowed, total),
            warning_rate=self._rate(warned, total),
            blocking_rate=self._rate(blocked, total),
        )

    def _job_metrics(
        self,
        query: ApplicationReliabilityQuery,
    ) -> ApplicationJobReliabilityMetrics:
        """Aggregate background-job repository metrics."""

        records = self._job_repository.list(
            ApplicationJobQuery(
                request_id=query.request_id,
                workspace_id=query.workspace_id,
                page_size=200,
            )
        ).items

        counts = Counter(record.status for record in records)
        total = len(records)

        succeeded = counts[ApplicationJobStatus.SUCCEEDED]
        failed = counts[ApplicationJobStatus.FAILED]
        cancelled = counts[ApplicationJobStatus.CANCELLED]
        dead_lettered = counts[
            ApplicationJobStatus.DEAD_LETTERED
        ]

        completed = (
            succeeded
            + failed
            + cancelled
            + dead_lettered
        )

        retry_attempts = sum(
            record.attempt_number > 1
            for record in records
        )

        return ApplicationJobReliabilityMetrics(
            total=total,
            pending=counts[ApplicationJobStatus.PENDING],
            scheduled=counts[
                ApplicationJobStatus.SCHEDULED
            ],
            queued=counts[ApplicationJobStatus.QUEUED],
            leased=counts[ApplicationJobStatus.LEASED],
            running=counts[ApplicationJobStatus.RUNNING],
            succeeded=succeeded,
            failed=failed,
            retry_scheduled=counts[
                ApplicationJobStatus.RETRY_SCHEDULED
            ],
            cancellation_requested=counts[
                ApplicationJobStatus
                .CANCELLATION_REQUESTED
            ],
            cancelled=cancelled,
            dead_lettered=dead_lettered,
            retry_attempts=retry_attempts,
            completion_rate=self._rate(completed, total),
            success_rate=self._rate(succeeded, total),
            failure_rate=self._rate(failed, total),
            dead_letter_rate=self._rate(
                dead_lettered,
                total,
            ),
            retry_rate=self._rate(retry_attempts, total),
        )

    @staticmethod
    def _rate(
        numerator: int,
        denominator: int,
    ) -> float:
        """Return a safe normalized rate."""

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def _now(self) -> datetime:
        """Return a validated snapshot timestamp."""

        value = self._clock()

        if value.tzinfo is None:
            raise ApplicationReliabilityQueryServiceError(
                "clock must return timezone-aware datetime"
            )

        return value

    def _new_snapshot_id(self) -> str:
        """Return one nonblank reliability snapshot ID."""

        value = self._snapshot_id_factory()

        if not value.strip():
            raise ApplicationReliabilityQueryServiceError(
                "snapshot ID factory returned blank value"
            )

        return value
