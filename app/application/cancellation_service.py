"""Application service for persisted job cancellation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from app.application.cancellation_record import (
    ApplicationCancellationStatus,
    ApplicationJobCancellationRequestRecord,
)
from app.application.cancellation_repository import (
    ApplicationCancellationRepository,
)
from app.application.cancellation_service_error import (
    ApplicationCancellationAlreadyActiveError,
    ApplicationCancellationServiceError,
    ApplicationCancellationStateError,
    ApplicationJobCannotBeCancelledError,
)
from app.application.job_record import (
    ApplicationJobCancellation,
    ApplicationJobRecord,
    ApplicationJobStatus,
)
from app.application.job_repository import (
    ApplicationJobRepository,
)
from app.application.job_transition import (
    ApplicationJobTransitionPolicy,
)


class ApplicationCancellationService:
    """Persist and coordinate background-job cancellation."""

    def __init__(
        self,
        *,
        job_repository: ApplicationJobRepository,
        cancellation_repository: (
            ApplicationCancellationRepository
        ),
        cancellation_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._job_repository = job_repository
        self._cancellation_repository = (
            cancellation_repository
        )
        self._cancellation_id_factory = (
            cancellation_id_factory
            or (lambda: f"cancellation-{uuid4()}")
        )

    def request(
        self,
        *,
        job_id: str,
        requested_by: str,
        reason: str,
        now: datetime,
        force: bool = False,
    ) -> ApplicationJobCancellationRequestRecord:
        """Persist a new cancellation request."""

        self._require_aware(now)

        if not requested_by.strip():
            raise ApplicationCancellationServiceError(
                "requested_by must not be blank"
            )

        if not reason.strip():
            raise ApplicationCancellationServiceError(
                "reason must not be blank"
            )

        job = self._job_repository.require(job_id)

        if job.terminal:
            raise ApplicationJobCannotBeCancelledError(
                "terminal application job cannot be cancelled"
            )

        active = (
            self._cancellation_repository
            .find_active_by_job_id(job.job_id)
        )

        if active is not None:
            raise ApplicationCancellationAlreadyActiveError(
                "application job already has an active "
                f"cancellation request: {job.job_id}"
            )

        ApplicationJobTransitionPolicy.require_transition(
            current=job.status,
            target=(
                ApplicationJobStatus.CANCELLATION_REQUESTED
            ),
        )

        cancellation_id = self._new_cancellation_id()

        persisted_request = (
            self._cancellation_repository.create(
                ApplicationJobCancellationRequestRecord(
                    cancellation_request_id=cancellation_id,
                    job_id=job.job_id,
                    request_id=job.request_id,
                    workspace_id=job.workspace_id,
                    requested_by=requested_by,
                    reason=reason,
                    force=force,
                    status=(
                        ApplicationCancellationStatus.REQUESTED
                    ),
                    requested_at=now,
                )
            )
        )

        job_cancellation = ApplicationJobCancellation(
            cancellation_id=cancellation_id,
            requested_at=now,
            requested_by=requested_by,
            reason=reason,
            force=force,
        )

        updated_job = self._replace_job(
            job,
            status=(
                ApplicationJobStatus.CANCELLATION_REQUESTED
            ),
            cancellation=job_cancellation,
            lease=None,
            record_version=job.record_version + 1,
        )

        self._job_repository.update(
            updated_job,
            expected_version=job.record_version,
        )

        return persisted_request

    def acknowledge(
        self,
        *,
        cancellation_request_id: str,
        acknowledged_by: str,
        now: datetime,
    ) -> ApplicationJobCancellationRequestRecord:
        """Record worker acknowledgement of cancellation."""

        self._require_aware(now)

        if not acknowledged_by.strip():
            raise ApplicationCancellationServiceError(
                "acknowledged_by must not be blank"
            )

        stored = self._cancellation_repository.require(
            cancellation_request_id
        )

        if (
            stored.status
            is not ApplicationCancellationStatus.REQUESTED
        ):
            raise ApplicationCancellationStateError(
                "only requested cancellation may be "
                "acknowledged"
            )

        updated = ApplicationJobCancellationRequestRecord(
            **stored.model_dump(
                exclude={
                    "status",
                    "acknowledged_at",
                    "acknowledged_by",
                    "record_version",
                }
            ),
            status=ApplicationCancellationStatus.ACKNOWLEDGED,
            acknowledged_at=now,
            acknowledged_by=acknowledged_by,
            record_version=stored.record_version + 1,
        )

        return self._cancellation_repository.update(
            updated,
            expected_version=stored.record_version,
        )

    def complete(
        self,
        *,
        cancellation_request_id: str,
        completed_by: str,
        now: datetime,
    ) -> ApplicationJobCancellationRequestRecord:
        """Complete cancellation and terminate the job."""

        self._require_aware(now)

        if not completed_by.strip():
            raise ApplicationCancellationServiceError(
                "completed_by must not be blank"
            )

        stored = self._cancellation_repository.require(
            cancellation_request_id
        )

        if stored.terminal:
            raise ApplicationCancellationStateError(
                "completed cancellation cannot be completed "
                "again"
            )

        job = self._job_repository.require(stored.job_id)

        if (
            job.status
            is not ApplicationJobStatus.CANCELLATION_REQUESTED
        ):
            raise ApplicationCancellationStateError(
                "job must be cancellation_requested before "
                "completion"
            )

        ApplicationJobTransitionPolicy.require_transition(
            current=job.status,
            target=ApplicationJobStatus.CANCELLED,
        )

        updated_request = (
            ApplicationJobCancellationRequestRecord(
                **stored.model_dump(
                    exclude={
                        "status",
                        "completed_at",
                        "completed_by",
                        "record_version",
                    }
                ),
                status=ApplicationCancellationStatus.COMPLETED,
                completed_at=now,
                completed_by=completed_by,
                record_version=stored.record_version + 1,
            )
        )

        persisted_request = (
            self._cancellation_repository.update(
                updated_request,
                expected_version=stored.record_version,
            )
        )

        updated_job = self._replace_job(
            job,
            status=ApplicationJobStatus.CANCELLED,
            finished_at=now,
            lease=None,
            record_version=job.record_version + 1,
        )

        self._job_repository.update(
            updated_job,
            expected_version=job.record_version,
        )

        return persisted_request

    @staticmethod
    def _replace_job(
        job: ApplicationJobRecord,
        **updates: object,
    ) -> ApplicationJobRecord:
        """Revalidate a Job after applying lifecycle changes."""

        values = job.model_dump()
        values.update(updates)

        return ApplicationJobRecord.model_validate(values)

    @staticmethod
    def _require_aware(now: datetime) -> None:
        """Require a timezone-aware datetime."""

        if now.tzinfo is None:
            raise ApplicationCancellationServiceError(
                "now must be timezone-aware"
            )

    def _new_cancellation_id(self) -> str:
        """Return one nonblank cancellation request ID."""

        value = self._cancellation_id_factory()

        if not value.strip():
            raise ApplicationCancellationServiceError(
                "cancellation ID factory returned blank value"
            )

        return value
