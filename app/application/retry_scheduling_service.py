"""Application service for background-job retry scheduling."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import uuid4

from app.application.job_record import (
    ApplicationJobRecord,
    ApplicationJobStatus,
    ApplicationJobType,
)
from app.application.job_repository import (
    ApplicationJobRepository,
)
from app.application.job_repository_query import (
    ApplicationJobQuery,
)
from app.application.retry_scheduling_result import (
    ApplicationRetrySchedulingResult,
    ApplicationRetrySchedulingStatus,
)
from app.application.retry_scheduling_service_error import (
    ApplicationJobNotRetryableError,
    ApplicationRetryAlreadyScheduledError,
    ApplicationRetrySchedulingServiceError,
)
from app.guardrails.retry_decision import (
    RetryDecisionType,
    RetryFailureContext,
)
from app.guardrails.retry_policy_evaluator import (
    RetryPolicyEvaluator,
)


class ApplicationRetrySchedulingService:
    """Schedule a new background-job attempt after failure."""

    def __init__(
        self,
        *,
        job_repository: ApplicationJobRepository,
        retry_policy_evaluator: RetryPolicyEvaluator,
        job_id_factory: Callable[[], str] | None = None,
        scheduling_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._job_repository = job_repository
        self._retry_policy_evaluator = (
            retry_policy_evaluator
        )
        self._job_id_factory = (
            job_id_factory
            or (lambda: f"retry-job-{uuid4()}")
        )
        self._scheduling_id_factory = (
            scheduling_id_factory
            or (lambda: f"retry-scheduling-{uuid4()}")
        )

    def schedule(
        self,
        *,
        source_job_id: str,
        failure: RetryFailureContext,
        now: datetime,
    ) -> ApplicationRetrySchedulingResult:
        """Evaluate and schedule the next job attempt."""

        self._require_aware(now)

        source = self._job_repository.require(source_job_id)

        self._validate_source_job(
            source=source,
            failure=failure,
        )
        self._ensure_retry_not_already_scheduled(source)

        decision = self._retry_policy_evaluator.evaluate(
            failure
        )

        if decision.decision is RetryDecisionType.STOP:
            return ApplicationRetrySchedulingResult(
                scheduling_id=self._new_scheduling_id(),
                source_job_id=source.job_id,
                status=(
                    ApplicationRetrySchedulingStatus.STOPPED
                ),
                retry_decision=decision,
                summary=(
                    "Retry scheduling stopped because "
                    f"{decision.stop_reason.value}."
                ),
                metadata={
                    "root_job_id": source.root_job_id,
                    "attempt_number": str(
                        source.attempt_number
                    ),
                },
            )

        if (
            decision.next_attempt is None
            or decision.delay_seconds is None
        ):
            raise ApplicationRetrySchedulingServiceError(
                "retry decision is missing scheduling data"
            )

        if decision.next_attempt != source.attempt_number + 1:
            raise ApplicationRetrySchedulingServiceError(
                "retry decision next_attempt does not match "
                "the source job"
            )

        scheduled = self._build_retry_job(
            source=source,
            next_attempt=decision.next_attempt,
            delay_seconds=decision.delay_seconds,
            retry_decision_id=decision.decision_id,
            now=now,
        )

        persisted = self._job_repository.create(scheduled)

        return ApplicationRetrySchedulingResult(
            scheduling_id=self._new_scheduling_id(),
            source_job_id=source.job_id,
            status=ApplicationRetrySchedulingStatus.SCHEDULED,
            retry_decision=decision,
            scheduled_job=persisted,
            summary=(
                "Retry attempt "
                f"{persisted.attempt_number} was scheduled "
                f"after {decision.delay_seconds:.4f} seconds."
            ),
            metadata={
                "root_job_id": source.root_job_id,
                "new_job_id": persisted.job_id,
            },
        )

    def _validate_source_job(
        self,
        *,
        source: ApplicationJobRecord,
        failure: RetryFailureContext,
    ) -> None:
        """Validate the source job and retry context."""

        if source.status is not ApplicationJobStatus.FAILED:
            raise ApplicationJobNotRetryableError(
                "retry scheduling requires a failed job"
            )

        if source.failure is None:
            raise ApplicationJobNotRetryableError(
                "failed source job requires failure information"
            )

        if not source.failure.retryable:
            raise ApplicationJobNotRetryableError(
                "source job failure is not retryable"
            )

        if failure.attempt_number != source.attempt_number:
            raise ApplicationRetrySchedulingServiceError(
                "retry failure attempt_number does not match "
                "the source job"
            )

    def _ensure_retry_not_already_scheduled(
        self,
        source: ApplicationJobRecord,
    ) -> None:
        """Reject duplicate next-attempt scheduling."""

        existing = self._job_repository.list(
            ApplicationJobQuery(
                previous_attempt_job_id=source.job_id,
                page_size=1,
            )
        )

        if existing.total_items > 0:
            raise ApplicationRetryAlreadyScheduledError(
                "retry attempt already exists for source job: "
                f"{source.job_id}"
            )

    def _build_retry_job(
        self,
        *,
        source: ApplicationJobRecord,
        next_attempt: int,
        delay_seconds: float,
        retry_decision_id: str,
        now: datetime,
    ) -> ApplicationJobRecord:
        """Build the next background-job attempt."""

        job_id = self._new_job_id()
        available_at = now + timedelta(
            seconds=delay_seconds
        )

        status = (
            ApplicationJobStatus.PENDING
            if delay_seconds == 0
            else ApplicationJobStatus.SCHEDULED
        )

        metadata = dict(source.metadata)
        metadata.update(
            {
                "retry_decision_id": retry_decision_id,
                "source_job_id": source.job_id,
            }
        )

        return ApplicationJobRecord(
            job_id=job_id,
            root_job_id=source.root_job_id,
            parent_job_id=source.parent_job_id,
            previous_attempt_job_id=source.job_id,
            request_id=source.request_id,
            workspace_id=source.workspace_id,
            execution_id=source.execution_id,
            job_type=ApplicationJobType.RETRY_EXECUTION,
            queue_name=source.queue_name,
            priority=source.priority,
            status=status,
            payload=dict(source.payload),
            attempt_number=next_attempt,
            maximum_attempts=source.maximum_attempts,
            available_at=available_at,
            created_at=now,
            record_version=1,
            metadata=metadata,
        )

    @staticmethod
    def _require_aware(now: datetime) -> None:
        """Require timezone-aware scheduling time."""

        if now.tzinfo is None:
            raise ApplicationRetrySchedulingServiceError(
                "now must be timezone-aware"
            )

    def _new_job_id(self) -> str:
        """Return one nonblank Job ID."""

        value = self._job_id_factory()

        if not value.strip():
            raise ApplicationRetrySchedulingServiceError(
                "job_id factory returned blank value"
            )

        return value

    def _new_scheduling_id(self) -> str:
        """Return one nonblank scheduling ID."""

        value = self._scheduling_id_factory()

        if not value.strip():
            raise ApplicationRetrySchedulingServiceError(
                "scheduling_id factory returned blank value"
            )

        return value
