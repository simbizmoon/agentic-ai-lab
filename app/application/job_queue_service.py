"""Application service for background-job queue operations."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import uuid4

from app.application.job_queue_service_error import (
    ApplicationJobLeaseExpiredError,
    ApplicationJobLeaseOwnershipError,
    ApplicationJobNotQueueableError,
    ApplicationJobQueueServiceError,
)
from app.application.job_record import (
    ApplicationJobLease,
    ApplicationJobRecord,
    ApplicationJobStatus,
)
from app.application.job_repository import (
    ApplicationJobRepository,
)
from app.application.job_repository_query import (
    ApplicationJobQuery,
)
from app.application.job_transition import (
    ApplicationJobTransitionPolicy,
)


class ApplicationJobQueueService:
    """Coordinate enqueue, lease, and worker queue operations."""

    def __init__(
        self,
        *,
        repository: ApplicationJobRepository,
        lease_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._repository = repository
        self._lease_id_factory = (
            lease_id_factory
            or (lambda: f"job-lease-{uuid4()}")
        )

    def enqueue(
        self,
        *,
        job_id: str,
        now: datetime,
    ) -> ApplicationJobRecord:
        """Move one available job into the queue."""

        self._require_aware(now)

        stored = self._repository.require(job_id)

        if not stored.available_for_queue_at(now):
            raise ApplicationJobNotQueueableError(
                "application job is not available for queueing: "
                f"{stored.job_id}"
            )

        ApplicationJobTransitionPolicy.require_transition(
            current=stored.status,
            target=ApplicationJobStatus.QUEUED,
        )

        updated = stored.model_copy(
            update={
                "status": ApplicationJobStatus.QUEUED,
                "queued_at": now,
                "record_version": stored.record_version + 1,
            }
        )

        return self._repository.update(
            updated,
            expected_version=stored.record_version,
        )

    def enqueue_due_jobs(
        self,
        *,
        now: datetime,
        queue_name: str | None = None,
        limit: int = 100,
    ) -> list[ApplicationJobRecord]:
        """Queue due pending, scheduled, or retry jobs."""

        self._require_aware(now)

        if limit < 1:
            raise ApplicationJobQueueServiceError(
                "limit must be at least 1"
            )

        if (
            queue_name is not None
            and not queue_name.strip()
        ):
            raise ApplicationJobQueueServiceError(
                "queue_name must not be blank when provided"
            )

        query = ApplicationJobQuery(
            queue_names=(
                [queue_name]
                if queue_name is not None
                else []
            ),
            statuses=[
                ApplicationJobStatus.PENDING,
                ApplicationJobStatus.SCHEDULED,
                ApplicationJobStatus.RETRY_SCHEDULED,
            ],
            available_to=now,
            page_size=min(limit, 200),
        )

        records = self._repository.list(query).items
        queued: list[ApplicationJobRecord] = []

        for record in records[:limit]:
            queued.append(
                self.enqueue(
                    job_id=record.job_id,
                    now=now,
                )
            )

        return queued

    def acquire(
        self,
        *,
        queue_name: str,
        worker_id: str,
        now: datetime,
        lease_duration_seconds: float,
    ) -> ApplicationJobRecord | None:
        """Lease the highest-priority queued job."""

        self._require_aware(now)

        if not worker_id.strip():
            raise ApplicationJobQueueServiceError(
                "worker_id must not be blank"
            )

        if lease_duration_seconds <= 0:
            raise ApplicationJobQueueServiceError(
                "lease_duration_seconds must be greater than 0"
            )

        candidates = self._repository.find_available(
            queue_name=queue_name,
            now=now,
            limit=1,
        )

        queued = [
            record
            for record in candidates
            if record.status is ApplicationJobStatus.QUEUED
        ]

        if not queued:
            return None

        stored = queued[0]

        ApplicationJobTransitionPolicy.require_transition(
            current=stored.status,
            target=ApplicationJobStatus.LEASED,
        )

        lease = ApplicationJobLease(
            lease_id=self._new_lease_id(),
            worker_id=worker_id,
            acquired_at=now,
            expires_at=(
                now + timedelta(
                    seconds=lease_duration_seconds
                )
            ),
        )

        updated = stored.model_copy(
            update={
                "status": ApplicationJobStatus.LEASED,
                "lease": lease,
                "record_version": stored.record_version + 1,
            }
        )

        return self._repository.update(
            updated,
            expected_version=stored.record_version,
        )

    def start(
        self,
        *,
        job_id: str,
        worker_id: str,
        now: datetime,
    ) -> ApplicationJobRecord:
        """Start a leased job owned by the worker."""

        self._require_aware(now)

        stored = self._repository.require(job_id)
        self._require_active_lease(
            record=stored,
            worker_id=worker_id,
            now=now,
        )

        ApplicationJobTransitionPolicy.require_transition(
            current=stored.status,
            target=ApplicationJobStatus.RUNNING,
        )

        updated = stored.model_copy(
            update={
                "status": ApplicationJobStatus.RUNNING,
                "started_at": now,
                "record_version": stored.record_version + 1,
            }
        )

        return self._repository.update(
            updated,
            expected_version=stored.record_version,
        )

    def release(
        self,
        *,
        job_id: str,
        worker_id: str,
        now: datetime,
    ) -> ApplicationJobRecord:
        """Release a leased job back to the queue."""

        self._require_aware(now)

        stored = self._repository.require(job_id)
        self._require_active_lease(
            record=stored,
            worker_id=worker_id,
            now=now,
        )

        if stored.status is not ApplicationJobStatus.LEASED:
            raise ApplicationJobQueueServiceError(
                "only a leased job may be released"
            )

        ApplicationJobTransitionPolicy.require_transition(
            current=stored.status,
            target=ApplicationJobStatus.QUEUED,
        )

        updated = stored.model_copy(
            update={
                "status": ApplicationJobStatus.QUEUED,
                "lease": None,
                "record_version": stored.record_version + 1,
            }
        )

        return self._repository.update(
            updated,
            expected_version=stored.record_version,
        )

    def renew_lease(
        self,
        *,
        job_id: str,
        worker_id: str,
        now: datetime,
        lease_duration_seconds: float,
    ) -> ApplicationJobRecord:
        """Extend an active worker lease."""

        self._require_aware(now)

        if lease_duration_seconds <= 0:
            raise ApplicationJobQueueServiceError(
                "lease_duration_seconds must be greater than 0"
            )

        stored = self._repository.require(job_id)
        self._require_active_lease(
            record=stored,
            worker_id=worker_id,
            now=now,
        )

        assert stored.lease is not None

        renewed = ApplicationJobLease(
            lease_id=stored.lease.lease_id,
            worker_id=stored.lease.worker_id,
            acquired_at=stored.lease.acquired_at,
            expires_at=(
                now + timedelta(
                    seconds=lease_duration_seconds
                )
            ),
        )

        updated = stored.model_copy(
            update={
                "lease": renewed,
                "record_version": stored.record_version + 1,
            }
        )

        return self._repository.update(
            updated,
            expected_version=stored.record_version,
        )

    def recover_expired_leases(
        self,
        *,
        now: datetime,
        queue_name: str | None = None,
        limit: int = 100,
    ) -> list[ApplicationJobRecord]:
        """Return expired leased jobs to the queue."""

        self._require_aware(now)

        if limit < 1:
            raise ApplicationJobQueueServiceError(
                "limit must be at least 1"
            )

        query = ApplicationJobQuery(
            queue_names=(
                [queue_name]
                if queue_name is not None
                else []
            ),
            statuses=[ApplicationJobStatus.LEASED],
            leased_only=True,
            page_size=min(limit, 200),
        )

        records = self._repository.list(query).items
        recovered: list[ApplicationJobRecord] = []

        for stored in records[:limit]:
            if (
                stored.lease is None
                or stored.lease.active_at(now)
            ):
                continue

            ApplicationJobTransitionPolicy.require_transition(
                current=stored.status,
                target=ApplicationJobStatus.QUEUED,
            )

            updated = stored.model_copy(
                update={
                    "status": ApplicationJobStatus.QUEUED,
                    "lease": None,
                    "record_version": (
                        stored.record_version + 1
                    ),
                }
            )

            recovered.append(
                self._repository.update(
                    updated,
                    expected_version=stored.record_version,
                )
            )

        return recovered

    @staticmethod
    def _require_aware(now: datetime) -> None:
        """Require a timezone-aware datetime."""

        if now.tzinfo is None:
            raise ApplicationJobQueueServiceError(
                "now must be timezone-aware"
            )

    @staticmethod
    def _require_active_lease(
        *,
        record: ApplicationJobRecord,
        worker_id: str,
        now: datetime,
    ) -> None:
        """Require an active lease owned by one worker."""

        if record.lease is None:
            raise ApplicationJobLeaseOwnershipError(
                "application job has no active lease"
            )

        if (
            record.lease.worker_id.strip().casefold()
            != worker_id.strip().casefold()
        ):
            raise ApplicationJobLeaseOwnershipError(
                "application job lease is owned by another "
                "worker"
            )

        if not record.lease.active_at(now):
            raise ApplicationJobLeaseExpiredError(
                "application job lease has expired"
            )

    def _new_lease_id(self) -> str:
        """Return one nonblank lease identifier."""

        value = self._lease_id_factory()

        if not value.strip():
            raise ApplicationJobQueueServiceError(
                "lease_id factory returned blank value"
            )

        return value
